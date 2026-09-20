# -*- coding: utf-8 -*-
"""اختبار الشيت المرجعي الجاهز (English_Arabic_Map.xlsx) كـ Step A في خط
الأنابيب: لو الاسم الإنجليزي موجود فيه، لازم يرجع الاسم/السعر حرفياً 100%
من شيت الأصناف الحقيقي (عن طريق الكود)، قبل أي تعريب أو Fuzzy matching."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from engine.pipeline import PharmaPipeline  # noqa: E402

PRODUCTS = [
    ("1001", "كونترولوك 40 مجم 14 قرص سعر جديد", 188.0),
    ("1002", "بروفين شراب 150 مل سعر جديد", 44.0),
    ("1003", "بانادول اكسترا 500 مجم 24 قرص", 20.0),
]

REFERENCE_MAP = [
    # الاسم في هذا الشيت المرجعي عمداً بدون لاحقة "سعر جديد" - يحاكي فرق
    # الصياغة الحقيقي بين الشيتين، عشان نتأكد إننا بنرجع نص products.xlsx
    # الحرفي مش نص هذا الشيت.
    ("1001", "كونترولوك 40 مجم 14 قرص", 188, "18437", "CONTROLOC 40 MG 14 TAB", 188),
    ("1002", "بروفين شراب 150 مل", 44, "17179", "BRUFEN SYRUP 150 ML", 44),
]


def _build_pipeline(tmp_dir):
    products_path = os.path.join(tmp_dir, "products.xlsx")
    ref_path = os.path.join(tmp_dir, "English_Arabic_Map.xlsx")
    pd.DataFrame(PRODUCTS, columns=["كود", "صنف", "سعر"]).to_excel(products_path, index=False)
    pd.DataFrame(
        REFERENCE_MAP,
        columns=["الكود (عربي)", "الصنف (عربي)", "السعر", "الكود (دواء)", "المقابل الإنجليزي", "سعر المقابل"],
    ).to_excel(ref_path, index=False)
    return PharmaPipeline(products_path=products_path, reference_map_path=ref_path)


def test_reference_map_returns_exact_sheet_text_not_reference_sheet_text():
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _build_pipeline(tmp)
        result = pipeline.process_line("CONTROLOC 40 MG 14 TAB")
        assert result.source == "reference_map"
        assert result.score == 98.0
        # لازم يرجع نص products.xlsx الحرفي (باللاحقة)، مش نص الشيت المرجعي
        assert result.suggested_arabic == "كونترولوك 40 مجم 14 قرص سعر جديد"


def test_reference_map_lookup_is_case_and_spacing_insensitive():
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _build_pipeline(tmp)
        result = pipeline.process_line("  brufen   syrup 150 ml  ")
        assert result.source == "reference_map"
        assert result.suggested_arabic == "بروفين شراب 150 مل سعر جديد"


def test_unmapped_english_name_falls_through_to_normal_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _build_pipeline(tmp)
        result = pipeline.process_line("PANADOL EXTRA 500MG 24 TAB")
        assert result.source != "reference_map"


def test_manual_exception_overrides_reference_map():
    """لو المستخدم أكّد يدوياً اسم مختلف لنفس الصنف، تأكيده الصريح لازم يفوز
    على الشيت المرجعي الثابت (الاستثناءات بتتفحص أولاً في الكود)."""
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = _build_pipeline(tmp)
        pipeline.exceptions = None  # سنمرر مسار استثناءات حقيقي بدل كده
        exceptions_path = os.path.join(tmp, "Exceptions.xlsx")
        from engine.exceptions_manager import ExceptionsManager
        pipeline.exceptions = ExceptionsManager(exceptions_path)
        pipeline.exceptions.add_exception("CONTROLOC 40 MG 14 TAB", "بانادول اكسترا 500 مجم 24 قرص")

        result = pipeline.process_line("CONTROLOC 40 MG 14 TAB")
        assert result.source == "exception"
        assert result.suggested_arabic == "بانادول اكسترا 500 مجم 24 قرص"
