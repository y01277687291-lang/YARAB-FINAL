# -*- coding: utf-8 -*-
"""
محرك تشغيل خط الأنابيب الكامل (Pipeline Engine)
---------------------------------------------------
يربط المراحل الخمس بالترتيب الصارم المطلوب في الوثيقة:

  الاستثناءات (أولوية مطلقة) -> التنظيف -> القاموس المعجمي
      -> التعريب الصوتي -> المطابقة الضبابية -> تحقق إضافي بالسعر

ويحسب "لون الثقة" النهائي:
  green  (>90%)   : من ملف الاستثناءات أو تطابق شبه تام مع قاعدة البيانات
  yellow (70-89%)  : تعريب + تقريب Fuzzy يحتاج مراجعة بالعين
  red    (<70%)    : ثقة غير كافية للاعتماد التلقائي — الاسم المعروض يبقى
                     "أقرب صنف" حقيقي من شيت فارما تشين نفسه (مش تخمين حر
                     من محرك التعريب) طالما فيه ولو مرشح واحد بالشيت.

كل النتائج بترجع أيضاً علم ignored=True/False لو الصنف (أو مشابه له جداً)
مُستبعد مسبقاً من قائمة Blacklist (راجع ignored_items_manager.py).
"""
from dataclasses import dataclass
from typing import Optional

from .cleaner import clean_line, is_arabic_text
from .lexical_dict import apply_lexical
from .transliteration import transliterate_word
from .matcher import ProductMatcher
from .exceptions_manager import ExceptionsManager
from .ignored_items_manager import IgnoredItemsManager
from .reference_map import ReferenceMapManager
from .controlled_items import ControlledItemsManager

GREEN, YELLOW, RED = "green", "yellow", "red"


@dataclass
class LineResult:
    original_text: str
    suggested_arabic: str
    score: float
    color: str
    source: str                 # "exception" | "reference_map" | "database" | "database_low_confidence" | "unmatched"
    matched_code: Optional[str] = None
    matched_price: Optional[str] = None
    invoice_price: Optional[float] = None
    quantity: Optional[float] = None
    price_verified: bool = False
    ignored: bool = False       # True لو الصنف ده (أو مشابه له) مُستبعد مسبقاً (Blacklist)
    controlled: bool = False    # True لو الصنف من "الأصناف المهمة" (أدوية جدول) - راجع engine/controlled_items.py
    debug_core_text: str = ""
    debug_transliterated: str = ""


def _confidence_color(score: float) -> str:
    if score > 90:
        return GREEN
    if score >= 70:
        return YELLOW
    return RED


class PharmaPipeline:
    def __init__(self, products_path: str = None, exceptions_path: str = None,
                 match_threshold: float = 80.0, price_tolerance: float = 1.0,
                 price_bonus: float = 10.0, ignored_path: str = None, reference_map_path: str = None,
                 controlled_items_path: str = None, cloud=None):
        self.cloud = cloud
        self.matcher = ProductMatcher(products_path)
        self.exceptions = ExceptionsManager(exceptions_path, cloud=cloud) if exceptions_path else None
        self.ignored = IgnoredItemsManager(ignored_path, cloud=cloud) if ignored_path else None
        self.reference_map = ReferenceMapManager(reference_map_path) if reference_map_path else ReferenceMapManager()
        self.controlled = ControlledItemsManager(controlled_items_path) if controlled_items_path else ControlledItemsManager()
        self.match_threshold = match_threshold
        self.price_tolerance = price_tolerance
        self.price_bonus = price_bonus

    # ---- إعادة تحميل مصادر البيانات (تُستخدم من شاشة الإعدادات) ----
    def reload_products(self, path: str):
        self.matcher.load(path)

    def reload_exceptions(self, path: str):
        self.exceptions = ExceptionsManager(path, cloud=self.cloud)

    def reload_ignored(self, path: str):
        self.ignored = IgnoredItemsManager(path, cloud=self.cloud)

    def reload_reference_map(self, path: str):
        self.reference_map = ReferenceMapManager(path)

    def reload_controlled_items(self, path: str):
        self.controlled = ControlledItemsManager(path)

    def save_exception(self, raw_text: str, mapped_arabic: str):
        if self.exceptions is not None:
            self.exceptions.add_exception(raw_text, mapped_arabic)

    def add_ignored(self, raw_text: str, matched_name: str = None):
        """يضيف الصنف لقائمة الاستبعاد (Blacklist) — نص الفاتورة الأصلي
        والاسم المطابَق من الشيت معاً لو متاح، عشان أعلى فرصة تعرّف تلقائي
        على نفس الصنف في فواتير قادمة مهما اختلفت صياغته في Odoo."""
        if self.ignored is None:
            return
        self.ignored.add(raw_text)
        if matched_name and matched_name.strip() != (raw_text or "").strip():
            self.ignored.add(matched_name)

    def _is_ignored(self, *texts) -> bool:
        if self.ignored is None:
            return False
        return any(self.ignored.is_ignored(t) for t in texts if t)

    # ---- المعالجة الأساسية لسطر واحد ----
    def process_line(self, raw_text: str, invoice_price: Optional[float] = None,
                      quantity: Optional[float] = None) -> LineResult:
        result = self._process_line_inner(raw_text, invoice_price=invoice_price, quantity=quantity)
        # فحص "الأصناف المهمة" (أدوية جدول) بمعزل تماماً عن مصدر النتيجة
        # (استثناء/شيت مرجعي/قاعدة بيانات/غير مطابق) - أي مسار وصل بيه
        # الاسم النهائي، لو طابق صنف من القائمة المهمة، لازم يتعلّم. حتى
        # لو الصنف "غير مطابق" (مفيش اسم معروض خالص)، لسه بنفحص تخمين
        # المحرك الداخلي (debug_transliterated) للتنبيه الأمني فقط — مش
        # لعرضه كاسم مقترَح، بس عشان دواء جدول ميفوّتش من غير تنبيه حتى
        # لو مش موجود بالشيت.
        result.controlled = (
            self.controlled.is_controlled(result.suggested_arabic)
            or self.controlled.is_controlled(result.debug_transliterated)
        )
        return result

    def _process_line_inner(self, raw_text: str, invoice_price: Optional[float] = None,
                             quantity: Optional[float] = None) -> LineResult:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            return LineResult(raw_text, "", 0.0, RED, "unmatched",
                               invoice_price=invoice_price, quantity=quantity)

        # المرحلة 5 (أولوية مطلقة): البحث في ملف الاستثناءات أولاً
        if self.exceptions is not None:
            mapped = self.exceptions.lookup(raw_text)
            if mapped:
                return LineResult(
                    original_text=raw_text,
                    suggested_arabic=mapped,
                    score=100.0,
                    color=GREEN,
                    source="exception",
                    invoice_price=invoice_price,
                    quantity=quantity,
                    ignored=self._is_ignored(raw_text, mapped),
                )

        # المرحلة 1 (أولوية قصوى بعد الاستثناءات): الشيت المرجعي الجاهز
        # (English_Arabic_Map.xlsx) — لو الاسم الإنجليزي زي ما هو من Odoo
        # موجود فيه، نجيب الكود المرتبط وناخد الاسم/السعر حرفياً 100% من
        # شيت فارما تشين الحقيقي (products.xlsx) عن طريق الكود مباشرة —
        # بدون أي تعريب صوتي أو Fuzzy matching إطلاقاً لهذا الصنف.
        ref_code = self.reference_map.lookup_code(raw_text)
        if ref_code:
            ref_row = self.matcher.get_by_code(ref_code)
            if ref_row:
                return LineResult(
                    original_text=raw_text,
                    suggested_arabic=ref_row["name"],
                    score=98.0,
                    color=GREEN,
                    source="reference_map",
                    matched_code=str(ref_row.get("code", "")),
                    matched_price=str(ref_row.get("price", "")),
                    invoice_price=invoice_price,
                    quantity=quantity,
                    price_verified=True,
                    ignored=self._is_ignored(raw_text, ref_row["name"]),
                )

        # المرحلة 1: التنظيف الأولي + عزل التركيزات
        clean = clean_line(raw_text)
        units_ar = " ".join(clean.extracted_units_ar)

        # اكتشاف الحالات "الشاذة": سطر مكتوب بالعربية أصلاً في Odoo
        # (مثل أسماء ألبان الأطفال والصابونات) -> تخطي المعجم والتعريب
        # والذهاب مباشرة للمطابقة الضبابية على قاعدة البيانات.
        if is_arabic_text(clean.core_text):
            transliterated_text = clean.core_text
        else:
            # المرحلة 2: القاموس المعجمي المباشر
            tokens = apply_lexical(clean.core_text)
            # المرحلة 3: التعريب الصوتي (لما تبقى فقط من كلمات إنجليزية)
            parts = []
            for kind, value in tokens:
                if kind == "ar":
                    parts.append(value)
                else:
                    parts.append(transliterate_word(value))
            transliterated_text = " ".join(p for p in parts if p)

        candidate_full = " ".join(x for x in [transliterated_text, units_ar] if x).strip()

        # المرحلة 4: المطابقة الضبابية مع قاعدة الأصناف (تشمل الوحدات المعاد
        # إلحاقها) — تحقق السعر ومساعدته على قبول تطابق أضعف نصياً يتم
        # داخل matcher.match() نفسها الآن.
        match = self.matcher.match(
            candidate_full,
            threshold=self.match_threshold,
            invoice_price=invoice_price,
            price_tolerance=self.price_tolerance,
            price_bonus=self.price_bonus,
        )

        if match.get("matched"):
            # سقف 98% لأي تطابق آلي (Fuzzy) — 100% محجوزة حصرياً للأصناف
            # اللي اتأكّدت يدوياً فعلاً (زر ✅ تأكيد -> استثناء) أو الشيت
            # المرجعي المعتمد (Step A)، عشان "100%" تفضل معناها فعلاً "متأكَّد
            # منه بشرياً"، مش مجرد تخمين خوارزمي عالي الثقة.
            score = min(float(match["score"]), 98.0)
            return LineResult(
                original_text=raw_text,
                suggested_arabic=match["original_name"],
                score=score,
                color=_confidence_color(score),
                source="database",
                matched_code=str(match.get("code", "")),
                matched_price=str(match.get("price", "")),
                invoice_price=invoice_price,
                quantity=quantity,
                price_verified=match.get("price_verified", False),
                ignored=self._is_ignored(raw_text, match["original_name"]),
                debug_core_text=clean.core_text,
                debug_transliterated=transliterated_text,
            )

        # لا يوجد تطابق كافٍ الثقة تكفي للاعتماد التلقائي: نعرض "أقرب اسم"
        # حقيقي موجود فعلاً في شيت فارما تشين لو موجود (مرتبط فعلاً بنفس
        # الاسم التجاري، راجع _identity_guards_pass)، عشان الاسم المعروض
        # يفضل دايماً نص وحرف زي ما هو مكتوب في الشيت. **مفيش أي حالة
        # بترجع تخمين حر من محرك التعريب الصوتي خالص** — لو مفيش صنف
        # حقيقي مرتبط، الخانة تفضل فاضية ولازم المستخدم يكتب يدوياً
        # (تعديل ✏️) أو يستبعد الصنف (🚫) لو مش من أصناف الصيدلية أصلاً.
        closest_name = match.get("closest_name")
        if closest_name:
            suggested = closest_name
            source = "database_low_confidence"
            matched_code = str(match.get("closest_code", ""))
            matched_price = str(match.get("closest_price", ""))
        else:
            suggested = ""
            source = "unmatched"
            matched_code = None
            matched_price = None

        return LineResult(
            original_text=raw_text,
            suggested_arabic=suggested,
            score=float(match.get("score", 0.0)),
            color=RED,
            source=source,
            matched_code=matched_code,
            matched_price=matched_price,
            invoice_price=invoice_price,
            quantity=quantity,
            ignored=self._is_ignored(raw_text, suggested),
            debug_core_text=clean.core_text,
            debug_transliterated=transliterated_text,
        )

    def process_lines(self, lines):
        return [self.process_line(line) for line in lines]

    def process_rows(self, rows):
        """rows: قائمة dict {"name", "quantity", "unit_price"} كما يرجعها pdf_reader.extract_item_rows"""
        return [
            self.process_line(r.get("name", ""), invoice_price=r.get("unit_price"), quantity=r.get("quantity"))
            for r in rows
        ]
