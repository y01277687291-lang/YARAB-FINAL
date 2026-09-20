# -*- coding: utf-8 -*-
"""ثوابت هوية التطبيق ورقم الإصدار (يُستخدم في التحديث التلقائي)."""

APP_NAME = "YA Pharma Scan"
APP_VERSION = "1.9.3"
APP_AUTHORS_FOOTER = "By Youssef Amr & Aly Amr"

# رابط ملف version.json الذي ينشره المطوّر بعد كل إصدار جديد على GitHub
# (Raw URL لملف في نفس الـ repo، مثال:
#  https://raw.githubusercontent.com/USER/REPO/main/version.json)
# اتركه فارغاً لتعطيل التحقق من التحديثات تلقائياً حتى يتم ضبطه.
DEFAULT_UPDATE_URL = ""

APP_PASSWORD = "YA@AA2026"
TRIAL_PERIOD_DAYS = 30

# قيمة سرية تُستخدم لتحويل كود التفعيل الحقيقي إلى بصمة (hash) قبل تخزينه
# في سجل الأكواد المرفق مع الأداة، بحيث لا يظهر أي كود صريح لأي مستخدم.
# غيّرها لقيمة خاصة بيك، وأعد توليد الأكواد (generate_activation_codes.py)
# بعد أي تغيير هنا حتى تتطابق البصمات مع الأكواد الحقيقية.
LICENSE_SALT = "YA-Pharma-Scan-2AmrBros-Secret-Salt-v1"
