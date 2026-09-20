# -*- coding: utf-8 -*-
"""اختبار المزامنة السحابية (CloudSync) وتكاملها مع الاستثناءات/الاستبعاد/
سجل التفعيل — بدون أي اتصال إنترنت فعلي (Fake بديل لـ CloudSync الحقيقي
يحاكي قاعدة بيانات في الذاكرة، عشان الاختبار يبقى سريع وحتمي)."""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.cloud_sync import CloudSync  # noqa: E402
from engine.exceptions_manager import ExceptionsManager  # noqa: E402
from engine.ignored_items_manager import IgnoredItemsManager  # noqa: E402
import auth  # noqa: E402


class FakeCloud:
    """بديل CloudSync بقاعدة بيانات في الذاكرة (مشتركة بين "أجهزة" الاختبار
    عن طريق نفس الـ dict) - بيحاكي بالظبط واجهة CloudSync الحقيقية."""

    def __init__(self, store: dict):
        self.store = store  # نفس الـ dict بين كل نسخ FakeCloud = "سحابة" مشتركة

    @property
    def enabled(self):
        return True

    def pull(self, path):
        return self.store.get(path)

    def push(self, path, value):
        self.store[path] = value
        return True


def test_cloud_sync_disabled_when_no_url():
    cs = CloudSync("")
    assert cs.enabled is False
    assert cs.pull("anything") is None
    assert cs.push("anything", {}) is False


def test_exception_confirmed_on_one_device_appears_on_another():
    """محاكاة السيناريو المطلوب بالظبط: جهاز يأكّد صنف، وجهاز تاني (شبكة
    منفصلة تماماً، غير متصلين ببعض إلا عن طريق السحابة) لازم يشوفه."""
    cloud_store = {}
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        device_a = ExceptionsManager(os.path.join(tmp_a, "Exceptions.xlsx"), cloud=FakeCloud(cloud_store))
        device_a.add_exception("WEIRD ENGLISH NAME", "اسم عربي مؤكد من جهاز أ")

        # جهاز ب: مجلد محلي مختلف تماماً، بس نفس "السحابة" المشتركة
        device_b = ExceptionsManager(os.path.join(tmp_b, "Exceptions.xlsx"), cloud=FakeCloud(cloud_store))
        assert device_b.lookup("WEIRD ENGLISH NAME") == "اسم عربي مؤكد من جهاز أ"


def test_ignored_item_excluded_on_one_device_appears_on_another():
    cloud_store = {}
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        device_a = IgnoredItemsManager(os.path.join(tmp_a, "Ignored_Items.xlsx"), cloud=FakeCloud(cloud_store))
        device_a.add("COSMETIC ITEM XYZ")

        device_b = IgnoredItemsManager(os.path.join(tmp_b, "Ignored_Items.xlsx"), cloud=FakeCloud(cloud_store))
        assert device_b.is_ignored("COSMETIC ITEM XYZ") is True


def test_activation_code_used_on_one_device_rejected_on_another(monkeypatch):
    """نفس فكرة اختبارات auth.py الحالية، بس هنا بمحاكاة سحابة حقيقية بين
    جهازين منفصلين تماماً - ده بالظبط السيناريو اللي المستخدم قلق منه."""
    cloud_store = {}
    code = "YAPS-CLOUD-TEST-0001"
    code_hash = auth.hash_code(code)

    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        # بذر الكود كـ"صادر" في سجل جهاز أ المحلي (يمثّل نسخة موزَّعة مع البرنامج)
        registry_path_a = os.path.join(tmp_a, "license_registry.json")
        import json
        os.makedirs(os.path.dirname(registry_path_a), exist_ok=True)
        with open(registry_path_a, "w", encoding="utf-8") as f:
            json.dump({"hashes": {code_hash: {"device_id": None, "activated_at": None}}}, f)
        registry_path_b = os.path.join(tmp_b, "license_registry.json")
        with open(registry_path_b, "w", encoding="utf-8") as f:
            json.dump({"hashes": {code_hash: {"device_id": None, "activated_at": None}}}, f)

        monkeypatch.setattr(auth, "LOCAL_LICENSE_PATH", os.path.join(tmp_a, "local_a.json"))
        settings_a = {}
        mgr_a = auth.LicenseManager(settings_a, cloud=FakeCloud(cloud_store))
        monkeypatch.setattr(mgr_a, "registry_path", registry_path_a)
        monkeypatch.setattr(mgr_a, "device_id", "device-A")

        ok_a, _ = mgr_a.activate(code)
        assert ok_a

        monkeypatch.setattr(auth, "LOCAL_LICENSE_PATH", os.path.join(tmp_b, "local_b.json"))
        settings_b = {}
        mgr_b = auth.LicenseManager(settings_b, cloud=FakeCloud(cloud_store))
        monkeypatch.setattr(mgr_b, "registry_path", registry_path_b)
        monkeypatch.setattr(mgr_b, "device_id", "device-B")

        ok_b, msg_b = mgr_b.activate(code)
        assert not ok_b
        assert "جهاز آخر" in msg_b
