# -*- coding: utf-8 -*-
"""
مولّد أكواد التفعيل (يُشغَّل مرة واحدة من المطوّر لتوليد دفعة أكواد جاهزة)
--------------------------------------------------------------------------
⚠️ سري جداً — لا توزّعه ولا ترفعه مع الأداة أبداً:
  activation_codes.txt هو الوحيد اللي فيه الأكواد الحقيقية صريحة، وهو ملف
  خاص بيك إنت بس (المطوّر) عشان توزّع منه كود لكل عميل. متسيبوش في نفس
  مجلد البرنامج اللي بتوزّعه، ومتضيفوش لأي مستودع Git (تم استبعاده تلقائياً
  في .gitignore).

يُنتج:
  1) activation_codes.txt          — سري، للمطوّر فقط (لا يُوزَّع أبداً).
  2) data/license_registry.json    — آمن للتوزيع مع الأداة: يحتوي فقط على
     "بصمة" (SHA-256 hash) لكل كود، وليس الكود نفسه، فلا يقدر أي مستخدم
     يقرأ منه أكواداً صالحة تانية حتى لو فتح الملف.

شغّله بـ:
    python generate_activation_codes.py [العدد]   # افتراضي 2000 كود
"""
import json
import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth import hash_code  # noqa: E402

OUTPUT_TXT = "activation_codes.txt"
OUTPUT_REGISTRY = os.path.join("data", "license_registry.json")

ALPHABET = string.ascii_uppercase + string.digits


def _random_block(n=4):
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def generate_codes(count: int):
    codes = set()
    while len(codes) < count:
        code = f"YAPS-{_random_block()}-{_random_block()}-{_random_block()}"
        codes.add(code)
    return sorted(codes)


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    codes = generate_codes(count)

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(codes) + "\n")

    os.makedirs("data", exist_ok=True)
    registry = {"hashes": {hash_code(code): {"device_id": None, "activated_at": None} for code in codes}}
    with open(OUTPUT_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    print(f"تم توليد {len(codes)} كود فريد.")
    print(f"  -> {OUTPUT_TXT}  (سري — لا توزّعه أبداً، احتفظ بيه عندك بس)")
    print(f"  -> {OUTPUT_REGISTRY}  (آمن للتوزيع مع الأداة — بصمات فقط)")
    print("انسخ license_registry.json إلى المسار المشترك (shared_folder_path) "
          "قبل توزيع الأداة على أول جهاز، لو بتستخدم مسار مشترك.")


if __name__ == "__main__":
    main()
