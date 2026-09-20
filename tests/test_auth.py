# -*- coding: utf-8 -*-
"""اختبار نظام التفعيل والمرساة المحمية (auth.py) - يتأكد إن مسح ملفات
data/ (السجل المشترك/المحلي) ما يسمحش بإعادة استخدام نفس الكود للحصول
على 30 يوم تانية، لأن المرساة (خارج data/ تماماً) لسه فاكرة أول تفعيل."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402


def _fresh_manager(tmp_dir, monkeypatch, anchor_path):
    """مدير تفعيل معزول تماماً عن أي بيانات حقيقية على الجهاز الفعلي."""
    monkeypatch.setattr(auth, "LOCAL_LICENSE_PATH", os.path.join(tmp_dir, "license_local.json"))
    monkeypatch.setattr(auth, "FALLBACK_ANCHOR_PATH", anchor_path)
    monkeypatch.setattr(auth, "_WINREG_AVAILABLE", False)
    monkeypatch.setattr(auth, "winreg", None)
    settings = {"shared_folder_path": tmp_dir}
    return auth.LicenseManager(settings)


def _seed_issued_code(registry_path, code_hash):
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump({"hashes": {code_hash: {"device_id": None, "activated_at": None}}}, f)


def test_activation_survives_data_folder_wipe(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        anchor_path = os.path.join(tmp, "anchor.dat")
        code = "YAPS-TEST-CODE-0001"
        code_hash = auth.hash_code(code)

        mgr = _fresh_manager(tmp, monkeypatch, anchor_path)
        _seed_issued_code(mgr.registry_path, code_hash)

        ok, msg = mgr.activate(code)
        assert ok, msg
        info_before = mgr.current_activation()
        assert info_before is not None
        original_activated_at = info_before["activated_at"]

        # امسح كل ملفات data/ (السجل المشترك بالكامل) - يحاكي "مسح ملف الـ Text"
        os.remove(mgr.registry_path)
        if os.path.exists(auth.LOCAL_LICENSE_PATH):
            os.remove(auth.LOCAL_LICENSE_PATH)

        # مدير جديد تماماً (زي إعادة فتح البرنامج) بعد المسح
        mgr2 = _fresh_manager(tmp, monkeypatch, anchor_path)
        info_after = mgr2.current_activation()
        assert info_after is not None, "المرساة المحمية المفروض تفضل فاكرة التفعيل بعد مسح data/"
        assert info_after["activated_at"] == original_activated_at, \
            "تاريخ التفعيل لازم يفضل زي ما هو (بدون تجديد) حتى بعد مسح data/"

        # وحتى لو حاول يفعّل نفس الكود تاني بعد المسح، ميدّيهوش تاريخ جديد
        ok2, _ = mgr2.activate(code)
        assert ok2
        info_after_reactivate = mgr2.current_activation()
        assert info_after_reactivate["activated_at"] == original_activated_at


def test_tampered_anchor_token_is_rejected(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        anchor_path = os.path.join(tmp, "anchor.dat")
        code = "YAPS-TEST-CODE-0002"
        code_hash = auth.hash_code(code)

        mgr = _fresh_manager(tmp, monkeypatch, anchor_path)
        _seed_issued_code(mgr.registry_path, code_hash)
        mgr.activate(code)

        # تعديل يدوي مباشر على توكن Fernet المشفَّر جوه ملف المرساة (محاولة تلاعب)
        with open(anchor_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        token = raw[code_hash]
        tampered_token = token[:-4] + ("A" * 4)  # تخريب آخر 4 حروف من التوكن المشفَّر
        raw[code_hash] = tampered_token
        with open(anchor_path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        assert mgr.anchor.get(code_hash) is None, "فك التشفير لازم يفشل تلقائياً بعد أي تعديل يدوي على التوكن"


def test_different_device_rejected_even_with_anchor(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        anchor_path = os.path.join(tmp, "anchor.dat")
        code = "YAPS-TEST-CODE-0003"
        code_hash = auth.hash_code(code)

        mgr = _fresh_manager(tmp, monkeypatch, anchor_path)
        _seed_issued_code(mgr.registry_path, code_hash)
        mgr.activate(code)

        mgr2 = _fresh_manager(tmp, monkeypatch, anchor_path)
        monkeypatch.setattr(mgr2, "device_id", "different-device-id")
        ok, msg = mgr2.activate(code)
        assert not ok
        assert "جهاز آخر" in msg

def test_get_device_id_falls_back_without_wmic(monkeypatch):
    """على أي نظام مالوش wmic (زي بيئة الاختبار دي)، لازم يرجع HWID ثابت
    ومتناسق (مش يفشل ولا يرجع None) عن طريق fallback الطريقة القديمة."""
    device_id = auth.get_device_id()
    assert isinstance(device_id, str) and len(device_id) == 16
    assert device_id == auth.get_device_id()  # ثابت بين النداءات المتكررة

def test_reactivating_same_expired_code_does_not_grant_current_activation(monkeypatch):
    """
    يعيد إنتاج ثغرة حقيقية اتصلحت في واجهة AuthGate: activate() بيرجع
    True لمجرد إن الكود ده اتفعّل قبل كده على نفس الجهاز (idempotent)،
    من غير ما يجدد تاريخ التفعيل. الشاشة (AuthGate._check_activation)
    لازم تتأكد من current_activation() منفصل قبل ما تفتح البرنامج، مش
    تثق في ok=True لوحدها - وإلا كان ممكن حد يلف الـ30 يوم بإعادة كتابة
    نفس الكود القديم بدل كود جديد فعلاً.
    """
    with tempfile.TemporaryDirectory() as tmp:
        anchor_path = os.path.join(tmp, "anchor.dat")
        code = "YAPS-TEST-CODE-0004"
        code_hash = auth.hash_code(code)

        mgr = _fresh_manager(tmp, monkeypatch, anchor_path)
        _seed_issued_code(mgr.registry_path, code_hash)
        ok1, _ = mgr.activate(code)
        assert ok1
        assert mgr.current_activation() is not None  # سارٍ فعلاً في البداية

        # نقفز 31 يوم للأمام (بعد انتهاء الصلاحية)
        real_datetime = auth.datetime

        class _FrozenFuture(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return real_datetime.now(tz) + real_datetime.resolution * 0 + __import__("datetime").timedelta(days=31)

        monkeypatch.setattr(auth, "datetime", _FrozenFuture)

        assert mgr.current_activation() is None  # لازم يبقى منتهي دلوقتي

        # المستخدم يحاول "يعيد تفعيل" نفس الكود القديم تاني (مش كود جديد)
        ok2, _ = mgr.activate(code)
        assert ok2  # activate() نفسه بيرجع True (idempotent) - ده متوقَّع
        # لكن التفعيل الفعلي لازم يفضل منتهي - مفيش تجديد مجاني بإعادة نفس الكود
        assert mgr.current_activation() is None
