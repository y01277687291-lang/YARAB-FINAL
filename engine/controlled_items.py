# -*- coding: utf-8 -*-
"""
شيت "الأصناف المهمة" (أدوية جدول / مراقَبة) — Controlled_Items.xlsx
-------------------------------------------------------------------
قائمة أسماء أدوية (عربي، بدون كود/سعر بالضرورة) يجب تمييزها بصرياً بشكل
لافت جداً في أي فاتورة تظهر فيها — عادةً أدوية جدول (مخدرات/مؤثرات
عقلية) تحتاج انتباه خاص من الصيدلي عند الصرف والتوريد.

المطابقة: بالاسم الجوهري (نفس _core_tokens في matcher.py — بعد استبعاد
كلمات الشكل/الجرعة العامة والأرقام)، مش تشابه تقريبي: كل كلمات الاسم
الجوهري للصنف "المهم" لازم تكون موجودة *حرفياً* داخل كلمات الصنف
المطابق/المقترح في الفاتورة، عشان العلامة دي حساسة ولازم تكون دقيقة
100% (إيجابية كاذبة هنا أقل خطورة من سلبية كاذبة، لكن لسه لازم دقة).
"""
import os

import pandas as pd
from rapidfuzz import fuzz

from engine.matcher import _core_tokens


class ControlledItemsManager:
    def __init__(self, path: str = None):
        self.path = path
        self._entries = []  # كل عنصر: set(core tokens) للاسم المهم
        if path:
            self.load(path)

    def load(self, path: str):
        self.path = path
        self._entries = []
        if not path or not os.path.exists(path):
            return
        try:
            df = pd.read_excel(path, header=None)
        except Exception:
            return

        # الشيت فيه صف عنوان + صف فاضي + صف هيدر أعمدة قبل البيانات
        # الفعلية - بنلقط أي خلية بعمود التاني (أو الأول لو عمود واحد بس)
        # تشبه اسم دواء حقيقي (نص عربي، مش رقم/عنوان).
        name_col = 1 if df.shape[1] > 1 else 0
        for value in df[name_col].tolist():
            if not isinstance(value, str):
                continue
            name = value.strip()
            if not name or name in ("اسم الصنف",) or "جدول" in name and "مهم" in name:
                continue  # تجاهل صفوف العنوان/الهيدر
            core = set(_core_tokens(name))
            if core:
                self._entries.append(core)

    def is_controlled(self, arabic_name: str) -> bool:
        """
        يرجع True لو الاسم (المطابق أو المقترح) يحتوي على صنف من قائمة
        الأصناف المهمة. المقارنة قريبة جداً من التطابق التام (نسبة تشابه
        ≥ 88% لكل كلمة) بدل تطابق حرفي 100% صارم، عشان اختلاف بسيط في
        التعريب الصوتي التلقائي (زي "جابتن" مقابل "جابتين") ميفوّتش
        تنبيه صنف مهم فعلاً — الخطأ الأخطر هنا هو تفويت التنبيه، مش
        ظهوره أكتر من اللازم.
        """
        if not arabic_name or not self._entries:
            return False
        item_core = set(_core_tokens(arabic_name))
        if not item_core:
            return False
        for entry in self._entries:
            if all(any(fuzz.ratio(word, item_word) >= 88 for item_word in item_core) for word in entry):
                return True
        return False

    def __len__(self):
        return len(self._entries)
