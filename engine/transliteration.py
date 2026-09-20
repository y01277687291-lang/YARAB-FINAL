# -*- coding: utf-8 -*-
"""
المرحلة 3: محرك التعريب الصوتي (Phonetic Transliteration Engine)
-------------------------------------------------------------------
يحوّل الاسم التجاري الصافي (المتبقي بعد القاموس المعجمي) من الإنجليزية
إلى نطق عربي، بخوارزمية "المطابقة من الأطول للأقصر" (Longest Match First):

  1) اللواحق الصيدلية الشهيرة (prazole, statin, cillin ...)
  2) المقاطع المركبة (ph, sh, th, gh, kh, ck, ch)
  3) الحروف الشرطية المعتمدة على السياق (C, G, X, Y, E)
  4) الحروف الفردية المباشرة (باقي الأبجدية)
"""
import re

# اللواحق مرتبة من الأطول للأقصر (نفس الترتيب المطلوب في الوثيقة)
SUFFIXES = [
    ("prazole", "برازول"),
    ("statin", "ستاتين"),
    ("cillin", "سيلين"),
    ("moxil", "موكسيل"),
    ("zole", "زول"),
    ("stat", "ستات"),
    ("mox", "موكس"),
    ("tion", "شن"),
    ("cine", "زين"),
    ("zine", "زين"),
    ("phen", "فين"),
    ("fen", "فين"),
    ("ceph", "سيف"),
    ("cef", "سيف"),
    ("ol", "ول"),   # في نهاية الكلمة فقط
    ("in", "ين"),   # في نهاية الكلمة فقط
]
# التأكد من الترتيب تنازلياً حسب الطول (أمان إضافي بغض النظر عن ترتيب الإدخال)
SUFFIXES.sort(key=lambda pair: len(pair[0]), reverse=True)

DIGRAPHS = {
    "th": "ث",
    "ph": "ف",
    "sh": "ش",
    "gh": "غ",
    "kh": "خ",
    "ck": "ك",
    # "ch" لها معالجة خاصة بالسياق أدناه (ليست ثابتة)
}

DIRECT_MAP = {
    "a": "ا", "b": "ب", "d": "د", "f": "ف", "h": "ه", "i": "ي",
    "j": "ج", "k": "ك", "l": "ل", "m": "م", "n": "ن", "o": "و",
    "p": "ب", "q": "ك", "r": "ر", "s": "س", "t": "ت", "u": "و",
    "v": "ف", "w": "و", "z": "ز",
}


def _transliterate_chars(s: str, limit: int = None) -> str:
    """
    محرك التعريب على مستوى الحروف.
    `limit`: لو أُرسلت، يُعالَج فقط s[0:limit] (حالة وجود لاحقة مفصولة عن
    النهاية)، لكن حروف السياق (c/g بعدهم e|i|y) تظل "تشوف" الحرف الحقيقي
    التالي من الكلمة الكاملة s حتى لو كان هذا الحرف جزءاً من اللاحقة
    المفصولة - وإلا لضاع السياق الصحيح (مثال: GARAMYCIN تُقسَّم إلى جذع
    "garamyc" + لاحقة "in"، فلو نظرنا فقط داخل الجذع لظننا أن c هي آخر
    حرف بلا امتداد فتحوّلت خطأً لـ"ك" بدل "س" الصحيحة لأن التالي الحقيقي i).
    """
    n_full = len(s)
    limit = n_full if limit is None else limit
    out = []
    i = 0
    while i < limit:
        two = s[i:i + 2]

        # ch: تعتمد على الحرف التالي لها (نظرة حقيقية حتى لو تجاوزت limit)
        if two == "ch" and i + 1 < limit:
            nxt = s[i + 2] if i + 2 < n_full else ""
            out.append("ك" if nxt in ("l", "r") else "ش")
            i += 2
            continue

        # باقي المقاطع المركبة الثابتة
        if two in DIGRAPHS and i + 1 < limit:
            out.append(DIGRAPHS[two])
            i += 2
            continue

        ch = s[i]
        is_start = (i == 0)
        is_end = (i == n_full - 1)  # نهاية الكلمة الحقيقية فقط (لا تتحقق أبداً لو limit<n_full)
        nxt_ch = s[i + 1] if i + 1 < n_full else ""  # نظرة للحرف التالي الحقيقي دوماً

        if ch == "c":
            out.append("س" if nxt_ch in ("e", "i", "y") else "ك")
        elif ch == "g":
            # الوثيقة تفرّق بين "ج ناعمة" و"ج جافة" لكن كلاهما بنفس الحرف
            # العربي (ج) — لا فرق في الرسم، فقط في النطق.
            out.append("ج")
        elif ch == "x":
            out.append("ز" if is_start else "كس")
        elif ch == "y":
            out.append("إي" if is_start else "ي")
        elif ch == "e":
            if is_end:
                pass  # يُهمل تماماً في نهاية الكلمة
            elif is_start:
                # حرف علة في بداية الكلمة يحتاج ألف حاملة قبله، وإلا
                # قُرئت كأنها ساكنة. مؤكد من الشيت الحقيقي:
                # Ezogast -> "ايزوجاست" (مش "يزوجاست").
                out.append("اي")
            else:
                out.append("ي")
        elif ch == "i" and is_start:
            # نفس المبدأ: Insulin-type بداية بـ I تحتاج ألف حاملة (اي)
            out.append("اي")
        elif ch in ("o", "u") and is_start:
            # مؤكد من الشيت الحقيقي: Ondalenz -> "اوندالينز" (مش "وندالينز")
            out.append("او")
        elif ch in DIRECT_MAP:
            out.append(DIRECT_MAP[ch])
        elif ch.isdigit():
            out.append(ch)  # أرقام متبقية (نادرة بعد مرحلة التنظيف) تُترك كما هي
        # أي رمز آخر غير معروف يُتجاهل بصمت
        i += 1
    return "".join(out)


def transliterate_word(word: str) -> str:
    """
    يحوّل كلمة إنجليزية واحدة (اسم تجاري) إلى نطق عربي.
    يطبّق أولاً قائمة اللواحق الشهيرة بالأطول فالأقصر، ثم يمرّر الجذع
    المتبقي على محرك الحروف (مع الحفاظ على سياق الحرف الحقيقي عند نقطة
    الفصل بين الجذع واللاحقة).
    """
    w = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not w:
        return word  # كلمة بدون حروف إنجليزية (رمز/رقم) تُترك كما هي

    for suf, ar in SUFFIXES:
        if w == suf:
            return ar
        if w.endswith(suf) and len(w) > len(suf):
            stem_len = len(w) - len(suf)
            return _transliterate_chars(w, limit=stem_len) + ar

    return _transliterate_chars(w)


def transliterate_text(words) -> str:
    """يعرّب قائمة كلمات إنجليزية ويعيدها كنص عربي واحد مفصول بمسافات."""
    return " ".join(transliterate_word(w) for w in words if w)
