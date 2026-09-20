# -*- coding: utf-8 -*-
"""
اختبارات التعديلات المطلوبة:
  1) Constrained Matching: أي اسم مُقترح (حتى بثقة منخفضة) لازم يكون
     نص حرفي من شيت فارما تشين نفسه، أبداً تخمين حر من محرك التعريب.
  2) السعر كعامل ترجيح: صنف بنفس الاسم تقريباً لكن سعر مختلف يُختار
     الأقرب سعراً لصنف الفاتورة.
  3) قائمة الاستبعاد (Blacklist): صنف يتسجّل "مستبعد" مرة واحدة، وبعد
     كده أي ظهور له (أو لنص مشابه له جداً) يترجع بعلم ignored=True.
"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.matcher import ProductMatcher, build_search_key  # noqa: E402
from engine.pipeline import PharmaPipeline  # noqa: E402
from engine.ignored_items_manager import IgnoredItemsManager  # noqa: E402

SAMPLE_PRODUCTS = [
    ("2001", "بانادول اكسترا 24 قرص سعر جديد", 20.0),
    ("2002", "بانادول اكسترا 12 قرص سعر جديد", 12.0),
    ("2003", "اوجمنتين 600 مجم شراب سعر جديد", 100.0),
]


def _build_test_matcher():
    matcher = ProductMatcher()
    df = pd.DataFrame(SAMPLE_PRODUCTS, columns=["كود", "صنف", "سعر"])
    matcher.df = df
    matcher._search_keys = [build_search_key(n) for n in df["صنف"].tolist()]
    return matcher


def _build_test_pipeline():
    pipeline = PharmaPipeline()
    pipeline.matcher = _build_test_matcher()
    return pipeline


def test_low_confidence_suggestion_never_shows_an_unrelated_real_item():
    """
    حتى مع صنف مش موجود إطلاقاً بنفس الجرعة (999mg مش موجودة، بس نفس
    الشكل موجود بجرعة تانية 600 مجم)، الاسم المقترح لازم يكون إما اسم
    حقيقي من الشيت *معقول الصلة* (نفس البراند)، أو مفيش اقتراح محدَّد
    خالص (خانة فاضية - غير مطابق) — ممنوع إطلاقاً يظهر اسم صنف حقيقي لكنه
    غير مرتبط بالمرة (مشكلة حقيقية اتبلّغ عنها: 'BEPRA' كان بيظهر مقترَح
    ليها 'ليبيتور' لمجرد تشابه كلمات عامة زي الجرعة والعدد)، وممنوع
    إطلاقاً يظهر تخمين حر من محرك التعريب الصوتي كـ"اقتراح".
    """
    pipeline = _build_test_pipeline()
    sheet_names = set(pipeline.matcher.df["صنف"].tolist())
    result = pipeline.process_line("Augmentin 999mg Syrup")
    assert result.color == "red"
    if result.source == "database_low_confidence":
        assert result.suggested_arabic in sheet_names
        assert "اوجمنتين" in result.suggested_arabic  # لازم يكون نفس البراند على الأقل
    else:
        assert result.source == "unmatched"
        assert result.suggested_arabic == ""  # مفيش تخمين حر - خانة فاضية تحتاج إدخال يدوي


def test_unrelated_high_score_candidate_never_shown_as_closest_suggestion():
    """
    إعادة إنتاج مباشرة لمشكلة حقيقية: صنف مش موجود بالشيت (BEPRA) بيوصل
    لنسبة تشابه عالية مع صنف تاني مختلف تماماً (ليبيتور) لمجرد اشتراكهم
    في كلمات عامة زي الجرعة والعدد ("20 مجم 28 قرص"). المقترح المعروض
    (لو فيه أي اقتراح أصلاً) ممنوع يكون 'ليبيتور' - غير مرتبط بالمرة.
    """
    with tempfile.TemporaryDirectory() as tmp:
        products_path = os.path.join(tmp, "products.xlsx")
        pd.DataFrame(
            [("1", "ليبيتور 20 مجم 28 قرص سعر جديد", 206.0),
             ("2", "بانادول اكسترا 24 قرص سعر جديد", 20.0)],
            columns=["كود", "صنف", "سعر"],
        ).to_excel(products_path, index=False)
        pipeline = PharmaPipeline(products_path=products_path)
        result = pipeline.process_line("BEPRA 20MG 28 F.C. TAB.")
        assert result.color == "red"
        assert result.suggested_arabic != "ليبيتور 20 مجم 28 قرص سعر جديد"


def test_database_match_never_reaches_100_percent():
    """100% محجوزة حصرياً للاستثناءات المؤكَّدة يدوياً والشيت المرجعي - أي
    تطابق آلي (Fuzzy) عن طريق قاعدة البيانات، حتى لو نص مطابق تماماً حرفياً،
    لازم سقفه 98% كحد أقصى."""
    with tempfile.TemporaryDirectory() as tmp:
        products_path = os.path.join(tmp, "products.xlsx")
        pd.DataFrame(
            [("1", "كونترولوك 40 مجم 14 قرص سعر جديد", 188.0)], columns=["كود", "صنف", "سعر"]
        ).to_excel(products_path, index=False)
        pipeline = PharmaPipeline(products_path=products_path)
        result = pipeline.process_line("كونترولوك 40 مجم 14 قرص سعر جديد")  # نفس نص صنف حقيقي بالحرف
        assert result.source == "database"
        assert result.score <= 98.0


def test_price_disambiguates_similar_named_items():
    """بانادول اكسترا 24 قرص و12 قرص بنفس الاسم تقريباً وسعر مختلف —
    لازم السعر يرجّح اختيار الصنف الصحيح."""
    pipeline = _build_test_pipeline()
    result = pipeline.process_line("Panadol Extra 12 Tab", invoice_price=12.0)
    assert result.matched_price in ("12.0", "12")
    assert "12" in result.suggested_arabic


def test_ignored_items_manager_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Ignored_Items.xlsx")
        mgr = IgnoredItemsManager(path)
        assert not mgr.is_ignored("Cotton Roll")
        mgr.add("Cotton Roll Bag")
        assert mgr.is_ignored("Cotton Roll Bag")
        # فرق مسافات بسيط - لازم يتلقط بالمطابقة الضبابية الاحتياطية
        assert mgr.is_ignored("Cotton  Roll   Bag")


def test_pipeline_marks_ignored_items_automatically():
    pipeline = _build_test_pipeline()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Ignored_Items.xlsx")
        pipeline.ignored = IgnoredItemsManager(path)
        pipeline.add_ignored("Cosmetics Bag Free Item")

        result = pipeline.process_line("Cosmetics Bag Free Item")
        assert result.ignored is True

        # صنف مختلف تماماً يفضل مش مستبعد
        other = pipeline.process_line("Augmentin 600mg Syrup")
        assert other.ignored is False
