# -*- coding: utf-8 -*-
"""
تسجيل الأصناف "الناقصة" — أصناف ظهرت في فاتورة ولم تُطابَق (أو رفض
المستخدم الاسم المقترح لها) في شيت الأصناف الحقيقي.
-------------------------------------------------------------------
زر "⚠️ ناقص" بالواجهة يستدعي هذا الملف لتسجيل سطر جديد في ملف
Missing_Items.xlsx منفصل تماماً — بدون أي تأثير على الفاتورة الحالية،
ولا على نتائج المطابقة، ولا على ملف الاستثناءات (Exceptions.xlsx).
الهدف قائمة متابعة يرجع لها الفريق لاحقاً لإضافة هذه الأصناف لشيت
الأصناف الحقيقي أو لمراجعتها يدوياً.

الملف قد يعيش على مسار مشترك (شبكة/Drive) مثل باقي ملفات المزامنة، لذلك
نطبّق نفس أسلوب "إعادة تحميل أحدث نسخة قبل الحفظ" + إعادة المحاولة عند
PermissionError المتّبع في engine/exceptions_manager.py، لتفادي فقدان
سطور سجّلها مستخدمون آخرون على أجهزة أخرى بالتوازي.
"""
import os
import time
from datetime import datetime

import pandas as pd

COLUMNS = [
    "التاريخ", "الصيدلية", "اسم الفاتورة",
    "الاسم الأصلي (Odoo)", "الاسم العربي المقترح",
    "سعر الفاتورة", "الكمية",
]


class MissingItemsManager:
    def __init__(self, path: str):
        self.path = path

    def _load(self) -> pd.DataFrame:
        if self.path and os.path.exists(self.path):
            try:
                df = pd.read_excel(self.path)
                for col in COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df[COLUMNS]
            except Exception:
                pass  # ملف تالف/مش موجود بعد - يبدأ بجدول فارغ
        return pd.DataFrame(columns=COLUMNS)

    def record(self, pharmacy_name: str, invoice_filename: str,
               original_text: str, arabic_text: str,
               invoice_price=None, quantity=None) -> bool:
        """يضيف سطراً جديداً لو الصنف (بنفس الاسم الأصلي من Odoo) مش مسجَّل
        في الشيت بالفعل، ويحفظه فوراً على القرص. يرجع True لو أضاف سطر
        جديد فعلاً، أو False لو كان مسجَّل من قبل (متجاهل التكرار عمداً —
        نفس الصنف ميتضافش تاني إلا بعد تصفير الشيت بالكامل عبر clear()).
        بيعمل إعادة تحميل أحدث نسخة أولاً (احتياطاً للمسار المشترك)
        وإعادة المحاولة عند تعارض فتح الملف من جهاز آخر في نفس اللحظة."""
        df = self._load()
        normalized_new = (original_text or "").strip().casefold()
        if normalized_new and df["الاسم الأصلي (Odoo)"].astype(str).str.strip().str.casefold().eq(normalized_new).any():
            return False  # مسجَّل بالفعل - نتجاهل التكرار

        new_row = {
            "التاريخ": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "الصيدلية": pharmacy_name or "",
            "اسم الفاتورة": invoice_filename or "",
            "الاسم الأصلي (Odoo)": original_text or "",
            "الاسم العربي المقترح": arabic_text or "",
            "سعر الفاتورة": invoice_price if invoice_price is not None else "",
            "الكمية": quantity if quantity is not None else "",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        last_error = None
        for attempt in range(5):
            try:
                df.to_excel(self.path, index=False)
                return True
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        if last_error:
            raise last_error
        return True

    def count(self) -> int:
        """عدد الأصناف المسجَّلة حالياً في شيت النواقص."""
        return len(self._load())

    def clear(self):
        """
        يصفّر شيت النواقص بالكامل (يفضل بس صف العناوين) بعد ما يتم سحبه
        ومراجعته — بدون التأثير على أي ملف تاني (الفاتورة/الاستثناءات/
        الاستبعاد). نفس أسلوب إعادة المحاولة عند PermissionError.
        """
        empty_df = pd.DataFrame(columns=COLUMNS)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        last_error = None
        for attempt in range(5):
            try:
                empty_df.to_excel(self.path, index=False)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        if last_error:
            raise last_error
