# -*- coding: utf-8 -*-
"""اختبار ميزة "الأصناف المهمة" (أدوية جدول) - controlled_items.py و
تكاملها مع pipeline.py (العلم controlled على LineResult، بمعزل عن مصدر
النتيجة: استثناء/شيت مرجعي/قاعدة بيانات/تخمين المحرك)."""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.controlled_items import ControlledItemsManager  # noqa: E402
from engine.pipeline import PharmaPipeline  # noqa: E402

# نفس شكل الشيت الحقيقي: صف عنوان + صف فاضي + صف هيدر أعمدة، ثم البيانات
CONTROLLED_SHEET_ROWS = [
    ["جدول أصناف مهمه (محدث)", None],
    [None, None],
    ["م", "اسم الصنف"],
    [1, "جابتن"],
    [2, "نايت كالم"],
]


def _build_controlled_xlsx(tmp_dir):
    path = os.path.join(tmp_dir, "Controlled_Items.xlsx")
    pd.DataFrame(CONTROLLED_SHEET_ROWS).to_excel(path, index=False, header=False)
    return path


def test_loads_correct_count_skipping_header_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = _build_controlled_xlsx(tmp)
        cm = ControlledItemsManager(path)
        assert len(cm) == 2  # مش 5 - لازم يتجاهل صفوف العنوان/الهيدر


def test_single_word_brand_matched_with_dosage_suffix():
    with tempfile.TemporaryDirectory() as tmp:
        cm = ControlledItemsManager(_build_controlled_xlsx(tmp))
        assert cm.is_controlled("جابتن 300 مجم 20 كبسولة سعر جديد") is True


def test_multi_word_brand_requires_both_words_present():
    with tempfile.TemporaryDirectory() as tmp:
        cm = ControlledItemsManager(_build_controlled_xlsx(tmp))
        assert cm.is_controlled("نايت كالم 2 جم 30 قرص") is True
        assert cm.is_controlled("نايت فقط") is False  # كلمة وحدة بس من الاسم المكوَّن من كلمتين


def test_unrelated_item_not_flagged():
    with tempfile.TemporaryDirectory() as tmp:
        cm = ControlledItemsManager(_build_controlled_xlsx(tmp))
        assert cm.is_controlled("بروفين شراب 150 مل سعر جديد") is False


def test_pipeline_sets_controlled_flag_regardless_of_source():
    """العلم controlled لازم يتحسب على النتيجة النهائية أياً كان مصدرها -
    هنا حالة صنف مش موجود بالشيت الأساسي أصلاً (غير مطابق تماماً) - لازم
    يتلوّن كمهم برضه بالاعتماد على تخمين المحرك الداخلي للتنبيه الأمني
    فقط (مش معروض كاسم مقترَح للمستخدم، الخانة تفضل فاضية)."""
    with tempfile.TemporaryDirectory() as tmp:
        controlled_path = _build_controlled_xlsx(tmp)
        products_path = os.path.join(tmp, "products.xlsx")
        pd.DataFrame([("1", "بانادول اكسترا 24 قرص", 20.0)], columns=["كود", "صنف", "سعر"]).to_excel(
            products_path, index=False
        )
        pipeline = PharmaPipeline(products_path=products_path, controlled_items_path=controlled_path)
        result = pipeline.process_line("GABTIN 300MG")
        assert result.controlled is True

        result2 = pipeline.process_line("BRUFEN SYRUP 150 ML")
        assert result2.controlled is False
