# -*- coding: utf-8 -*-
"""
وضع التوربو (Turbo Mode) — تسريع نقل الاسم من الأداة لنظام المخازن.
-------------------------------------------------------------------
بدل: نسخ -> Alt+Tab يدوي -> Ctrl+V يدوي -> Enter يدوي (4 خطوات لكل صنف)،
لما وضع التوربو مفعَّل، ضغطة "📋 نسخ" الواحدة بتعمل الأربع خطوات دي
تلقائياً: تنسخ، تسيب البرنامج (Alt+Tab لآخر نافذة كانت شغّالة)، تلصق،
وتضغط Enter.

⚠️ تحذير مهم: ده بيحاكي ضغط لوحة مفاتيح حقيقي على مستوى النظام كله
(مش بس جوه برنامجنا) — لازم يكون نظام المخازن هو *آخر نافذة كانت مفتوحة*
قبل ما ترجع لأداتنا، ولازم يكون فيه خانة إدخال جاهزة تستقبل اللصق فعلاً،
وإلا الـ Enter ممكن يعمل حاجة تانية غير متوقعة في أي نافذة تانية مفتوحة.
شغّاله على ويندوز بس (بيتجاهَل بهدوء على أي نظام تاني).

بديل أدق (لو حابب): بدل Alt+Tab (بيروح لآخر نافذة عشوائياً)، ممكن نستهدف
نافذة بعينها بالاسم (عنوانها) لو قلتلي اسم نافذة برنامج المخازن بالظبط.
"""
import sys
import time

_WINDOWS = sys.platform == "win32"

if _WINDOWS:
    import ctypes

    _user32 = ctypes.windll.user32
    VK_TAB = 0x09
    VK_MENU = 0x12   # Alt
    VK_CONTROL = 0x11
    VK_V = 0x56
    VK_RETURN = 0x0D
    KEYEVENTF_KEYUP = 0x0002

    def _key_down(vk):
        _user32.keybd_event(vk, 0, 0, 0)

    def _key_up(vk):
        _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
else:
    def _key_down(vk):
        pass

    def _key_up(vk):
        pass


def is_available() -> bool:
    """هل وضع التوربو ممكن يشتغل على النظام ده (ويندوز بس)؟"""
    return _WINDOWS


def send_alt_tab():
    """يبدّل لآخر نافذة كانت شغّالة قبل برنامجنا (زي Alt+Tab يدوي بالظبط)."""
    if not _WINDOWS:
        return
    _key_down(VK_MENU)
    time.sleep(0.05)
    _key_down(VK_TAB)
    time.sleep(0.08)
    _key_up(VK_TAB)
    time.sleep(0.05)
    _key_up(VK_MENU)


def send_paste():
    """يحاكي Ctrl+V."""
    if not _WINDOWS:
        return
    _key_down(VK_CONTROL)
    time.sleep(0.02)
    _key_down(VK_V)
    time.sleep(0.05)
    _key_up(VK_V)
    _key_up(VK_CONTROL)


def send_enter():
    """يحاكي ضغطة Enter."""
    if not _WINDOWS:
        return
    _key_down(VK_RETURN)
    time.sleep(0.03)
    _key_up(VK_RETURN)


def run_sequence(root_widget, after_ms_switch=150, after_ms_paste=250, after_ms_enter=120):
    """
    ينفّذ التتابع الكامل (Alt+Tab -> لصق -> Enter) بدون تجميد الواجهة،
    عن طريق جدولة كل خطوة بـ root_widget.after() بدل استخدام time.sleep
    المباشر (اللي كان هيوقف الواجهة كلها لحظياً). root_widget أي عنصر
    Tkinter عنده .after() (النافذة الرئيسية للتطبيق عادةً).
    """
    if not _WINDOWS:
        return
    send_alt_tab()
    root_widget.after(after_ms_switch, lambda: (
        send_paste(),
        root_widget.after(after_ms_enter, send_enter),
    ))
