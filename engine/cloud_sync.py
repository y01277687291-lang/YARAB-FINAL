# -*- coding: utf-8 -*-
"""
مزامنة سحابية اختيارية (CloudSync) — تخلي بيانات مربوطة عبر أجهزة على
شبكات منفصلة تماماً (مش بس مسار شبكة محلي مشترك): سجل التفعيل (Anchor
إضافي)، الاستثناءات المؤكَّدة يدوياً (Exceptions)، والأصناف المستبعدة
(Ignored Items).

الفكرة: قاعدة بيانات Firebase Realtime Database مجانية (أو أي خدمة
تدعم نفس أسلوب REST البسيط: PUT لحفظ/استبدال قيمة كاملة تحت مسار،
GET لقراءتها) — سطر واحد بس محتاج ضبطه في الإعدادات (رابط القاعدة).

## إزاي تظبطها (مرة واحدة بس، مجاني):
1. روح https://console.firebase.google.com وسجّل دخول بحساب Google.
2. أنشئ مشروع جديد (اسمه أي حاجة، مثلاً "ya-pharma-scan").
3. من القائمة الجانبية: Build -> Realtime Database -> Create Database.
4. اختر "Start in test mode" (يسمح بالقراءة/الكتابة من غير مفاتيح API
   معقّدة - كافي لعدد صيدليات محدود، ومينفعش يتوصله إلا اللي عنده الرابط).
5. هتلاقي رابط شكله: https://ya-pharma-scan-default-rtdb.firebaseio.com
   انسخه وحطه في إعدادات البرنامج -> "رابط المزامنة السحابية".
6. افتح نفس الإعداد بالظبط على كل الأجهزة التانية.

بدون هذا الإعداد، البرنامج يشتغل بالضبط زي ما كان (محلي بالكامل، أو
مسار شبكة محلي لو مضبوط) - المزامنة السحابية طبقة إضافية اختيارية فوق
كده، ومفيش أي طلب شبكة بيحصل أصلاً لو الرابط فاضي.
"""
import json
import urllib.error
import urllib.request


class CloudSync:
    def __init__(self, base_url: str = "", timeout: float = 3.0):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}.json"

    def pull(self, path: str):
        """يرجع القيمة المخزَّنة تحت المسار ده، أو None لو مفيش اتصال/مفيش
        بيانات - أبداً ما بيوقف تشغيل البرنامج حتى لو الإنترنت مقطوع."""
        if not self.enabled:
            return None
        try:
            with urllib.request.urlopen(self._url(path), timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw and raw != "null" else None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None

    def push(self, path: str, value) -> bool:
        """يحفظ (يستبدل بالكامل) القيمة تحت المسار ده. يرجع True/False
        للنجاح، وأبداً ما بيرفع Exception حتى لو الإنترنت مقطوع."""
        if not self.enabled:
            return False
        try:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self._url(path), data=body, method="PUT",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def test_connection(self):
        """فحص سريع للإعدادات: يرجع (True, رسالة) أو (False, رسالة الخطأ)."""
        if not self.enabled:
            return False, "الرابط فاضي."
        ok = self.push("_connection_test", {"ok": True})
        if ok:
            return True, "الاتصال بقاعدة البيانات السحابية شغّال تمام."
        return False, "تعذّر الوصول للرابط ده - راجع الرابط والاتصال بالإنترنت."
