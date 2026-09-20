# -*- coding: utf-8 -*-
"""
قارئ فواتير PDF (Odoo)
------------------------
يعمل بأسلوبين احتياطيين (Best-Effort):
  1) استخراج الجداول (pdfplumber.extract_tables) — الحالة الأكثر شيوعاً.
  2) لو لم يوجد جدول، استخراج نصي سطراً بسطر مع تصفية العناوين/التذييلات.

مُختبَر فعلياً على فاتورة Odoo حقيقية (Picking/Stock Transfer) بأعمدة:
#, Code, Product, Quantity, Lot Date, Batch No., Box Lot No., Unit Price.
"""
import os
import re
import pdfplumber

# عمود اسم الصنف: طلب المستخدم صراحةً الاعتماد على عمود "Product" فقط
# (بدون "Description"/"Item"/"Name" التي قد تطابق أعمدة أخرى بالخطأ في
# بعض تخطيطات الفواتير).
COLUMN_HINTS = ["product"]

# كلمات ترشّح سطر الهيدر/الفوتر المتكرر ليُستبعد من كل صفحة (احتياطي نصي)
HEADER_FOOTER_HINTS = [
    "invoice", "فاتورة", "page", "صفحة", "total", "إجمالي",
    "odoo", "date", "تاريخ", "customer", "عميل",
]

# عناوين صفوف التذييل/الإجمالي التي تظهر أحياناً كصف أخير داخل الجدول
FOOTER_ROW_VALUES = {"total", "grand total", "subtotal", "إجمالي", "الإجمالي", "المجموع"}

# كلمات مرشحة لعنوان عمود "سعر الوحدة" و"الكمية" في جدول الفاتورة
PRICE_COLUMN_HINTS = ["unit price", "price", "سعر"]
QUANTITY_COLUMN_HINTS = ["quantity", "qty", "الكمية", "كمية"]


def _normalize_header_cell(cell) -> str:
    """
    يوحّد نص خلية العنوان: يستبدل أي سطر جديد بمسافة ويجمع المسافات الزائدة،
    لأن pdfplumber أحياناً يقسّم عنوان عمود من كلمتين على سطرين
    (مثال: "Unit\\nPrice") فيفوّت أي بحث مباشر عن "unit price".
    """
    if not cell:
        return ""
    text = str(cell).replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _find_column_index(header_row, hints):
    for idx, cell in enumerate(header_row):
        c = _normalize_header_cell(cell)
        if c and any(hint in c for hint in hints):
            return idx
    return None


def _find_item_column_index(header_row):
    return _find_column_index(header_row, COLUMN_HINTS)


def _find_price_column_index(header_row):
    return _find_column_index(header_row, PRICE_COLUMN_HINTS)


def _find_quantity_column_index(header_row):
    return _find_column_index(header_row, QUANTITY_COLUMN_HINTS)


def _parse_price(raw_value):
    if raw_value is None:
        return None
    s = str(raw_value).strip().replace(",", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None


def _parse_quantity(raw_value):
    if raw_value is None:
        return None
    s = str(raw_value).strip().replace(",", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    val = float(m.group(0))
    return int(val) if val == int(val) else val


def extract_item_rows_from_tables(pdf_path: str):
    """
    يستخرج صفوف الأصناف كاملة (الاسم من عمود Product + الكمية + سعر
    الوحدة كما وردا في الفاتورة) من أي جداول موجودة في الـ PDF.
    يعيد قائمة dict: {"name": ..., "quantity": ..., "unit_price": float|None}
    """
    rows_out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = table[0]
                col_idx = _find_item_column_index(header)
                if col_idx is None:
                    # لا يوجد عمود "Product" واضح - نتجاهل هذا الجدول
                    continue
                price_idx = _find_price_column_index(header)
                qty_idx = _find_quantity_column_index(header)
                for row in table[1:]:
                    if col_idx >= len(row) or not row[col_idx]:
                        continue
                    val = str(row[col_idx]).strip().replace("\n", " ")
                    val = re.sub(r"\s+", " ", val)
                    if not val:
                        continue
                    # استبعاد صف "الإجمالي" الذي يظهر أحياناً كصف أخير في الجدول
                    if val.strip().lower() in FOOTER_ROW_VALUES:
                        continue
                    unit_price = None
                    if price_idx is not None and price_idx < len(row):
                        unit_price = _parse_price(row[price_idx])
                    quantity = None
                    if qty_idx is not None and qty_idx < len(row):
                        quantity = _parse_quantity(row[qty_idx])
                    rows_out.append({"name": val, "quantity": quantity, "unit_price": unit_price})
    return rows_out


def extract_item_lines_from_tables(pdf_path: str):
    """نسخة متوافقة مع الإصدار السابق: أسماء الأصناف فقط (بدون السعر/الكمية)."""
    return [r["name"] for r in extract_item_rows_from_tables(pdf_path)]


def extract_item_lines_from_text(pdf_path: str):
    """احتياطي: استخراج نصي سطراً بسطر مع استبعاد الهيدر/الفوتر المتكرر."""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if any(h in line.lower() for h in HEADER_FOOTER_HINTS):
                    continue
                # نستبعد الأسطر التي هي أرقام/رموز فقط (مجاميع، تواريخ، إلخ)
                if not re.search(r"[A-Za-z\u0600-\u06FF]{3,}", line):
                    continue
                lines.append(line)
    return lines


def extract_item_lines(pdf_path: str):
    """
    يحاول الجداول أولاً (أدق)، ولو لم يعثر على شيء يرجع للاستخراج النصي.
    يعيد قائمة نصوص أسطر الأصناف كما وردت في الـ PDF (بدون أي تنظيف بعد).
    """
    lines = extract_item_lines_from_tables(pdf_path)
    if lines:
        return lines
    return extract_item_lines_from_text(pdf_path)


def extract_item_rows(pdf_path: str):
    """
    نفس extract_item_lines لكن يرجع أيضاً الكمية وسعر الوحدة كما وردا
    بالفاتورة. يعيد قائمة dict: {"name", "quantity", "unit_price"}.
    """
    rows = extract_item_rows_from_tables(pdf_path)
    if rows:
        return rows
    # احتياطي نصي: بدون سعر/كمية (الاستخراج النصي البسيط لا يفصل الأعمدة بدقة)
    return [{"name": line, "quantity": None, "unit_price": None}
            for line in extract_item_lines_from_text(pdf_path)]


def extract_invoice_header_text(pdf_path: str) -> str:
    """
    يستخرج نص رأس الفاتورة (كل ما قبل بداية جدول الأصناف) من الصفحة الأولى
    فقط — وهو المكان الذي يظهر فيه حقل "To:" باسم/كود الصيدلية المستلمة،
    لاستخدامه في تحديد اسم الصيدلية عبر pharmacy_directory.resolve_pharmacy_name.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return ""
            text = pdf.pages[0].extract_text() or ""
    except Exception:
        return ""

    # نقطع النص عند بداية جدول الأصناف (سطر العناوين # Code Product ...)
    m = re.search(r"#\s*Code\s*Product", text, flags=re.IGNORECASE)
    return text[:m.start()] if m else text


def find_pdf_files_in_folder(folder_path: str):
    """يرجع كل ملفات PDF داخل فولدر معيّن (بحث في المستوى الأعلى فقط)، مرتبة أبجدياً."""
    if not folder_path or not os.path.isdir(folder_path):
        return []
    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf")
    ]
    return sorted(files)
