# -*- coding: utf-8 -*-
"""
التحديث التلقائي للأداة (Auto-Update)
-------------------------------------------------------------------
يتحقق من ملف version.json المنشور على GitHub (Raw URL)، ولو فيه إصدار
أحدث من الحالي، يحمّل ملف الـ .exe الجديد ويستبدل به النسخة الحالية.

آمن على بيانات المستخدم: كل من settings.json وmجلد data/ (الذي يحوي
Exceptions.xlsx وproducts.xlsx) يعيشون بجانب الـ exe في نفس المجلد ولا
يُلمَسون إطلاقاً أثناء التحديث — فقط ملف الـ exe نفسه يُستبدل.

آلية الاستبدال على ويندوز (لا يمكن الكتابة فوق exe شغّال حالياً):
  1) يُنزَّل الإصدار الجديد باسم مؤقت (YAPharmaScan_new.exe).
  2) يُكتب سكربت .bat صغير ينتظر إغلاق العملية الحالية، يمسح القديم،
     يعيد تسمية الجديد بنفس اسم الـ exe الأصلي، ثم يشغّله من جديد.
  3) البرنامج يُغلق نفسه فيشتغل الـ .bat.
"""
import json
import os
import subprocess
import sys
import urllib.request

from version import APP_VERSION


def _version_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def check_for_update(update_url: str, timeout: float = 6.0):
    """
    يرجع dict {"version": "...", "url": "...", "notes": "..."} لو فيه إصدار
    أحدث متاح، أو None لو مفيش تحديث أو الرابط غير مضبوط/غير متاح.

    الصيغة المتوقعة لملف version.json على GitHub:
        {"version": "1.2.0", "url": "https://.../YAPharmaScan.exe",
         "notes": "وصف مختصر للتحديث"}
    """
    if not update_url:
        return None
    try:
        with urllib.request.urlopen(update_url, timeout=timeout) as resp:
            remote = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    remote_version = str(remote.get("version", "0"))
    if _version_tuple(remote_version) > _version_tuple(APP_VERSION):
        return remote
    return None


def download_and_apply_update(download_url: str, progress_callback=None) -> bool:
    """
    ينزّل الإصدار الجديد ويجهّز استبداله عند إغلاق البرنامج.
    يرجع True لو تم التجهيز بنجاح (والبرنامج يحتاج يقفل نفسه بعدها).
    """
    if not getattr(sys, "frozen", False):
        # في وضع التطوير (سكريبت بايثون عادي) لا يوجد exe لاستبداله
        return False

    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    new_path = os.path.join(exe_dir, "_update_new.exe")

    try:
        def _report(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                pct = min(100, int(block_num * block_size * 100 / total_size))
                progress_callback(pct)

        urllib.request.urlretrieve(download_url, new_path, reporthook=_report)
    except Exception:
        return False

    bat_path = os.path.join(exe_dir, "_apply_update.bat")
    bat_content = f"""@echo off
:wait_loop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I "{exe_name}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak > NUL
    goto wait_loop
)
del "{exe_path}"
move /Y "{new_path}" "{exe_path}"
start "" "{exe_path}"
del "%~f0"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    return True
