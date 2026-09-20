# -*- coding: utf-8 -*-
"""
اختبار سريع لخط الأنابيب الكامل باستخدام قاعدة البيانات الحقيقية وملف
الاستثناءات المرفقين من المستخدم. شغّله بـ:
    python -m tests.test_pipeline
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import PharmaPipeline  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

SAMPLE_INVOICE_LINES = [
    "Panadol Extra 500mg Tab",
    "Amoxicillin 500 mg Cap",
    "Omeprazole 20mg Cap",
    "Atorvastatin 20mg Tab",
    "Vitamin C Effervescent",
    "Baby Shampoo 200ml",
    "Free Sample Cough Syrup",
    "لبن هيرو 2 400 جرام",
    "صابون سولانترا الترا لترطيب البشرة",
    "Ceftriaxone 1g Vial IM",
]


def main():
    pipeline = PharmaPipeline(
        products_path=os.path.join(DATA_DIR, "products.xlsx"),
        exceptions_path=os.path.join(DATA_DIR, "Exceptions.xlsx"),
    )
    print(f"تم تحميل {len(pipeline.matcher)} صنف من قاعدة البيانات.")
    print(f"تم تحميل {len(pipeline.exceptions)} استثناء.")
    print("-" * 70)

    for line in SAMPLE_INVOICE_LINES:
        r = pipeline.process_line(line)
        color_emoji = {"green": "🟩", "yellow": "🟨", "red": "🟥"}[r.color]
        print(f"{color_emoji} [{r.score:5.1f}%] {line!r}")
        print(f"      -> {r.suggested_arabic}   (source={r.source}"
              f"{', code=' + r.matched_code if r.matched_code else ''})")
        if r.debug_transliterated and r.debug_transliterated != r.suggested_arabic:
            print(f"      (تعريب صوتي خام: {r.debug_transliterated})")
    print("-" * 70)


if __name__ == "__main__":
    main()
