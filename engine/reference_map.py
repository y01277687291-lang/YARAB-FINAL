# -*- coding: utf-8 -*-
"""
شيت الربط اليدوي المرجعي (Reference English -> Arabic Map)
-------------------------------------------------------------------
شيت جاهز بيربط اسم الصنف الإنجليزي زي ما هو مكتوب بالظبط في Odoo بكود
الصنف العربي المطابق في شيت فارما تشين (English_Arabic_Map.xlsx، أعمدة:
"المقابل الإنجليزي" و"الكود (عربي)" — راجع settings.resolve_reference_map_path).

هذا مصدر أولوية قصوى (Step A) قبل أي تنظيف/تعريب/Fuzzy matching: لو الاسم
الإنجليزي (بعد تطبيع بسيط: توحيد الحالة + المسافات فقط، بدون أي تغيير في
الأحرف نفسها) موجود في الشيت، نستخدم الكود المقابل للبحث المباشر في شيت
الأصناف الحقيقي (products.xlsx) عن طريق ProductMatcher.get_by_code() —
وليس نص "الصنف (عربي)" في هذا الشيت نفسه، عشان نضمن رجوع الاسم حرفياً 100%
من شيت فارما تشين الحقيقي دايماً (بيانه ممكن يختلف شكلياً عن نسخة المرجع،
زي غياب لاحقة "سعر جديد" مثلاً).

الأولوية بالنسبة لملف الاستثناءات (Exceptions.xlsx): الاستثناءات (تأكيدات
المستخدم اليدوية من داخل التطبيق نفسه) بتتفحص هي الأول دايماً، لأنها تمثّل
قرار المستخدم الصريح الأحدث ولازم تقدر تتجاوز أي شيء في الشيت المرجعي لو
اختلفوا. الشيت المرجعي ده بيتفحص بعدها مباشرة، قبل أي Fuzzy logic.
"""
import os
import re

import pandas as pd

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """تطبيع خفيف جداً للمقارنة: توحيد الحالة (Upper) + المسافات المتكررة
    فقط — بدون حذف أي حرف أو رمز، عشان يبقى فعلاً 'نفس الاسم كما هو'."""
    return _WS_RE.sub(" ", (text or "").strip().upper())


class ReferenceMapManager:
    def __init__(self, path: str = None):
        self.path = path
        self._map = {}  # normalized_english -> arabic_code (str)
        if path:
            self.load(path)

    def load(self, path: str):
        self.path = path
        self._map = {}
        if not path or not os.path.exists(path):
            return
        try:
            df = pd.read_excel(path)
        except Exception:
            return

        # يقبل تسميات أعمدة مختلفة شائعة، للمرونة لو المستخدم عدّل الهيدر
        english_col = None
        code_col = None
        for col in df.columns:
            c = str(col).strip()
            if c in ("المقابل الإنجليزي", "الاسم الإنجليزي", "english", "English", "Odoo Name"):
                english_col = col
            elif c in ("الكود (عربي)", "كود عربي", "arabic_code", "Arabic Code"):
                code_col = col
        if english_col is None or code_col is None:
            return  # شكل شيت غير متوقع - نتجاهله بأمان بدل ما نكسر التشغيل

        for eng, code in zip(df[english_col], df[code_col]):
            key = _normalize(str(eng))
            if key and pd.notna(code):
                self._map[key] = str(code).strip()

    def lookup_code(self, raw_english_text: str):
        """يرجع كود الصنف العربي المطابق، أو None لو الاسم مش موجود في الشيت المرجعي."""
        if not raw_english_text:
            return None
        return self._map.get(_normalize(raw_english_text))
