# -*- coding: utf-8 -*-
"""
مزامنة سحابية اختيارية (Cloud Sync) — Firebase Realtime Database أو أي
قاعدة بيانات JSON مجانية بتدعم GET/PUT بسيطة عبر REST.
-------------------------------------------------------------------
الهدف: ربط بيانات كل الأجهزة ببعض حتى لو كل جهاز على شبكة منفصلة
تماماً (بعكس "المسار المشترك" اللي بيشتغل بس لو الأجهزة على نفس الشبكة
المحلية). المزامنة دي بتغطي 3 حاجات:
  1. سجل التفعيل (license) - عشان نكتشف لو نفس الكود اتفعّل على جهاز
     مختلف، حتى لو الجهازين في صيدليتين منفصلتين تماماً.
  2. الاستثناءات (Exceptions) - أي "✅ تأكيد" على أي جهاز يظهر عند
     باقي الأجهزة.
  3. الأصناف المستبعدة (Ignored Items) - أي "🚫 استبعاد" على أي جهاز
     يظهر عند باقي الأجهزة.

الإعداد بالكامل اختياري: من غير رابط مُهيَّأ في الإعدادات (cloud_sync_url
فاضي، وهو الافتراضي)، كل حاجة بتشتغل محلياً/بمسار مشترك بس زي الأول
بالظبط - مفيش أي تغيير في السلوك. أي فشل في الاتصال (لا يوجد إنترنت،
الرابط غلط، السيرفر واقع) بيُتجاهَل بهدوء والبرنامج يكمل شغله محلياً.

خطوات التفعيل (مرة واحدة لكل الأجهزة، من الإعدادات):
  1. اعمل مشروع Firebase مجاني (console.firebase.google.com).
  2. فعّل "Realtime Database" واضبطه على وضع اختبار (test mode) أو
     قواعد قراءة/كتابة مفتوحة لعنوان القاعدة بتاعتك.
  3. انسخ رابط القاعدة (شكله: https://PROJECT-ID-default-rtdb.firebaseio.com)
     والصقه في خانة "رابط المزامنة السحابية" بالإعدادات في كل الأجهزة.
"""
import json
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 5


class CloudSync:
    def __init__(self, base_url: str = ""):
        self.base_url = (base_url or "").strip().rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def _url_for(self, key: str) -> str:
        return f"{self.base_url}/{key}.json"

    def pull(self, key: str):
        """يرجع البيانات المخزَّنة تحت هذا المفتاح، أو None لو غير مفعَّل
        أو تعذّر الوصول (بدون إنترنت مثلاً) — يُتجاهَل بهدوء دائماً."""
        if not self.enabled:
            return None
        try:
            with urllib.request.urlopen(self._url_for(key), timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw and raw != "null" else None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None

    def push(self, key: str, data) -> bool:
        """يحفظ البيانات تحت هذا المفتاح في السحابة. يرجع True لو نجح،
        False لو غير مفعَّل أو فشل الاتصال — الفشل هنا لا يوقف أي شيء،
        النسخة المحلية هي دائماً المرجع الأول والمضمون."""
        if not self.enabled:
            return False
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                self._url_for(key), data=payload, method="PUT",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS):
                pass
            return True
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return False
