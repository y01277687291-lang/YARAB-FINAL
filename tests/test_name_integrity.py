# -*- coding: utf-8 -*-
"""
اختبار ضمان سلامة الاسم المعروض (Name Integrity Guard)
--------------------------------------------------------
يثبت آلياً، وبشكل دائم يمنع رجوع أي خطأ مستقبلي، ضمانتين طلبهما المستخدم:

  1) أي اسم صنف "مطابَق" (source == "database") يظهر على الشاشة لازم يكون
     نفس النص المكتوب في شيت الأصناف حرفاً بحرف (بدون أي تعديل/إعادة صياغة
     من محرك التعريب) — لأن الاسم بييجي مباشرة من عمود "صنف" في الملف نفسه.

  2) لو اسم الصنف في الفاتورة فيه أرقام (جرعة/عدد شريط/حجم عبوة)، لازم
     النظام ميختارش صنف بجرعة مختلفة حتى لو تشابه نصياً بنسبة عالية جداً —
     ده كان سبب ظهور "اسم غلط" فعلياً في شيت العميل (463 مجموعة أصناف
     متطابقة الاسم ومختلفة الجرعة فقط، زي "أوجمنتين 600 مجم" و"457 مجم").

يعمل بدون أي ملف خارجي (بيانات وهمية مضمّنة تحاكي المشكلة الحقيقية)،
فيُشغَّل بسهولة في أي بيئة تطوير أو CI بدون الحاجة لشيت أصناف حقيقي:

    python -m tests.test_name_integrity
    # أو:
    pytest tests/test_name_integrity.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from engine.matcher import ProductMatcher, build_search_key  # noqa: E402
from engine.pipeline import PharmaPipeline  # noqa: E402

# بيانات وهمية تحاكي بالضبط مشكلة "نفس الاسم، جرعة مختلفة" الموجودة فعلياً
# في شيت العميل (463 مجموعة مشابهة) — أكتر حالة خطيرة لظهور اسم/جرعة غلط
SAMPLE_PRODUCTS = [
    ("1001", "اوجمنتين 600 مجم شراب سعر جديد", 100.0),
    ("1002", "اوجمنتين 457 مجم شراب سعر جديد", 90.0),
    ("1003", "اوجمنتين 312 مجم شراب سعر جديد", 80.0),
    ("1004", "اوجمنتين 156 مجم شراب سعر جديد", 70.0),
    ("1005", "كتافلام 50 مجم اقراص سعر جديد", 45.0),
    ("1006", "كتافلام 25 مجم اقراص سعر جديد", 35.0),
    ("1007", "زوركال 40 مجم 28 قرص سعر جديد", 60.0),
    ("1008", "زوركال 40 مجم 14 قرص سعر جديد", 40.0),
    ("1009", "زوركال 20 مجم 14 قرص سعر جديد", 30.0),
    ("1010", "بانادول اكسترا 500 مجم 24 قرص", 20.0),
    ("1011", "ليبيتور 20 مجم 28 قرص سعر جديد", 150.0),
]


def _build_test_matcher() -> ProductMatcher:
    matcher = ProductMatcher()
    df = pd.DataFrame(SAMPLE_PRODUCTS, columns=["كود", "صنف", "سعر"])
    matcher.df = df
    matcher._search_keys = [build_search_key(n) for n in df["صنف"].tolist()]
    return matcher


def _build_test_pipeline() -> PharmaPipeline:
    pipeline = PharmaPipeline()
    pipeline.matcher = _build_test_matcher()
    return pipeline


# (نص الفاتورة, الاسم الصحيح المتوقع من الشيت أو None لو محتاج تأكيد يدوي)
DOSAGE_SAFETY_CASES = [
    ("اوجمنتين 600 مجم شراب", "اوجمنتين 600 مجم شراب سعر جديد"),
    ("اوجمنتين 457 مجم شراب", "اوجمنتين 457 مجم شراب سعر جديد"),
    ("اوجمنتين 312 مجم شراب", "اوجمنتين 312 مجم شراب سعر جديد"),
    ("اوجمنتين 156 مجم شراب", "اوجمنتين 156 مجم شراب سعر جديد"),
    ("كتافلام 50 مجم اقراص", "كتافلام 50 مجم اقراص سعر جديد"),
    ("كتافلام 25 مجم اقراص", "كتافلام 25 مجم اقراص سعر جديد"),
    ("زوركال 40 مجم 28 قرص", "زوركال 40 مجم 28 قرص سعر جديد"),
    ("زوركال 40 مجم 14 قرص", "زوركال 40 مجم 14 قرص سعر جديد"),
    # جرعة غير موجودة إطلاقاً في الشيت -> يجب ألا يُعتمد أي تطابق تلقائي
    ("اوجمنتين 999 مجم شراب", None),
]


def test_dosage_safety_never_picks_wrong_strength():
    """يمنع اختيار جرعة/عبوة خاطئة رغم التشابه النصي العالي جداً بينها."""
    pipeline = _build_test_pipeline()
    for invoice_text, expected_name in DOSAGE_SAFETY_CASES:
        result = pipeline.process_line(invoice_text)
        if expected_name is None:
            assert result.source != "database" or result.color == "red", (
                f"كان يجب عدم اعتماد أي تطابق تلقائي لـ {invoice_text!r} "
                f"(جرعة غير موجودة بالشيت) لكن ظهر: {result.suggested_arabic!r}"
            )
        else:
            assert result.suggested_arabic == expected_name, (
                f"لـ {invoice_text!r}: كان المتوقع {expected_name!r} "
                f"لكن ظهر {result.suggested_arabic!r} - احتمال اختيار جرعة/عبوة خاطئة!"
            )


def test_matched_name_is_byte_for_byte_from_sheet():
    """أي اسم 'مطابَق' من قاعدة البيانات لازم يكون موجوداً حرفياً في الشيت."""
    pipeline = _build_test_pipeline()
    sheet_names = set(pipeline.matcher.df["صنف"].tolist())
    for invoice_text, expected_name in DOSAGE_SAFETY_CASES:
        if expected_name is None:
            continue
        result = pipeline.process_line(invoice_text)
        assert result.source == "database", f"لم يتم العثور على تطابق لـ {invoice_text!r}"
        assert result.suggested_arabic in sheet_names, (
            f"الاسم المعروض {result.suggested_arabic!r} غير موجود حرفياً في الشيت! "
            "هذا يعني أن الاسم اتولّد من محرك التعريب وليس من الشيت مباشرة."
        )


def test_unrelated_brand_never_matched_by_shared_dosage_words():
    """
    يعيد إنتاج مشكلة حقيقية اتبلّغ عنها: 'بيبرا 20 مجم' (اسم غير موجود
    إطلاقاً بالشيت) كان بيتطابق مع 'ليبيتور 20 مجم 28 قرص' بنسبة 81% لمجرد
    اشتراكهم في كلمات عامة (20، مجم، قرص) رغم إن الدواءين مختلفان تماماً.
    حارس الاسم التجاري (مقارنة أفضل زوج كلمات جوهرية بعد استبعاد كلمات
    الشكل/الجرعة العامة) لازم يرفض التطابق ده نهائياً.
    """
    pipeline = _build_test_pipeline()
    result = pipeline.process_line("بيبرا 20 مجم")
    assert result.source != "database" or result.color == "red", (
        f"مفروض عدم اعتماد تطابق تلقائي لـ 'بيبرا 20 مجم' (اسم غير موجود بالشيت)، "
        f"لكن ظهر: {result.suggested_arabic!r} - احتمال تطابق بصنف مختلف تماماً بسبب كلمات مشتركة عامة!"
    )


def test_form_conflict_never_matched_even_same_brand():
    """
    حارس الشكل الصيدلي: لازم يرفض تطابق دواء بنفس الاسم التجاري تقريباً
    بس شكل مختلف تماماً (قرص مقابل كريم مثلاً) - الشكل جزء من هوية الصنف.
    """
    pipeline = _build_test_pipeline()
    # مفيش أي "كتافلام كريم" في الشيت التجريبي (بس فيه كتافلام أقراص) -
    # فمفروض ميتقبلش تلقائياً حتى لو الاسم التجاري "كتافلام" مطابق تماماً.
    result = pipeline.process_line("كتافلام 50 مجم كريم")
    assert result.source != "database" or result.color == "red", (
        f"مفروض عدم اعتماد تطابق تلقائي لـ 'كتافلام 50 مجم كريم' (الشكل الصيدلي مختلف عن أي صنف بالشيت)، "
        f"لكن ظهر: {result.suggested_arabic!r}"
    )


def main():
    tests = [test_dosage_safety_never_picks_wrong_strength, test_matched_name_is_byte_for_byte_from_sheet,
              test_unrelated_brand_never_matched_by_shared_dosage_words,
              test_form_conflict_never_matched_even_same_brand]
    for t in tests:
        t()
        print(f"✅ {t.__name__}")
    print("-" * 70)
    print("كل ضمانات سلامة الاسم اجتازت الاختبار بنجاح.")


if __name__ == "__main__":
    main()
