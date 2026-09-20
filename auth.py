# -*- coding: utf-8 -*-
"""
نظام كلمة المرور والتفعيل (Password + Activation Key System)
-------------------------------------------------------------------
1) كلمة مرور ثابتة لفتح الأداة (App Authentication).
2) كود تفعيل صالح لمدة 30 يوماً من لحظة إدخاله على هذا الجهاز تحديداً.
   - كل كود يُستخدم مرة واحدة فقط ولجهاز واحد فقط (يُربط بمعرّف الجهاز
     "HWID"، راجع get_device_id).
   - سجل الأكواد (license_registry.json) يعيش على مسار مشترك (شبكة/مجلد
     مزامَن) لو تم ضبطه في الإعدادات، بحيث يرى كل الأجهزة نفس حالة كل كود
     فوراً، ويمنع استخدام نفس الكود على أكثر من جهاز.
   - نسخة محلية احتياطية (license_local.json) تُستخدم لو انقطع الوصول
     للمسار المشترك مؤقتاً، حتى لا يتوقف عمل من فعّل الأداة من قبل.

مهم جداً عن الخصوصية (Hash بدل النص الصريح):
   سجل الأكواد المرفق مع البرنامج (وبالتالي المتاح لأي مستخدم يفتح مجلد
   الأداة أو ملفاتها) **لا يحتوي أبداً على الأكواد الحقيقية كنص صريح**، بل
   على "بصمة" (SHA-256 hash) لكل كود فقط. حتى لو فتح أي شخص هذا الملف، مش
   هيقدر يستخرج منه أي كود صالح تاني — لأن تحويل البصمة رجوعاً للكود الأصلي
   غير ممكن عملياً. الكود الحقيقي (activation_codes.txt) يفضل ملف سري خاص
   بالمطوّر فقط، ولا يجب أبداً توزيعه أو رفعه مع الأداة على أي جهاز مستخدم.

-------------------------------------------------------------------
سد ثغرة أمنية (v1.7.1): "مرساة تفعيل" محمية خارج data/ تماماً
-------------------------------------------------------------------
المشكلة القديمة: كل دليل التفعيل (تاريخ التفعيل + الجهاز) كان مخزَّن حصراً
في ملف نصي عادي داخل مجلد data/ (license_local.json). مسح هذا الملف (أو
مجلد data/ كله) كان بيخلّي البرنامج "ينسى" إن الكود اتفعّل قبل كده، فيقبل
نفس الكود تاني كأنه جديد ويدّي 30 يوم كاملة إضافية.

الحل: كل تفعيل بيتسجَّل كمان في "مرساة" (_Anchor) في مكان محمي بره مجلد
data/ تماماً:
  - على ويندوز: قيمة داخل Windows Registry تحت HKEY_CURRENT_USER (مش ملف
    ظاهر جوه مجلد البرنامج، ومش بيتمسح بمسح data/ ولا حتى بإعادة تثبيت
    الأداة في مجلد جديد).
  - fallback (لو مش ويندوز أو تعذّر الوصول للـ Registry لأي سبب): ملف
    مخفي في مجلد المستخدم الشخصي (Home)، برضه بره مجلد البرنامج بالكامل.
عند أي تفعيل أو فحص، المرساة هي المرجع الأول والأخير: لو موجودة وصالحة
لنفس الجهاز، بترجع نفس تاريخ التفعيل الأصلي دايماً (مفيش تجديد تاريخ بمجرد
مسح ملفات data/ وإعادة إدخال نفس الكود).

-------------------------------------------------------------------
تشفير حقيقي (v1.8.0): Fernet (AES + HMAC موثّق) بدل التوقيع اليدوي
-------------------------------------------------------------------
قيمة المرساة (device_id + activated_at) بقت مُشفَّرة بالكامل بمكتبة
`cryptography.fernet.Fernet` (تشفير متماثل قياسي: AES-128-CBC + توثيق
HMAC-SHA256 مدمج) بدل ما تكون JSON عادي مع توقيع يدوي — أي محاولة قراءة
أو تعديل القيمة من غير المفتاح السري (المُشتق من LICENSE_SALT) بترجع
فشل تلقائي (InvalidToken)، فمفيش أي جزء من بيانات التفعيل ممكن يتقرا أو
يتلاعَب بيه بدون المفتاح.
(ملاحظة تقنية بالنسبة للدقة: Fernet بيستخدم AES-128 داخلياً مش AES-256 -
لو مطلوب AES-256 حرفياً محتاج طبقة تشفير مختلفة (AES-GCM يدوي) بتعقيد
وخطورة تنفيذ أعلى بكتير مقابل فايدة أمنية حقيقية إضافية محدودة هنا.)

هوية الجهاز (HWID) بقت أقوى: بنحاول أولاً السيريال نمبر بتاع الـ
Motherboard + ProcessorId بتاع الـ CPU (عبر `wmic` على ويندوز) بدل
الاعتماد بس على عنوان MAC، مع سقوط تلقائي (fallback) للطريقة القديمة
لو wmic مش متاح (نظام غير ويندوز، أو ويندوز حديث شال wmic).
"""
import base64
import hashlib
import json
import os
import platform
import subprocess
import time
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken

from version import APP_PASSWORD, TRIAL_PERIOD_DAYS, LICENSE_SALT
from settings import DATA_DIR, resolve_license_registry_path

try:
    import winreg  # متاح على ويندوز فقط
    _WINREG_AVAILABLE = True
except ImportError:  # لينكس/ماك (وبيئة التطوير/الاختبار)
    winreg = None
    _WINREG_AVAILABLE = False

REGISTRY_ANCHOR_KEY = r"Software\YA_Pharma_Scan\License"
# مرساة احتياطية خارج مجلد data/ تماماً — عمداً في مجلد المستخدم الشخصي
# (Home)، بعيداً عن مجلد البرنامج بالكامل، عشان مسح data/ (أو حتى مجلد
# البرنامج كله لإعادة تثبيته من الصفر) ما يمسحهاش.
FALLBACK_ANCHOR_PATH = os.path.join(os.path.expanduser("~"), ".yaps_license_anchor.dat")


def _derive_fernet_key(salt: str) -> bytes:
    """يشتق مفتاح Fernet صالح (32 بايت urlsafe-base64) من الملح السري الثابت."""
    digest = hashlib.sha256(salt.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET = Fernet(_derive_fernet_key(LICENSE_SALT))


def _wmic_value(args: list) -> str:
    """يشغّل أمر wmic ويرجع القيمة (السطر اللي بعد سطر العنوان)، أو '' لو
    فشل أي حاجة (نظام مش ويندوز، wmic مش موجود، مهلة انتهت...)."""
    try:
        out = subprocess.check_output(
            args, stderr=subprocess.DEVNULL, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).decode(errors="ignore")
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return lines[1] if len(lines) >= 2 else ""
    except Exception:
        return ""


def get_device_id() -> str:
    """
    معرّف الجهاز (HWID). على ويندوز: سيريال نمبر الـ Motherboard +
    ProcessorId بتاع الـ CPU (عبر wmic) - أصعب بكتير على المستخدم العادي
    إنه يغيّرهم أو يزوّرهم عن مجرد عنوان MAC. لو wmic مش متاح لأي سبب
    (نظام غير ويندوز، أو تم إلغاؤه من إصدار ويندوز حديث)، بنرجع تلقائياً
    لعنوان MAC + اسم الجهاز كما كان قبل كده.
    """
    board = _wmic_value(["wmic", "baseboard", "get", "serialnumber"])
    cpu = _wmic_value(["wmic", "cpu", "get", "processorid"])
    if board or cpu:
        raw = f"{board}|{cpu}|{uuid.getnode()}"
    else:
        raw = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def check_password(entered: str) -> bool:
    return entered == APP_PASSWORD


def hash_code(code: str) -> str:
    """
    يحوّل كود التفعيل الحقيقي إلى بصمة (hash) لا يمكن الرجوع منها للكود
    الأصلي — هذه البصمة فقط هي التي تُخزَّن في سجل الأكواد المرفق مع
    الأداة، حفاظاً على سرية الأكواد الحقيقية.
    """
    normalized = (code or "").strip().upper()
    return hashlib.sha256((LICENSE_SALT + normalized).encode("utf-8")).hexdigest()


class _Anchor:
    """
    مرساة تفعيل محمية خارج ملفات data/ الظاهرة تماماً — راجع الشرح الكامل
    أعلى الملف. المصدر الأوثق دايماً لتاريخ أول تفعيل حقيقي لأي كود على
    أي جهاز، حتى لو انمسحت كل ملفات data/. كل قيمة مُشفَّرة بالكامل
    بـ Fernet (مش مجرد موقَّعة) - فك التشفير بيفشل تلقائياً لو اتغيّر أي
    بايت فيها.
    """

    def read_all(self) -> dict:
        """يرجع dict {code_hash: encrypted_token_str} من كل القيم المخزَّنة."""
        if _WINREG_AVAILABLE:
            try:
                out = {}
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_ANCHOR_KEY) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        out[name] = value
                        i += 1
                return out
            except FileNotFoundError:
                return {}
            except OSError:
                return {}
        try:
            if os.path.exists(FALLBACK_ANCHOR_PATH):
                with open(FALLBACK_ANCHOR_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _write_value(self, code_hash: str, token: str):
        if _WINREG_AVAILABLE:
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_ANCHOR_KEY)
                winreg.SetValueEx(key, code_hash, 0, winreg.REG_SZ, token)
                winreg.CloseKey(key)
                return
            except OSError:
                pass  # نكمل على fallback لو الوصول للـ Registry اتمنع لأي سبب
        data = self.read_all()
        data[code_hash] = token
        try:
            with open(FALLBACK_ANCHOR_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get(self, code_hash: str):
        """يرجع dict {device_id, activated_at} لو القيمة موجودة وتم فك
        تشفيرها بنجاح، وإلا None (بما في ذلك حالة عدم الوجود أو التلاعب)."""
        token = self.read_all().get(code_hash)
        if not token:
            return None
        try:
            decrypted = _FERNET.decrypt(token.encode("utf-8") if isinstance(token, str) else token)
            info = json.loads(decrypted.decode("utf-8"))
            return {"device_id": info["device_id"], "activated_at": info["activated_at"]}
        except (InvalidToken, ValueError, KeyError, TypeError):
            return None  # تالف/متلاعَب به/مش نفس المفتاح السري -> يُعامل كغير موجود

    def set(self, code_hash: str, device_id: str, activated_at: str):
        payload = json.dumps({"device_id": device_id, "activated_at": activated_at}).encode("utf-8")
        token = _FERNET.encrypt(payload).decode("utf-8")
        self._write_value(code_hash, token)


LOCAL_LICENSE_PATH = os.path.join(DATA_DIR, "license_local.json")


class LicenseManager:
    def __init__(self, settings: dict, cloud=None):
        self.settings = settings
        self.registry_path = resolve_license_registry_path(settings)
        self.device_id = get_device_id()
        self.anchor = _Anchor()
        self.cloud = cloud  # CloudSync اختياري - راجع engine/cloud_sync.py

    # ---------------------------------------------------------------- IO
    def _load_registry(self) -> dict:
        data = {"hashes": {}}
        for path in (self.registry_path, LOCAL_LICENSE_PATH):
            try:
                if path and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    break
            except Exception:
                continue

        # دمج نسخة السحابة (لو مفعَّلة): أي كود اتفعّل على جهاز في صيدلية
        # تانية على شبكة منفصلة تماماً لازم يظهر هنا كمان - عشان نكتشف
        # فعلياً لو نفس الكود بيتحاول يتفعّل على أكتر من جهاز، حتى لو
        # الجهازين مش على نفس الشبكة المحلية خالص.
        if self.cloud and self.cloud.enabled:
            remote = self.cloud.pull("license_registry")
            if isinstance(remote, dict) and remote.get("hashes"):
                hashes = data.setdefault("hashes", {})
                for code_hash, info in remote["hashes"].items():
                    if code_hash not in hashes:
                        hashes[code_hash] = info
        return data

    def _save_registry(self, data: dict):
        os.makedirs(os.path.dirname(self.registry_path) or ".", exist_ok=True)
        last_error = None
        for attempt in range(5):
            try:
                with open(self.registry_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        else:
            if last_error:
                raise last_error
        # نسخة محلية احتياطية دائماً، حتى لو المسار المشترك اشتغل
        os.makedirs(os.path.dirname(LOCAL_LICENSE_PATH) or ".", exist_ok=True)
        with open(LOCAL_LICENSE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.cloud and self.cloud.enabled:
            self.cloud.push("license_registry", data)

    # ------------------------------------------------------------ لوجيك
    def current_activation(self):
        """
        يرجع dict {"activated_at": iso, "days_left": float} لو هذا الجهاز
        عنده تفعيل ساري حالياً، وإلا None. المرساة المحمية (خارج data/)
        هي المرجع الأساسي، فهي بتفضل فاكرة أول تاريخ تفعيل حتى لو انمسحت
        كل ملفات data/ بالكامل.
        """
        device_id = self.device_id
        best = None  # (activated_at_dt, code_hash)

        # 1) نمرّ على سجل data/ عشان أي كود اتفعّل عليه قبل كده — ولو
        #    لقيناه من غير مرساة بعد (نسخة أقدم من الأداة)، نؤمّنه دلوقتي.
        data = self._load_registry()
        for code_hash, info in data.get("hashes", {}).items():
            if info.get("device_id") == device_id and info.get("activated_at"):
                if self.anchor.get(code_hash) is None:
                    self.anchor.set(code_hash, device_id, info["activated_at"])
                try:
                    activated_at = datetime.fromisoformat(info["activated_at"])
                except ValueError:
                    continue
                if best is None or activated_at < best[0]:
                    best = (activated_at, code_hash)

        # 2) المرساة المحمية نفسها — المرجع اللي بيفضل موجود حتى لو
        #    انمسحت كل ملفات data/.
        for code_hash in self.anchor.read_all().keys():
            verified = self.anchor.get(code_hash)
            if verified and verified.get("device_id") == device_id:
                try:
                    activated_at = datetime.fromisoformat(verified["activated_at"])
                except ValueError:
                    continue
                if best is None or activated_at < best[0]:
                    best = (activated_at, code_hash)

        if best is None:
            return None
        activated_at, code_hash = best
        expires_at = activated_at + timedelta(days=TRIAL_PERIOD_DAYS)
        remaining = (expires_at - datetime.now()).total_seconds() / 3600.0
        if remaining <= 0:
            return None
        return {
            "code_hash": code_hash,
            "activated_at": activated_at.isoformat(timespec="seconds"),
            "hours_left": remaining,
            "days_left": remaining / 24.0,
        }

    def activate(self, code: str):
        """
        يحاول تفعيل كود جديد على هذا الجهاز.
        يرجع (True, رسالة) عند النجاح، أو (False, رسالة الخطأ) عند الفشل.
        """
        code = (code or "").strip().upper()
        if not code:
            return False, "من فضلك اكتب كود التفعيل."

        code_hash = hash_code(code)
        device_id = self.device_id

        # المرساة المحمية أولاً: لو الكود ده اتفعّل قبل كده (حتى لو
        # ملفات data/ اتمسحت بالكامل)، منديش 30 يوم جديدة تانية — نرجّع
        # نفس تاريخ التفعيل الأصلي كما هو ونعيد بناء ملفات data/ منه.
        anchored = self.anchor.get(code_hash)
        if anchored:
            if anchored["device_id"] != device_id:
                return False, "هذا الكود مُفعَّل بالفعل على جهاز آخر."
            data = self._load_registry()
            hashes = data.setdefault("hashes", {})
            entry = hashes.setdefault(code_hash, {})
            entry["device_id"] = device_id
            entry["activated_at"] = anchored["activated_at"]
            entry["device_name"] = platform.node()
            try:
                self._save_registry(data)
            except Exception:
                pass  # المرساة المحمية كافية للتحقق حتى لو فشل حفظ JSON دلوقتي
            return True, "هذا الكود مفعَّل بالفعل على هذا الجهاز."

        data = self._load_registry()
        hashes = data.setdefault("hashes", {})
        entry = hashes.get(code_hash)

        if entry is None:
            return False, "الكود غير موجود ضمن قائمة الأكواد الصادرة."

        if entry.get("device_id") and entry["device_id"] != device_id:
            return False, "هذا الكود مُفعَّل بالفعل على جهاز آخر."

        if entry.get("device_id") == device_id and entry.get("activated_at"):
            # كان مفعَّل من قبل تفعيل المرساة (نسخة أقدم من الأداة) - نؤمّنه الآن
            self.anchor.set(code_hash, device_id, entry["activated_at"])
            return True, "هذا الكود مفعَّل بالفعل على هذا الجهاز."

        # تفعيل جديد فعلاً: تبدأ مدة الـ30 يوماً من هذه اللحظة بالضبط
        activated_at = datetime.now().isoformat(timespec="seconds")
        entry["device_id"] = device_id
        entry["activated_at"] = activated_at
        entry["device_name"] = platform.node()
        self._save_registry(data)
        self.anchor.set(code_hash, device_id, activated_at)  # التأمين ضد مسح data/
        return True, "تم التفعيل بنجاح! تبدأ مدة 30 يوماً من الآن."
