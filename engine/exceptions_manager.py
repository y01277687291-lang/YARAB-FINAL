# -*- coding: utf-8 -*-
"""
المرحلة 5 (الأولوية المطلقة): محرك الاستثناءات والتعلم الذاتي
-------------------------------------------------------------------
قبل أي تعريب صوتي، يبحث البرنامج أولاً في ملف Exceptions.xlsx:
  العمود A: Odoo_Raw_Name        (الاسم كما يظهر في الفاتورة)
  العمود B: Mapped_Arabic_Name   (الاسم العربي المعتمد)

عند تعديل صنف يدوياً من الواجهة، زر "حفظ كاستثناء" يضيف هذا الربط هنا
فوراً ليتعرف عليه النظام في كل الفواتير التالية.
"""
import os
import re
import time
import pandas as pd

COL_RAW = "Odoo_Raw_Name"
COL_MAPPED = "Mapped_Arabic_Name"


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class ExceptionsManager:
    def __init__(self, path: str, cloud=None):
        self.path = path
        self.cloud = cloud  # CloudSync اختياري - راجع cloud_sync.py
        self._map = {}
        self.load()

    def load(self):
        self._map = {}
        if self.path and os.path.exists(self.path):
            try:
                df = pd.read_excel(self.path)
                for _, row in df.iterrows():
                    raw = str(row.get(COL_RAW, "") or "")
                    mapped = str(row.get(COL_MAPPED, "") or "")
                    if raw.strip():
                        self._map[_normalize_key(raw)] = mapped.strip()
            except Exception:
                # ملف تالف أو صيغة غير متوقعة - يبدأ البرنامج بقائمة استثناءات فارغة
                self._map = {}
        else:
            # لا يوجد ملف بعد - يُنشأ فارغاً عند أول حفظ
            self._map = {}

        # دمج نسخة السحابة (لو مفعَّلة): أي "تأكيد" حصل على جهاز تاني
        # (حتى على شبكة منفصلة تماماً) لازم يظهر هنا كمان. النسخة المحلية
        # على القرص تتحدَّث فوراً بالدمج، عشان تفضل متاحة حتى لو السحابة
        # مش متاحة في المرة الجاية.
        if self.cloud and self.cloud.enabled:
            remote = self.cloud.pull("exceptions")
            if isinstance(remote, dict) and remote:
                changed = False
                for key, mapped in remote.items():
                    if key not in self._map:
                        self._map[key] = mapped
                        changed = True
                if changed:
                    try:
                        self._save(push_cloud=False)
                    except Exception:
                        pass

    def lookup(self, raw_text: str):
        """يرجع الاسم العربي المعتمد لو السطر موجود في ملف الاستثناءات، وإلا None."""
        return self._map.get(_normalize_key(raw_text))

    def add_exception(self, raw_text: str, mapped_arabic: str):
        """
        يضيف (أو يحدّث) استثناء ويحفظه فوراً في الملف على القرص، وفي
        السحابة لو مفعَّلة (عشان باقي الأجهزة تشوفه فوراً حتى لو على
        شبكة مختلفة تماماً).
        لو المسار مشترك على الشبكة، نعيد تحميل أحدث نسخة أولاً قبل الحفظ
        حتى لا نفقد تأكيدات أضافها مستخدمون آخرون على أجهزة أخرى بالتوازي.
        """
        try:
            latest = ExceptionsManager(self.path, cloud=self.cloud)
            self._map.update(latest._map)
        except Exception:
            pass  # المسار المشترك غير متاح مؤقتاً - نكمل بالنسخة المحلية الحالية
        key = _normalize_key(raw_text)
        self._map[key] = mapped_arabic.strip()
        self._save()

    def _save(self, push_cloud: bool = True):
        rows = [
            {COL_RAW: raw, COL_MAPPED: mapped}
            for raw, mapped in self._map.items()
        ]
        df = pd.DataFrame(rows, columns=[COL_RAW, COL_MAPPED])
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        # المسار قد يكون على مجلد شبكة مشترك (Shared Path) قد يفتحه أكثر
        # من مستخدم في نفس اللحظة، فنعيد المحاولة بضع مرات قبل الاستسلام.
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
            self.cloud.push("exceptions", self._map)

    def __len__(self):
        return len(self._map)
