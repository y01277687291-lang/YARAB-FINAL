# -*- coding: utf-8 -*-
"""
المرحلة 2: القاموس المعجمي المباشر (Direct Lexical Mapping)
-------------------------------------------------------------
يمنع تعريب الكلمات الوظيفية نطقياً (مثل Tab, Cap, Adult ...) ويستبدلها
بمعناها العربي الصيدلي المباشر فوراً، قبل دخول محرك التعريب الصوتي.

المصدر: وثيقة التوصيف + ملف "New Text Document.txt" المرفق من المستخدم
(يحتوي على توسعات: النكهات، طرق الحقن، Senior، Comp/Co، Cup، Cough ...).
"""
import re

# كل مفتاح يُكتب lowercase بدون مسافات زائدة. القيمة قد تحوي "/" فاصلة بين
# مرادفين عربيين كما وردت في المصدر حرفياً.
LEXICAL_MAP = {
    # --- أ. الأشكال الصيدلية (Dosage Forms) ---
    "tab": "أقراص", "tablet": "أقراص", "tabs": "أقراص",
    "cap": "كبسول", "capsule": "كبسول", "caps": "كبسول",
    "syr": "شراب", "syrup": "شراب",
    "amp": "أمبول", "ampoule": "أمبول",
    "vial": "فيال", "vials": "فيال",
    "sachet": "أكياس", "sachets": "أكياس", "sach": "أكياس",
    "susp": "معلق", "sosp": "معلق", "suspension": "معلق",
    "cream": "كريم", "crm": "كريم",
    "oint": "مرهم", "ointment": "مرهم",
    "gel": "جل",
    "drop": "نقط", "drops": "نقط", "drp": "نقط",
    "supp": "لبوس", "suppository": "لبوس",
    "eff": "فوار", "effervescent": "فوار",
    "spray": "بخاخ", "spr": "بخاخ",

    # --- ب. الأعمار والتطبيقات المستهدفة (Target Groups) ---
    "infant": "رضع", "infants": "رضع",
    "baby": "أطفال / رضع",
    "pediatric": "أطفال", "pedia": "أطفال", "ped": "أطفال",
    "children": "أطفال",
    "adult": "بالغين", "adults": "بالغين",
    "junior": "ناشئين / أطفال",
    "senior": "كبار السن",
    "vaginal": "مهبلي", "vag": "مهبلي",
    "rectal": "شرجي", "anal": "شرجي",

    # --- ج. المستلزمات الطبية والأصناف الخاصة (Medical Supplies & Misc) ---
    "soap": "صابون",
    "shampoo": "شامبو",
    "lotion": "لوشن",
    "wipes": "مناديل مبللة",
    "syringe": "سرنجة", "syrg": "سرنجة",
    "cannula": "كانيولا",
    "cotton": "قطن",
    "alcohol": "كحول",
    "gauze": "شاش",
    "bandage": "رباط ضاغط",
    "strip": "شرائط", "strips": "شرائط",
    "lancet": "شكاكات", "lancets": "شكاكات",
    "sugar free": "خالي من السكر", "sf": "خالي من السكر",

    # --- د. توسعات ملف "New Text Document.txt" ---
    "patch": "لصقة", "patches": "لصقة",
    "mouthwash": "مضمضة / غسول فم",
    "toothpaste": "معجون أسنان",
    "orange": "برتقال",
    "lemon": "ليمون",
    "strawberry": "فراولة",
    "mint": "نعناع",
    "inhaler": "بخاخ / استنشاق", "inh": "بخاخ / استنشاق",
    "nebulizer": "جلسات / نيبولايزر", "neb": "جلسات / نيبولايزر",
    "infusion": "تسقيط / محلول", "inf": "تسقيط / محلول",
    "injection": "حقن / حقنة", "inj": "حقن / حقنة",
    "iv": "وريد (وريدي)",
    "im": "عضل (عضلي)",
    "sc": "تحت الجلد",
    "comp": "مركب", "compound": "مركب", "complex": "مركب",
    "co": "مركب",
    "cup": "كوب", "measuring cup": "كوب (أو كوب معيار)",
    "cough": "كحة / للسعال",

    # --- هـ. إضافات مؤكدة من فحص شيت الأصناف الحقيقي مباشرة ---
    "milk": "لبن",                 # الشيت بيستخدم "لبن هيرو" وليس "ميلك هيرو"
    "evohaler": "بخاخة",           # نوع بخاخ استنشاق (مؤكد من "فليكسوتيد ... بخاخه")
    "dose": "جرعة",                # مؤكد من "فليكسوتيد 250 مجم 60 جرعة"
}

# مفاتيح مرتبة حسب عدد الكلمات تنازلياً (لمطابقة العبارات المركبة أولاً
# مثل "sugar free" أو "measuring cup" قبل الكلمات المفردة)
_MULTI_WORD_KEYS = sorted(
    (k for k in LEXICAL_MAP if " " in k),
    key=lambda k: len(k.split()),
    reverse=True,
)
_MAX_PHRASE_WORDS = max((len(k.split()) for k in _MULTI_WORD_KEYS), default=1)


from .transliteration import transliterate_word


def _normalize_token(token: str) -> str:
    return re.sub(r"[^a-z]", "", token.lower())


def apply_lexical(text: str):
    """
    يطبّق القاموس المعجمي على النص (بعد التنظيف)، مع مطابقة أطول عبارة أولاً
    (longest match first) على مستوى الكلمات المتتالية.

    يعيد قائمة عناصر بنفس ترتيب النص الأصلي، كل عنصر إما:
      ("ar", "النص العربي المباشر")   -> صنف/فئة تمت ترجمتها مباشرة
      ("en", "الكلمة الإنجليزية")     -> اسم تجاري صافٍ يُرسل لمحرك التعريب الصوتي

    حالة خاصة: بادئة "EL" (أداة التعريف "ال" الشائعة جداً في أسماء الأدوية
    والشركات المصرية مثل El Nile, El Ezaby) — بدل ما تتعرّب حرفاً بحرف
    وتطلع نص غريب (EL -> "يل")، بندمجها مباشرة مع الكلمة اللي بعدها كـ"ال"
    + تعريب الكلمة التالية بدون مسافة (زي "النيل" مش "يل نيل").
    """
    words = text.split()
    output = []
    i = 0
    n = len(words)
    while i < n:
        # حالة بادئة "EL" + كلمة تالية
        if _normalize_token(words[i]) == "el" and i + 1 < n:
            next_word_ar = transliterate_word(words[i + 1])
            output.append(("ar", "ال" + next_word_ar))
            i += 2
            continue

        matched = False
        max_span = min(_MAX_PHRASE_WORDS, n - i)
        for span in range(max_span, 1, -1):
            phrase = " ".join(_normalize_token(w) for w in words[i:i + span])
            if phrase in LEXICAL_MAP:
                output.append(("ar", LEXICAL_MAP[phrase]))
                i += span
                matched = True
                break
        if matched:
            continue
        key = _normalize_token(words[i])
        if key in LEXICAL_MAP:
            output.append(("ar", LEXICAL_MAP[key]))
        else:
            output.append(("en", words[i]))
        i += 1
    return output
