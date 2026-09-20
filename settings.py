# -*- coding: utf-8 -*-
"""إدارة ملف settings.json المحفوظ بجانب الأداة (مسارات شيت الأصناف واستثناءاته).

ملاحظة عن التجميع بـ PyInstaller (--onefile):
  - الملفات المرفقة عبر --add-data تُستخرج مؤقتاً في مجلد للقراءة فقط
    (sys._MEIPASS) عند كل تشغيل، وتُحذف بعد إغلاق البرنامج.
  - لذلك أي ملف قابل للتعديل من المستخدم (Exceptions.xlsx الذي يُكتب فيه
    باستمرار، وsettings.json) يجب أن يعيش في مجلد بجانب ملف الـ .exe نفسه
    (قابل للكتابة ويبقى بعد إغلاق البرنامج)، وليس داخل MEIPASS المؤقت.
  - عند أول تشغيل، لو لم توجد نسخة "حية" من data/ بجانب الـ exe، تُنسخ
    النسخة الافتراضية المرفقة داخل الحزمة إليها تلقائياً.
"""
import json
import os
import shutil
import sys


def _exe_dir() -> str:
    """المجلد القابل للكتابة بجانب الأداة، سواء كسكريبت أو .exe مُجمّع."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _bundled_dir() -> str:
    """مجلد الموارد الافتراضية المرفقة مع الحزمة (للقراءة فقط)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_PATH = os.path.join(_exe_dir(), "settings.json")
DATA_DIR = os.path.join(_exe_dir(), "data")
_BUNDLED_DATA_DIR = os.path.join(_bundled_dir(), "data")


def _ensure_writable_data_dir():
    """ينسخ data/ الافتراضية بجانب الـ exe عند أول تشغيل إن لم تكن موجودة."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isdir(_BUNDLED_DATA_DIR):
        return
    for fname in os.listdir(_BUNDLED_DATA_DIR):
        dest = os.path.join(DATA_DIR, fname)
        if not os.path.exists(dest):
            shutil.copy2(os.path.join(_BUNDLED_DATA_DIR, fname), dest)


_ensure_writable_data_dir()

DEFAULTS = {
    "products_path": os.path.join(DATA_DIR, "products.xlsx"),
    "reference_map_path": os.path.join(DATA_DIR, "English_Arabic_Map.xlsx"),
    # مسار الاستثناءات المحلي (Fallback لو المسار المشترك مش متاح مؤقتاً)
    "exceptions_path": os.path.join(DATA_DIR, "Exceptions.xlsx"),
    # مسار مجلد مشترك على الشبكة (مثال: \\SERVER\Pharma\YA_Pharma_Scan أو
    # مجلد مزامَن عبر Google Drive/OneDrive) يحتوي Exceptions.xlsx +
    # license_registry.json بحيث تنعكس التأكيدات والتفعيل فوراً لكل الأجهزة.
    # اتركه فارغاً لاستخدام المسار المحلي فقط.
    "shared_folder_path": "",
    "cloud_sync_url": "",       # رابط Firebase Realtime Database اختياري - راجع engine/cloud_sync.py
    "turbo_mode": False,        # وضع التوربو: نسخ -> Alt+Tab -> لصق -> Enter تلقائياً (راجع turbo.py)
    "match_threshold": 80.0,
    "price_match_tolerance": 1.0,     # فرق مسموح به بالجنيه عند مقارنة السعر
    "price_match_bonus": 10.0,        # نسبة الزيادة على الثقة عند تطابق السعر
    "window_geometry": "1150x650",
    "update_url": "",                  # رابط version.json للتحديث التلقائي
    # وضع عرض النص العربي: "reshape_bidi" (افتراضي، تشكيل حروف متصلة +
    # ترتيب اتجاه صحيح عبر arabic_reshaper+bidi) أو "plain" (تمرير النص
    # الخام بدون أي معالجة، معتمدين على عرض ويندوز/Tk الأصلي للعربي).
    # جرّب "plain" من شاشة الإعدادات لو النص لسه بايظ رغم إصلاحات الخط —
    # ده بيفصل هل المشكلة أصلاً في خطوة إعادة التشكيل نفسها ولا في حاجة تانية.
    "arabic_render_mode": "plain",
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULTS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def resolve_exceptions_path(settings: dict) -> str:
    """
    يرجّح المسار المشترك (shared_folder_path/Exceptions.xlsx) لو مضبوط
    ومتاح للوصول، وإلا يرجع المسار المحلي كخطة بديلة (Fallback) حتى لا
    يتوقف العمل عند انقطاع الشبكة مؤقتاً.
    """
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        shared_path = os.path.join(shared, "Exceptions.xlsx")
        try:
            os.makedirs(shared, exist_ok=True)
            return shared_path
        except OSError:
            pass  # المسار المشترك غير متاح الآن - نستخدم المحلي مؤقتاً
    return settings.get("exceptions_path") or os.path.join(DATA_DIR, "Exceptions.xlsx")


def resolve_reference_map_path(settings: dict) -> str:
    """نفس منطق resolve_exceptions_path لكن للشيت المرجعي الجاهز (ربط
    إنجليزي->كود عربي، Step A في خط أنابيب المطابقة)."""
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        try:
            os.makedirs(shared, exist_ok=True)
            return os.path.join(shared, "English_Arabic_Map.xlsx")
        except OSError:
            pass
    return settings.get("reference_map_path") or os.path.join(DATA_DIR, "English_Arabic_Map.xlsx")


def resolve_controlled_items_path(settings: dict) -> str:
    """نفس منطق resolve_exceptions_path لكن لشيت الأصناف المهمة (أدوية جدول)."""
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        try:
            os.makedirs(shared, exist_ok=True)
            return os.path.join(shared, "Controlled_Items.xlsx")
        except OSError:
            pass
    return os.path.join(DATA_DIR, "Controlled_Items.xlsx")


def resolve_missing_items_path(settings: dict) -> str:
    """نفس منطق resolve_exceptions_path لكن لملف تتبّع الأصناف الناقصة
    (سجل منفصل تماماً، لا يؤثر على الفاتورة ولا على ملف الاستثناءات)."""
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        try:
            os.makedirs(shared, exist_ok=True)
            return os.path.join(shared, "Missing_Items.xlsx")
        except OSError:
            pass  # المسار المشترك غير متاح الآن - نستخدم المحلي مؤقتاً
    return os.path.join(DATA_DIR, "Missing_Items.xlsx")


def resolve_ignored_items_path(settings: dict) -> str:
    """نفس منطق resolve_exceptions_path لكن لقائمة الأصناف "المستبعدة"
    (Blacklist) اللي مش المفروض تتدخل على السيستم أصلاً (كوزماتيكس، أكياس،
    بكر ريست...). قائمة منفصلة تماماً عن الاستثناءات وعن الأصناف الناقصة."""
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        try:
            os.makedirs(shared, exist_ok=True)
            return os.path.join(shared, "Ignored_Items.xlsx")
        except OSError:
            pass  # المسار المشترك غير متاح الآن - نستخدم المحلي مؤقتاً
    return os.path.join(DATA_DIR, "Ignored_Items.xlsx")


def resolve_license_registry_path(settings: dict) -> str:
    """نفس منطق resolve_exceptions_path لكن لسجل أكواد التفعيل المشترك."""
    shared = (settings.get("shared_folder_path") or "").strip()
    if shared:
        try:
            os.makedirs(shared, exist_ok=True)
            return os.path.join(shared, "license_registry.json")
        except OSError:
            pass
    return os.path.join(DATA_DIR, "license_registry.json")
