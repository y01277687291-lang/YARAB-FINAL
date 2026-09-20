# -*- coding: utf-8 -*-
"""
المرحلة 1: الفلترة والتنظيف الأول (Pre-cleaning & Stripping)
-------------------------------------------------------------
تنظف سطر الصنف من:
  - الكلمات الإدارية (Offer, Free, Promo, Sample, Pack ...)
  - التركيزات والأرقام (mg / ml / g / iu) وتخزنها جانباً لإعادة إلحاقها
    بالنص العربي بعد التعريب دون أن تمر هي نفسها على محرك التعريب.
"""
import re
from dataclasses import dataclass, field

# الكلمات الإدارية الواجب حذفها تلقائياً
ADMIN_WORDS = [
    "offer", "free", "promo", "sample", "pack", "pck",
    "box", "piece", "pcs", "item",
    # "eye" في سياق eye drop/eye ointment: لاحظنا في شيتك الحقيقي إن
    # القطرات بتتكتب "قطرة" بس بدون كلمة "عين" منفصلة غالباً، فحذفها هنا
    # أدق من ترجمتها لكلمة مستقلة تزوّد نص المقارنة من غير داعي.
    "eye",
    "dispersible",
]

# اختصارات شائعة بنقاط بين الحروف (F.C. = Film Coated، N.P = علامة سعر/تعبئة
# في بعض الفواتير) — لاحظنا في فواتير حقيقية إنها كانت بتتحوّل لحروف عربية
# بلا معنى (زي "فك" أو "نب") لأنها مش أسماء أصناف حقيقية أصلاً، فبنشيلها
# كضوضاء بدل ما تدخل محرك التعريب. النقاط بينها تمنع مطابقتها ككلمات
# عادية، فبنستخدم Regex مخصص ليها.
NOISE_ABBREV_PATTERNS = [
    r"\bf\.?\s*c\.?\b",   # F.C. / FC (Film Coated)
    r"\bn\.?\s*p\.?\b",   # N.P / NP
]
NOISE_ABBREV_REGEX = re.compile("|".join(NOISE_ABBREV_PATTERNS), flags=re.IGNORECASE)

# أنماط عزل التركيزات/الأرقام والوحدات (مرتبة من الأطول للأقصر لتفادي القطع الخاطئ)
UNIT_PATTERNS = [
    r"\d+(\.\d+)?\s*mcg",
    r"\d+(\.\d+)?\s*iu",
    r"\d+(\.\d+)?\s*mg",
    r"\d+(\.\d+)?\s*ml",
    r"\d+(\.\d+)?\s*gm",
    r"\d+(\.\d+)?\s*g\b",
    r"\d+(\.\d+)?\s*%",
]
UNIT_REGEX = re.compile("|".join(UNIT_PATTERNS), flags=re.IGNORECASE)

# وحدات القياس بالعربي لإعادة كتابة الرقم عند الإلحاق
UNIT_AR_MAP = [
    (re.compile(r"mcg", re.IGNORECASE), "ميكروجرام"),
    (re.compile(r"iu", re.IGNORECASE), "وحدة دولية"),
    (re.compile(r"mg", re.IGNORECASE), "مجم"),
    (re.compile(r"ml", re.IGNORECASE), "مل"),
    (re.compile(r"gm", re.IGNORECASE), "جم"),
    (re.compile(r"g\b", re.IGNORECASE), "جم"),
]


@dataclass
class CleanResult:
    """ناتج مرحلة التنظيف: النص المتبقي (اسم تجاري صافي) + القيم المستخرجة جانباً."""
    core_text: str
    extracted_units: list = field(default_factory=list)   # كما وردت بالإنجليزية، مثل "500mg"
    extracted_units_ar: list = field(default_factory=list)  # مترجمة، مثل "500 مجم"
    original_text: str = ""


def _arabicize_unit_token(token: str) -> str:
    """يحوّل رمز الوحدة الإنجليزي داخل الرقم المستخرج إلى مقابله العربي (500mg -> 500 مجم)."""
    out = token.strip()
    for pattern, ar in UNIT_AR_MAP:
        if pattern.search(out):
            number = re.search(r"\d+(\.\d+)?", out)
            num_str = number.group(0) if number else ""
            return f"{num_str} {ar}".strip()
    return out


def clean_line(raw_text: str) -> CleanResult:
    """
    ينظف سطر صنف واحد من الفاتورة:
      1) يحذف الكلمات الإدارية.
      2) يعزل الأرقام/التركيزات (mg/ml/g/iu/%) ويخزنها جانباً.
      3) يوحّد المسافات الزائدة.
    """
    original = raw_text
    text = raw_text.strip()

    # توحيد الترميز ومعالجة الرموز الغريبة الشائعة قبل أي شيء
    text = text.replace("\u00a0", " ")  # non-breaking space
    text = re.sub(r"\s+", " ", text).strip()

    # استخراج التركيزات/الأرقام أولاً (قبل حذف الكلمات الإدارية حتى لا تتداخل)
    extracted_units = []
    extracted_units_ar = []

    def _pull(match):
        token = match.group(0)
        extracted_units.append(token.strip())
        extracted_units_ar.append(_arabicize_unit_token(token))
        return " "

    text = UNIT_REGEX.sub(_pull, text)

    # حذف الاختصارات المنقّطة الشائعة (F.C. / N.P) قبل أي معالجة تانية
    text = NOISE_ABBREV_REGEX.sub(" ", text)
    # تنظيف أي نقطة يتيمة متبقية (مش جزء من رقم عشري) كأثر جانبي لحذف
    # الاختصارات أعلاه
    text = re.sub(r"(?<!\d)\.(?!\d)", " ", text)

    # حذف الكلمات الإدارية ككلمات مستقلة (word boundaries) بدون حساسية لحالة الأحرف
    for word in ADMIN_WORDS:
        text = re.sub(rf"\b{re.escape(word)}\b", " ", text, flags=re.IGNORECASE)

    # تنظيف نهائي للمسافات والفواصل المتبقية
    text = re.sub(r"[\-_/,]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return CleanResult(
        core_text=text,
        extracted_units=extracted_units,
        extracted_units_ar=extracted_units_ar,
        original_text=original,
    )


def is_arabic_text(text: str) -> bool:
    """
    يكتشف إن كان السطر مكتوباً بالعربية أصلاً في Odoo (حالات "الشواذ")
    فيتم حينها تخطي محركي القاموس المعجمي والتعريب الصوتي (المرحلتين 2 و3)
    والذهاب مباشرة لمرحلة المطابقة الضبابية على قاعدة البيانات.
    """
    if not text:
        return False
    arabic_chars = re.findall(r"[\u0600-\u06FF]", text)
    latin_chars = re.findall(r"[A-Za-z]", text)
    return len(arabic_chars) > len(latin_chars)
