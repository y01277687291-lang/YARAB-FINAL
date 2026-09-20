# -*- coding: utf-8 -*-
"""
المرحلة 4: التطابق التقريبي مع إخفاء المفاتيح (Index Normalization & Fuzzy Matching)
---------------------------------------------------------------------------------------
- عند تحميل قاعدة بيانات الأصناف (Excel/CSV) في الذاكرة:
    تُبنى "مفاتيح بحث" نظيفة خالية من عبارات مثل "(سعر جديد)"، "سعر جديد"،
    "س.ج"، "جديد" — دون فقدان النص الأصلي الكامل (الذي يُعاد استدعاؤه عند التطابق).
- الاسم أولاً دائماً (Name First / Price = Secondary Verification فقط):
  المطابقة عبر RapidFuzz (token_sort_ratio)، وحد التشابه (threshold) على
  الاسم إجباري وثابت ولا يُخفَّض أبداً بسبب السعر. السعر يتدخل فقط
  للترجيح بين مرشحين اتنين أو أكتر عدّوا حد الاسم فعلاً بالفعل — أبداً
  لتمرير مرشح ضعيف بالاسم لمجرد تطابق سعري (مشكلة حقيقية اتصلحت: كانت
  بتستبدل الصنف بصنف مختلف تماماً لتشابه السعر بالغلط).
- حارس أرقام/جرعات إجباري (راجع _extract_numbers أسفل) يمنع اعتماد صنف
  بجرعة/عبوة مختلفة عن المذكورة صراحة في نص الفاتورة، حتى لو تشابه
  النص لفظياً بنسبة عالية جداً.
- حتى عند الرفض (لا يوجد تطابق كافٍ بثقة)، تُرجع الدالة اسم "أقرب صنف"
  حقيقي موجود فعلاً في الشيت (closest_name) بدل أي تخمين حر، لأن الأداة
  ممنوع تطلع أي اسم من عندها أبداً — القرار النهائي للمستخدم فقط.
"""
import os
import re
import pandas as pd
from rapidfuzz import process, fuzz

# العبارات التي تُحذف من نص المطابقة فقط (تبقى في النص الأصلي المُعاد عند التطابق)
NOISE_PATTERNS = [
    r"\(?\s*سعر\s*جديد\s*\)?",
    r"\bس\s*\.\s*ج\b",
    r"\bجديد\b",
]
NOISE_REGEX = re.compile("|".join(NOISE_PATTERNS))

# حد أدنى لتشابه "أطول كلمة جوهرية" (بعد استبعاد كلمات الشكل/الجرعة
# العامة FILLER_WORDS) بين المرشح والمفتاح المطابق — أطول كلمة عادةً هي
# الاسم التجاري المميِّز الفعلي، مش أي كلمة وصفية عامة قصيرة قد تتكرر في
# أصناف مختلفة تماماً (مثال حقيقي: "مساج"/massage ظهرت في صنفين مختلفين
# كليةً، SPALAX وفريوميد، وكانت تخلي مقارنة "أفضل زوج" القديمة تمرّ غلط
# بنسبة 100%). حد 80 اتقاس فعلياً: كل حالات التطابق الصحيح المتحقَّق
# منها بتوصل 100% بالظبط (نفس الكلمة التجارية)، وحالات التشابه الحرفي
# العرضي بين براندات مختلفة بتوصل 63% كحد أقصى لوحظ.
BRAND_ANCHOR_THRESHOLD = 80.0

# كلمات صيدلانية عامة (شكل/جرعة/تعبئة) بتتكرر في مئات الأصناف المختلفة،
# فمينفعش الاعتماد عليها لتمييز هوية الصنف — بنستبعدها قبل مقارنة "الاسم
# الجوهري" بين المرشح والمفتاح المطابق (راجع _core_tokens وحارس الاسم
# التجاري بالأسفل).
FILLER_WORDS = {
    "مجم", "مجم/مل", "جم", "جرام", "مل", "مكجم", "وحدة", "وحدات",
    "قرص", "أقراص", "كبسول", "كبسولة", "كبسولات", "شراب", "كريم", "مرهم",
    "جل", "لوشن", "بخاخ", "بخاخة", "حقن", "أمبول", "أمبولة", "فيال",
    "محلول", "معلق", "معلقة", "لبوس", "نقط", "نقطة", "قطرة", "قطرات",
    "عبوة", "علبة", "شريط", "شرائط", "باكيت", "حبة", "حبوب", "فوار",
    "مضغوط", "سائل", "سعر", "جديد", "للأطفال", "للكبار",
}

# مجموعات "الشكل الصيدلي" (Form) — كلمتين ممكن يكونوا متشابهين نصياً جداً
# (زي "كريم" و"كريمة") بس شكل الصنف مختلف تماماً عملياً (قرص مش نفس كريم)،
# فده حارس منفصل عن حارس هوية الاسم: نمنع التطابق لو الفاتورة والمرشح
# بيذكروا شكلين واضحين ومختلفين (حتى لو الاسم التجاري نفسه اتطابق!).
FORM_GROUPS = {
    "solid_oral": {"قرص", "أقراص", "كبسول", "كبسولة", "كبسولات", "فوار", "مضغوط"},
    "liquid_oral": {"شراب", "معلق", "معلقة"},
    "topical": {"كريم", "مرهم", "جل", "لوشن"},
    "injectable": {"حقن", "أمبول", "أمبولة", "فيال"},
    "drops": {"نقط", "نقطة", "قطرة", "قطرات"},
    "suppository": {"لبوس"},
    "spray": {"بخاخ", "بخاخة"},
}
_WORD_TO_FORM_GROUP = {word: group for group, words in FORM_GROUPS.items() for word in words}


def _form_group(name: str):
    """يرجع اسم مجموعة الشكل الصيدلي المذكورة في النص، أو None لو مفيش
    كلمة شكل واضحة فيه."""
    for token in re.split(r"\s+", (name or "").strip()):
        group = _WORD_TO_FORM_GROUP.get(token)
        if group:
            return group
    return None

# لو سعر الفاتورة مطابق لسعر مرشح ضمن المرشحين المؤهلين اسمياً (بعد حد
# التشابه العادي)، نستخدمه للترجيح بينهم فقط — لا يُستخدم إطلاقاً لقبول
# مرشح لم يتخطَّ threshold أصلاً. الاسم دايماً أولاً وقبل أي حاجة
# (Name First / Price = Secondary Verification Only).
MAX_CANDIDATES = 8

DEFAULT_MATCH_THRESHOLD = 80.0

NUMBER_REGEX = re.compile(r"\d+")


def _extract_numbers(text: str) -> set:
    """يستخرج كل الأرقام (جرعة مجم، عدد شرائط، حجم عبوة...) من النص كمجموعة."""
    return set(NUMBER_REGEX.findall(text or ""))


def _core_tokens(name: str) -> list:
    """
    يرجع كلمات "هوية الصنف" الفعلية بعد استبعاد الأرقام وكلمات الشكل/الجرعة
    العامة (FILLER_WORDS). المقارنة بترتيب الكلمة الأولى بس كانت بتفشل لو
    اختلف ترتيب الصياغة بين المرشح والمفتاح (مثلاً "اقراص X" مقابل "X
    اقراص") — أول كلمة ساعتها بتبقى كلمة شكل عامة عند الطرفين فتتشابه
    بالغلط وتعدّي الحارس رغم اختلاف الدواء الحقيقي تماماً.
    """
    tokens = [t for t in re.split(r"\s+", (name or "").strip()) if t]
    core = [t for t in tokens if t not in FILLER_WORDS and not NUMBER_REGEX.fullmatch(t)]
    return core or tokens  # لو الاسم كله كلمات عامة/أرقام، استخدم الكلمات الأصلية بدل ما نرجع فاضي


def build_search_key(name: str) -> str:
    """ينظف اسم الصنف من عبارات الضوضاء التسويقية لبناء مفتاح بحث نظيف."""
    key = NOISE_REGEX.sub(" ", name or "")
    key = re.sub(r"\s+", " ", key).strip()
    return key


# مرادفات شائعة الاستخدام بالتبادل في شيتك الحقيقي لنفس نوع المنتج (اكتُشفت
# بالفحص المباشر: 165 صنف بكلمة "قطرة" مقابل 146 صنف بكلمة "نقط" لنفس
# الغرض تماماً، حسب مين كتب الصنف وقتها). نجرّب الاسم بكل الصيغ الممكنة
# عند المطابقة الضبابية بدل ما نعتمد صيغة واحدة بس.
SYNONYM_PAIRS = [
    ("نقط", "قطرة"),
    ("بخاخة", "بخاخ"),
]


def _name_variants(text: str):
    """يرجع كل الصيغ الممكنة للنص بعد تبديل كل زوج مرادفات موجود فيه."""
    variants = {text}
    for a, b in SYNONYM_PAIRS:
        current = list(variants)
        for v in current:
            if a in v:
                variants.add(v.replace(a, b))
            if b in v:
                variants.add(v.replace(b, a))
    return list(variants)


class ProductMatcher:
    """
    يحمّل قاعدة بيانات الأصناف العربية (كود / صنف / سعر) في الذاكرة عند بدء
    البرنامج، ويوفر مطابقة ضبابية سريعة (RapidFuzz) لاسم صنف مُعرَّب صوتياً.
    """

    def __init__(self, path: str = None):
        self.path = path
        self.df = pd.DataFrame(columns=["كود", "صنف", "سعر"])
        self._search_keys = []      # مفاتيح البحث النظيفة (بنفس ترتيب df)
        self._code_index = {}
        if path:
            self.load(path)

    def load(self, path: str):
        self.path = path
        if not path or not os.path.exists(path):
            self.df = pd.DataFrame(columns=["كود", "صنف", "سعر"])
            self._search_keys = []
            self._code_index = {}
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif ext == ".csv":
            df = pd.read_csv(path)
        else:
            raise ValueError(f"صيغة ملف غير مدعومة لقاعدة الأصناف: {ext}")

        # توحيد أسماء الأعمدة المتوقعة (يقبل تسميات عربية أو إنجليزية شائعة)
        rename_map = {}
        for col in df.columns:
            c = str(col).strip()
            if c in ("كود", "code", "Code", "CODE"):
                rename_map[col] = "كود"
            elif c in ("صنف", "الصنف", "name", "Name", "product", "Product"):
                rename_map[col] = "صنف"
            elif c in ("سعر", "السعر", "price", "Price"):
                rename_map[col] = "سعر"
        df = df.rename(columns=rename_map)
        if "صنف" not in df.columns:
            raise ValueError("ملف قاعدة الأصناف لا يحتوي على عمود 'صنف'.")

        df["صنف"] = df["صنف"].astype(str)
        self.df = df.reset_index(drop=True)
        self._search_keys = [build_search_key(n) for n in self.df["صنف"].tolist()]
        # فهرس كود -> رقم صف، لتفعيل بحث فوري بالكود (يستخدمه ملف الربط
        # اليدوي المرجعي reference_map.py) بدون أي مطابقة تقريبية إطلاقاً.
        if "كود" in self.df.columns:
            self._code_index = {str(c).strip(): i for i, c in enumerate(self.df["كود"].tolist())}
        else:
            self._code_index = {}

    def get_by_code(self, code: str):
        """
        يرجع dict {name, code, price} للصنف صاحب هذا الكود بالضبط من الشيت
        الحقيقي، أو None لو الكود مش موجود. تطابق تام بالكود فقط — بدون أي
        Fuzzy — يضمن رجوع النص الأصلي حرفياً 100% من الشيت دائماً.
        """
        idx = self._code_index.get(str(code).strip())
        if idx is None:
            return None
        row = self.df.iloc[idx]
        return {"name": row["صنف"], "code": row.get("كود", ""), "price": row.get("سعر", "")}

    def match(self, candidate_ar_name: str, threshold: float = DEFAULT_MATCH_THRESHOLD,
              invoice_price=None, price_tolerance: float = 1.0, price_bonus: float = 10.0):
        """
        يقارن الاسم العربي الناتج من محرك التعريب بكل مفاتيح البحث النظيفة.
        يرجع dict فيه: matched (bool), score (0-100), original_name,
        code, price, price_verified — أو matched=False لو لم يتجاوز أي
        مرشح نسبة العتبة (أو النسبة المخفَّضة بمساعدة السعر).

        أولوية مطلقة للتطابق التام: لو المرشح (بعد تنظيف عبارات الضوضاء)
        يطابق حرفياً أحد مفاتيح البحث، يُعتمد فوراً بثقة 100% دون المرور
        على المطابقة الضبابية إطلاقاً. هذا يمنع مشكلة حقيقية اكتُشفت أثناء
        الاختبار: بعض أسماء الأصناف تكون جزءاً نصياً من اسم صنف آخر مختلف
        تماماً في الشيت (مثال: "ريلاكس كريم" هي جزء من "ساج ريلاكس كريم")،
        وخوارزمية Fuzzy وحدها كانت أحياناً تعطي كليهما نفس الدرجة العليا
        فتختار الصنف الخطأ رغم وجود تطابق تام حقيقي متاح.

        الاسم أولاً دائماً (Name First): حد التشابه (threshold) على الاسم
        إجباري ولا يُخفَّض أبداً بسبب السعر. السعر بيتدخل بس للترجيح بين
        مرشحين عدّوا حد الاسم فعلاً (Price = Secondary Verification)، مع
        إبقاء حارس الاسم التجاري إجبارياً دايماً كخط دفاع أخير.
        """
        if not self._search_keys or not candidate_ar_name:
            return {"matched": False, "score": 0.0}

        # الأولوية القصوى: تطابق تام مع النص الأصلي الكامل كما هو في الشيت
        # (بدون أي تنظيف) — يحسم أي التباس بين صنفين لهما نفس الاسم بعد
        # حذف عبارة "سعر جديد" لكنهما فعلياً كودان مختلفان في الشيت (أصناف
        # قديمة أعيد تسعيرها). التطابق مع النص الكامل يضمن اختيار الصف
        # الصحيح فعلياً بدل أي صف آخر بنفس المفتاح المنظّف.
        for i, full_name in enumerate(self.df["صنف"].tolist()):
            if full_name == candidate_ar_name:
                row = self.df.iloc[i]
                return {
                    "matched": True,
                    "score": 100.0,
                    "original_name": row["صنف"],
                    "code": row.get("كود", ""),
                    "price": row.get("سعر", ""),
                    "price_verified": False,
                }

        candidate_key = build_search_key(candidate_ar_name)
        if candidate_key:
            for i, key in enumerate(self._search_keys):
                if key == candidate_key:
                    row = self.df.iloc[i]
                    return {
                        "matched": True,
                        "score": 100.0,
                        "original_name": row["صنف"],
                        "code": row.get("كود", ""),
                        "price": row.get("سعر", ""),
                        "price_verified": False,
                    }

        # لا يوجد تطابق تام: نلجأ للمطابقة الضبابية. نستخدم token_sort_ratio
        # (وليس token_set_ratio) لأن الأخيرة متساهلة جداً مع فروق الطول بين
        # النصوص (علاقات Subset)، وهو ما تسبب في نفس مشكلة الاختيار الخطأ
        # أعلاه حتى في الحالات غير التامة.
        # كمان نجرّب كل صيغ المرادفات الممكنة (SYNONYM_PAIRS) ونختار أفضل
        # نتيجة بينهم، عشان اختلاف تسمية نفس المنتج داخل شيتك نفسه (زي
        # "نقط" مقابل "قطرة") ميفوّتش تطابق حقيقي موجود فعلاً.
        #
        # الاسم أولاً (Name First): بنجمع أفضل MAX_CANDIDATES مرشح بالاسم
        # فقط من كل الصيغ، وأي مرشح ما وصلش threshold بالاسم بيتاستبعد
        # نهائياً هنا — قبل ما السعر يدخل في القصة خالص. السعر ميقدرش
        # يخلّي مرشح ضعيف بالاسم يعدي.
        candidate_scores = {}
        for variant in _name_variants(candidate_ar_name):
            for _choice, sc, i in process.extract(
                variant, self._search_keys, scorer=fuzz.token_sort_ratio, limit=MAX_CANDIDATES
            ):
                if i not in candidate_scores or sc > candidate_scores[i]:
                    candidate_scores[i] = sc

        if not candidate_scores:
            return {"matched": False, "score": 0.0}

        ranked = sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)
        best_idx, best_score = ranked[0]

        def _identity_guards_pass(row_name: str) -> bool:
            """المحك الموحَّد لهوية الصنف: نفس الأرقام (اتجاهياً) + نفس
            مجموعة الشكل الصيدلي (لو محدَّدة عند الطرفين) + كلمة جوهرية
            واحدة على الأقل شبه متطابقة (بعيداً عن كلمات الشكل/الجرعة
            العامة FILLER_WORDS). مُستخدَم مرتين: أولاً لإيجاد 'أقرب صنف
            حقيقي معقول' للعرض حتى في حالة الرفض، وثانياً لقرار الاعتماد
            التلقائي نفسه — بدل ما نعرض للمستخدم صنف مختلف تماماً بمجرد
            إنه رفع نسبة التشابه الخام بكلمات عامة مشتركة (مشكلة حقيقية
            اتبلّغ عنها: 'BEPRA' بيظهر مقترَح ليها 'ليبيتور' لمجرد اشتراكهم
            في '20 مجم 28 قرص')."""
            candidate_numbers = _extract_numbers(candidate_ar_name)
            matched_numbers = _extract_numbers(row_name)
            if candidate_numbers and (candidate_numbers - matched_numbers):
                return False
            candidate_form = _form_group(candidate_ar_name)
            matched_form = _form_group(row_name)
            if candidate_form and matched_form and candidate_form != matched_form:
                return False
            candidate_core = _core_tokens(candidate_ar_name)
            matched_core = _core_tokens(build_search_key(row_name))
            if candidate_core and matched_core:
                # نقارن أطول كلمة جوهرية من كل طرف بس (غالباً هي الاسم
                # التجاري المميِّز الفعلي) — مش "أفضل زوج" من كل الكلمات:
                # مقارنة "أفضل زوج" كانت بتفشل لما يشترك الاسمين في كلمة
                # وصفية عامة قصيرة (زي "مساج"/"massage") موجودة فعلاً في
                # صنفين مختلفين تماماً، فتدّي 100% تشابه على كلمة غير
                # مميِّزة أصلاً وتخلي الحارس يمرّ غلط رغم اختلاف البراند
                # الحقيقي (مثال حقيقي: SPALAX مقابل فريوميد، الاتنين
                # فيهم "مساج" لكنهم دواءان مختلفان تماماً).
                candidate_anchor = max(candidate_core, key=len)
                matched_anchor = max(matched_core, key=len)
                if fuzz.ratio(candidate_anchor, matched_anchor) < BRAND_ANCHOR_THRESHOLD:
                    return False
            return True

        # "أقرب صنف حقيقي" للعرض عند الرفض: أول مرشح (بالترتيب التنازلي
        # حسب نسبة التشابه الخام) يعدّي محك الهوية أعلاه فعلاً — مش أول
        # مرشح بالنسبة الخام بس، عشان ميظهرش صنف مختلف تماماً كـ"اقتراح"
        # لمجرد تشابه كلمات عامة. لو محدش من كل المرشحين عدّى المحك، منعرضش
        # أي اسم محدَّد خالص (نسيب pipeline.py يرجع للتعريب الصوتي الخام
        # كحل أخير، بدل اسم صنف حقيقي لكنه مضلِّل تماماً).
        closest_info = {}
        for cand_idx, _cand_score in ranked:
            cand_row = self.df.iloc[cand_idx]
            if _identity_guards_pass(cand_row["صنف"]):
                closest_info = {
                    "closest_name": cand_row["صنف"],
                    "closest_code": cand_row.get("كود", ""),
                    "closest_price": cand_row.get("سعر", ""),
                }
                break

        # حد الاسم إجباري وثابت (Name First) — السعر ممنوع يخفّضه إطلاقاً.
        # المرشحين اللي وصلوا الحد ده بس هم المؤهلين، والسعر بعد كده بيرجّح
        # بينهم فقط (Price = Secondary Verification)، مش بيقبل حد فشل بالاسم.
        qualified = [(i, sc) for i, sc in ranked if sc >= threshold]
        if not qualified:
            return {"matched": False, "score": best_score, **closest_info}

        def _price_matches(row_idx) -> bool:
            if invoice_price is None:
                return False
            try:
                db_price = float(self.df.iloc[row_idx].get("سعر"))
                return abs(db_price - float(invoice_price)) <= price_tolerance
            except (TypeError, ValueError):
                return False

        # الترجيح بالسعر: بس بين المرشحين اللي عدّوا حد الاسم أصلاً، ولمصلحة
        # أعلى نسبة اسم من بينهم لو أكتر من مرشح سعره مطابق (نادر، لكن
        # ممكن يحصل مع أصناف بنفس السعر بالظبط).
        price_matched_qualified = [c for c in qualified if _price_matches(c[0])]
        idx, score = (max(price_matched_qualified, key=lambda c: c[1])
                      if price_matched_qualified else qualified[0])

        chosen_row = self.df.iloc[idx]
        if not _identity_guards_pass(chosen_row["صنف"]):
            return {"matched": False, "score": score, **closest_info}

        price_verified = _price_matches(idx)

        if price_verified:
            score = min(100.0, score + price_bonus)

        row = self.df.iloc[idx]
        return {
            "matched": True,
            "score": score,
            "original_name": row["صنف"],
            "code": row.get("كود", ""),
            "price": row.get("سعر", ""),
            "price_verified": price_verified,
        }

    def __len__(self):
        return len(self.df)
