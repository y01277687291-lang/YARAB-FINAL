# -*- coding: utf-8 -*-
"""
قائمة الأصناف "المستبعدة" (Blacklist / Ignored Items)
-------------------------------------------------------
أصناف بتظهر في فواتير Odoo وميحتاجش تتدخل على سيستم فارما تشين خالص
(كوزماتيكس، أكياس، بكرة ريست... إلخ). زر "🚫 استبعاد" بالواجهة يضيف الصنف
هنا مرة واحدة، وبعد كده أي ظهور لنفس الصنف — أو صنف مشابه له جداً حتى لو
فيه فرق بسيط في الصياغة/المسافات — في أي فاتورة قادمة يتلوّن رمادياً
تلقائياً بمجرد المعالجة، دون أي حاجة لمراجعته يدوياً تاني.

المطابقة: تطابق تام على النص بعد التطبيع أولاً (أسرع)، ثم تشابه ضبابي
احتياطي (RapidFuzz) لالتقاط الفروق الطفيفة (مسافة زيادة، خطأ إملائي بسيط)
لنفس الصنف المستبعد بالضبط.
"""
import os
import re
import time

import pandas as pd
from rapidfuzz import fuzz, process

COL_NAME = "Item_Name"

# نسبة تشابه عالية جداً عمداً (مش زي حد المطابقة العادي 80%) — الهدف هنا
# التقاط "نفس الصنف بالظبط" بفروق كتابة طفيفة، مش أصناف مختلفة قريبة الاسم.
FUZZY_IGNORE_THRESHOLD = 90.0


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class IgnoredItemsManager:
    def __init__(self, path: str, cloud=None):
        self.path = path
        self.cloud = cloud  # CloudSync اختياري - راجع cloud_sync.py
        self._keys = []      # مفاتيح مطبَّعة (lower + مسافات موحّدة)
        self._display = []   # النصوص الأصلية كما أُضيفت (للحفظ فقط)
        self.load()

    def load(self):
        self._keys, self._display = [], []
        if self.path and os.path.exists(self.path):
            try:
                df = pd.read_excel(self.path)
                for _, row in df.iterrows():
                    name = str(row.get(COL_NAME, "") or "").strip()
                    if name:
                        self._keys.append(_normalize_key(name))
                        self._display.append(name)
            except Exception:
                # ملف تالف/صيغة غير متوقعة - يبدأ بقائمة فارغة بدل ما يوقف البرنامج
                self._keys, self._display = [], []

        # دمج نسخة السحابة (لو مفعَّلة): أي "استبعاد" حصل على جهاز تاني
        # لازم يظهر هنا كمان، حتى لو الجهازين على شبكتين منفصلتين تماماً.
        if self.cloud and self.cloud.enabled:
            remote = self.cloud.pull("ignored_items")
            if isinstance(remote, list) and remote:
                changed = False
                for name in remote:
                    key = _normalize_key(name)
                    if key and key not in self._keys:
                        self._keys.append(key)
                        self._display.append(name)
                        changed = True
                if changed:
                    try:
                        self._save(push_cloud=False)
                    except Exception:
                        pass

    def is_ignored(self, text: str) -> bool:
        """True لو النص (أو أي نص مشابه له جداً في القائمة) مُستبعد مسبقاً."""
        if not text or not self._keys:
            return False
        key = _normalize_key(text)
        if key in self._keys:
            return True
        result = process.extractOne(key, self._keys, scorer=fuzz.ratio)
        return bool(result and result[1] >= FUZZY_IGNORE_THRESHOLD)

    def add(self, text: str):
        """يضيف صنفاً جديداً لقائمة الاستبعاد ويحفظها فوراً محلياً وفي
        السحابة لو مفعَّلة. يعيد تحميل أحدث نسخة أولاً (احتياطاً للمسار
        المشترك/السحابة) عشان ميفقدش استبعادات أضافها مستخدم تاني."""
        text = (text or "").strip()
        if not text:
            return
        try:
            self.load()
        except Exception:
            pass
        key = _normalize_key(text)
        if key and key not in self._keys:
            self._keys.append(key)
            self._display.append(text)
            self._save()

    def _save(self, push_cloud: bool = True):
        df = pd.DataFrame({COL_NAME: self._display})
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        last_error = None
        for attempt in range(5):
            try:
                df.to_excel(self.path, index=False)
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        else:
            if last_error:
                raise last_error

        if push_cloud and self.cloud and self.cloud.enabled:
            self.cloud.push("ignored_items", self._display)

    def __len__(self):
        return len(self._keys)
