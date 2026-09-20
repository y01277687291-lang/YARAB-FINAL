# -*- coding: utf-8 -*-
"""اختبار وحدة وضع التوربو (turbo.py) - يتأكد إنها آمنة تماماً على أي
نظام غير ويندوز (بتتجاهل بهدوء بدل ما تكسر البرنامج)، وإن الدالة
الرئيسية run_sequence مش بترمي أي استثناء حتى من غير نافذة Tkinter حقيقية."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import turbo  # noqa: E402


def test_is_available_matches_platform():
    assert turbo.is_available() == (sys.platform == "win32")


def test_key_functions_never_raise_on_non_windows():
    # على بيئة الاختبار (لينكس) لازم يبقوا no-op آمن تماماً
    turbo.send_alt_tab()
    turbo.send_paste()
    turbo.send_enter()


class _FakeWidget:
    def after(self, _ms, callback):
        callback()  # ينفّذ فوراً بدل جدولة حقيقية - كافي للاختبار


def test_run_sequence_never_raises():
    turbo.run_sequence(_FakeWidget())
