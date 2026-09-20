# -*- coding: utf-8 -*-
"""اختبار وحدة تسجيل الأصناف الناقصة (missing_items.py)."""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from missing_items import MissingItemsManager, COLUMNS  # noqa: E402


def test_record_creates_file_with_expected_columns():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Missing_Items.xlsx")
        mgr = MissingItemsManager(path)
        mgr.record(
            pharmacy_name="صيدلية تجريبية",
            invoice_filename="INV-001.pdf",
            original_text="Xigduo 5/1000mg",
            arabic_text="زيجدو 5/1000 مجم",
            invoice_price=120.5,
            quantity=3,
        )
        assert os.path.exists(path)
        df = pd.read_excel(path)
        assert list(df.columns) == COLUMNS
        assert len(df) == 1
        assert df.iloc[0]["الاسم الأصلي (Odoo)"] == "Xigduo 5/1000mg"


def test_record_appends_without_losing_previous_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Missing_Items.xlsx")
        mgr = MissingItemsManager(path)
        mgr.record("صيدلية أ", "INV-001.pdf", "Item A", "الصنف أ", 10, 1)
        mgr.record("صيدلية أ", "INV-002.pdf", "Item B", "الصنف ب", 20, 2)

        df = pd.read_excel(path)
        assert len(df) == 2
        assert set(df["الاسم الأصلي (Odoo)"]) == {"Item A", "Item B"}


def test_record_handles_missing_optional_fields():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Missing_Items.xlsx")
        mgr = MissingItemsManager(path)
        mgr.record(pharmacy_name=None, invoice_filename=None,
                    original_text="Item C", arabic_text="", invoice_price=None, quantity=None)
        df = pd.read_excel(path)
        assert len(df) == 1
        assert df.iloc[0]["الصيدلية"] == "" or pd.isna(df.iloc[0]["الصيدلية"])


def test_count_and_clear():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Missing_Items.xlsx")
        mgr = MissingItemsManager(path)
        assert mgr.count() == 0
        mgr.record("صيدلية أ", "INV-001.pdf", "Item A", "الصنف أ", 10, 1)
        mgr.record("صيدلية أ", "INV-002.pdf", "Item B", "الصنف ب", 20, 2)
        assert mgr.count() == 2

        mgr.clear()
        assert mgr.count() == 0
        df = pd.read_excel(path)
        assert list(df.columns) == COLUMNS  # الهيدر لسه موجود، بس مفيش صفوف


def test_record_does_not_duplicate_same_item():
    """نفس الصنف (نفس الاسم الأصلي) ميتكررش في شيت النواقص حتى لو اتضغط
    عليه 'ناقص' كذا مرة - إلا بعد تصفير الشيت بالكامل."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "Missing_Items.xlsx")
        mgr = MissingItemsManager(path)

        added1 = mgr.record("صيدلية أ", "INV-001.pdf", "DUPLICATE ITEM", "صنف مكرر", 15, 1)
        assert added1 is True
        assert mgr.count() == 1

        # نفس الاسم بالظبط تاني (من نفس الفاتورة أو فاتورة تانية)
        added2 = mgr.record("صيدلية أ", "INV-002.pdf", "DUPLICATE ITEM", "صنف مكرر", 15, 3)
        assert added2 is False
        assert mgr.count() == 1  # لسه صف واحد بس، مفيش تكرار

        # نفس الاسم بفروق حالة أحرف/مسافات - برضه يُعتبر تكرار
        added3 = mgr.record("صيدلية أ", "INV-003.pdf", "  duplicate item  ", "صنف مكرر", 15, 1)
        assert added3 is False
        assert mgr.count() == 1

        # بعد التصفير، نفس الصنف يُقبل تاني كسطر جديد
        mgr.clear()
        added4 = mgr.record("صيدلية أ", "INV-004.pdf", "DUPLICATE ITEM", "صنف مكرر", 15, 1)
        assert added4 is True
        assert mgr.count() == 1
