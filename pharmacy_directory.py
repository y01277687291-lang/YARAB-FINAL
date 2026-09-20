# -*- coding: utf-8 -*-
"""
دليل أكواد الصيدليات (Pharmacy Directory)
-------------------------------------------------------------------
يربط كود الصيدلية كما يظهر في حقل "To:" بفواتير Odoo (مثال: "ALN/Alanwar")
باسمها العربي الحقيقي المعروف لدى المستخدم (مثال: "صيدلية الانور").

المصدر: قائمة أكواد أرسلها المستخدم يدوياً. أضف أي صيدلية جديدة هنا بنفس
الصيغة (الكود كما يظهر في الفاتورة، الاسم العربي).
"""
import re
from rapidfuzz import process, fuzz

# (الكود كما يظهر في فاتورة Odoo، الاسم العربي الحقيقي للصيدلية)
PHARMACY_DIRECTORY = [
    ("ALN/Alanwar", "صيدلية الانور"),
    ("AMRAY/Amry", "صيدلية عبد الرحمن ابو حادى"),
    ("btm/Stock", "صيدلية ولاء الدوانسي"),
    ("El-da/El-dahriari", "صيدلية الحسيني الغرياني"),
    ("El-Su/El-Sultan Hussein", "صيدلية السلطان حسين"),
    ("El-Wa/Elwatanya", "صيدلية احمد هويدي"),
    ("GAMAL/GAMAL/Stock", "صيدلية تامر السلاب"),
    ("Gleem/Gleem", "صيدلية هالة سامي"),
    ("Joini/Joinidis-Roshdy", "صيدلية جوانيدس"),
    ("K21/21", "صيدلية دينا الشامي"),
    ("Korni/Kornish", "صيدلية عماد الدين على"),
    ("Loran/Loran", "صيدلية السراي"),
    ("Mosta/Mostafa Kamel", "صيدلية احمد صلاح"),
    ("NAQL/Stock", "صيدلية ريم عبد الرحمن"),
    ("NKH", "صيدلية امين جمال"),
    ("nwr/Stock", "صيدلية دمحمد مصطى نوار"),
    ("Rabaa/Rabaa Cairo Team", "صيدلية الجمعية التعاونية للعاملين بجمعية"),
    ("San-S/San-Stefano", "صيدلية المها"),
    ("SMOH1/5mouha", "صيدلية محمد هويدي"),
    ("Tahri/Stock", "صيدلية التحرير"),
    ("VENOS/Stock", "صيدلية فينوس"),
    ("WAPOR/Stock", "صيدلية احمد علاء احمد"),
]

FUZZY_MATCH_THRESHOLD = 75.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


# مطابقة الكود الكامل كما هو (أدق مطابقة)
_FULL_CODE_MAP = {_norm(code): name for code, name in PHARMACY_DIRECTORY}

# مطابقة الجزء الأول قبل أول "/" فقط (مفيد لو ظهر في الفاتورة بدون الجزء
# الثاني، أو بترتيب معكوس بسبب مشاكل استخراج النص ثنائي الاتجاه RTL/LTR)
_SHORT_CODE_COUNTS = {}
for code, name in PHARMACY_DIRECTORY:
    short = _norm(code.split("/")[0])
    _SHORT_CODE_COUNTS.setdefault(short, set()).add(name)
# لا نعتمد الكود المختصر كمفتاح مطابقة إلا لو كان فريداً (يخص صيدلية واحدة)
_SHORT_CODE_MAP = {
    short: next(iter(names))
    for short, names in _SHORT_CODE_COUNTS.items()
    if len(names) == 1
}

# أطول الأكواد أولاً حتى لا يطابق كود قصير جزءاً من كود أطول بالخطأ
_FULL_CODES_SORTED = sorted(PHARMACY_DIRECTORY, key=lambda pair: len(pair[0]), reverse=True)


def _extract_candidate_token(text: str) -> str:
    """
    يحاول عزل أقرب نص يشبه كود صيدلية (حروف/أرقام مفصولة بـ / أو -) من حقل
    "To:" في رأس الفاتورة، لعرضه كما هو لو ملقناش اسم مقابل معروف.
    """
    to_idx = text.lower().find("to:")
    region = text[to_idx:to_idx + 250] if to_idx != -1 else text
    m = re.search(r"[A-Za-z][A-Za-z0-9\-]*(?:/[A-Za-z0-9\-]+){1,2}", region)
    return m.group(0) if m else ""


def resolve_pharmacy_name(invoice_header_text: str):
    """
    يحدد اسم الصيدلية العربي بناءً على النص الخام لرأس الفاتورة (يحتوي على
    حقل "To:"). يرجع (الاسم_المعروض, matched: bool).
    لو معرفناش نطابقه بصيدلية معروفة، نرجع أقرب نص كود لقيناه في الفاتورة
    كما هو (matched=False) بدل ما نرجع فراغ.
    """
    text = invoice_header_text or ""
    if not text.strip():
        return "", False

    # 1) مطابقة الكود الكامل كنص فرعي داخل رأس الفاتورة (الأدق)
    for code, name in _FULL_CODES_SORTED:
        if _norm(code) in text.lower():
            return name, True

    # 2) مطابقة الكود المختصر (الجزء الأول) كحد كلمة كاملة
    for short, name in _SHORT_CODE_MAP.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(short)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            return name, True

    # 3) مطابقة تقريبية (Fuzzy) لأقرب نص كود موجود فعلياً في الفاتورة
    candidate = _extract_candidate_token(text)
    if candidate:
        best = process.extractOne(
            candidate, [code for code, _ in PHARMACY_DIRECTORY], scorer=fuzz.token_sort_ratio
        )
        if best and best[1] >= FUZZY_MATCH_THRESHOLD:
            matched_code = best[0]
            return _FULL_CODE_MAP[_norm(matched_code)], True

    # 4) لا يوجد تطابق: أظهر النص كما هو في الفاتورة (كود خام أو لا شيء)
    return candidate or "", False
