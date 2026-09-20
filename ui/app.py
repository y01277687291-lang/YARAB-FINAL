# -*- coding: utf-8 -*-
"""
الواجهة الرسومية الرئيسية (CustomTkinter) — YA Pharma Scan
--------------------------------------------------------------
تطبّق مواصفات القسم 4 من الوثيقة الأصلية، بالإضافة إلى:
  - بوابة دخول: كلمة مرور + كود تفعيل (30 يوماً/جهاز) مع عداد متبقي بارز
  - عمود سعر الفاتورة + عمود الكمية (من الفاتورة) + مؤشر "تحقق بالسعر"
  - استيراد فاتورة واحدة أو عدة فواتير أو فولدر كامل دفعة واحدة، مع
    التنقل بين الفواتير (السابقة/التالية) وعداد "فاتورة X من Y"
  - عداد "نُسخ X من Y صنف" لكل فاتورة + زر "إتمام الفاتورة" + زر "إغلاق"
  - أزرار لكل صنف: نسخ / تعديل / تأكيد كاستثناء دائم / وضع علامة "ناقص"
    (يسجَّل في ملف Missing_Items.xlsx منفصل دون التأثير على الفاتورة) /
    "استبعاد" (Blacklist دائم في Ignored_Items.xlsx لأصناف زي الكوزماتيكس
    والأكياس اللي مش بتتدخل على السيستم أصلاً — تتلوّن رمادياً تلقائياً
    من نفسها في أي فاتورة قادمة بمجرد التعرف عليها)
  - تلوين الصف: أخضر/أصفر/أحمر حسب نسبة الثقة، بنفسجي بعد "تأكيد"
    يدوي، وردي بعد وضع علامة "ناقص"، رمادي للأصناف المستبعدة
  - زر فحص التحديثات (Auto-Update) يحافظ على data/ وsettings.json
  - فوتر "By Youssef Amr & Aly Amr"
  - إصلاح شكل النص العربي (تشكيل + اتجاه صحيح) في كل عناصر الواجهة، لأن
    CustomTkinter/Tkinter على ويندوز ضعيف في عرض العربي المتصل بشكل صحيح
    من تلقاء نفسه (يظهر الحروف منفصلة أو باتجاه معكوس) بدون هذا الإصلاح.
"""
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import PharmaPipeline  # noqa: E402
from pdf_reader import extract_item_rows, extract_invoice_header_text, find_pdf_files_in_folder  # noqa: E402
from settings import (load_settings, save_settings, resolve_exceptions_path, resolve_missing_items_path,
                       resolve_ignored_items_path, resolve_reference_map_path, resolve_controlled_items_path,
                       DATA_DIR)  # noqa: E402
import turbo  # noqa: E402
from version import APP_NAME, APP_VERSION, APP_AUTHORS_FOOTER  # noqa: E402
from auth import LicenseManager, check_password  # noqa: E402
from pharmacy_directory import resolve_pharmacy_name  # noqa: E402
from missing_items import MissingItemsManager  # noqa: E402
from engine.cloud_sync import CloudSync  # noqa: E402
import updater  # noqa: E402

try:
    import pyperclip
    _HAS_CLIPBOARD = True
except ImportError:
    _HAS_CLIPBOARD = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display as _bidi_get_display

    # وضع عرض النص العربي: قابل للتبديل من شاشة الإعدادات (settings.py:
    # arabic_render_mode) لتشخيص مشاكل عرض متكررة بدون تعديل كود. "plain"
    # يمرّر النص الخام بدون أي معالجة (اختبار مباشر: هل عرض ويندوز/Tk
    # الأصلي للعربي كافٍ لوحده على جهاز المستخدم ولا فعلاً محتاج
    # reshape+bidi؟) — القيمة الافتراضية "reshape_bidi" تحافظ على السلوك
    # القديم زي ما هو.
    _ARABIC_RENDER_MODE = ["reshape_bidi"]

    def set_arabic_render_mode(mode: str):
        _ARABIC_RENDER_MODE[0] = mode if mode in ("reshape_bidi", "plain") else "reshape_bidi"

    # الإيموجي (📋 ✏️ ✅ ⚠️ 🚫 ...) مالوش تصنيف اتجاه (bidi class) ثابت في
    # معيار يونيكود، فلو دخل مع نص عربي في نفس نداء bidi.get_display() بيدّي
    # أحياناً ترتيب عرض متكسر (حروف عربية ظاهرة غلط زي "خُسّ" بدل "نسخ" مثلاً)
    # حتى لو النص العربي لوحده كان هيتشكّل صح تماماً. الحل: نفصل أي إيموجي
    # بادئ/لاحق عن السطر *قبل* التشكيل، ونشكّل الجزء العربي بس، وبعدين نلزق
    # الإيموجي في آخر السطر الناتج (يعني هيظهر أقصى اليمين لأي عنصر محاذاته
    # لليمين anchor="e" - وده كل عناصرنا).
    _EMOJI_RUN = re.compile(
        r"(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\u25A0-\u25FF\u2B00-\u2BFF][\uFE0F\u200D]?)+"
    )

    def _ar(text):
        """
        يحوّل أي نص عربي إلى صيغة العرض الصحيحة (تشكيل الحروف المتصلة +
        اتجاه صحيح) قبل عرضه في أي عنصر بالواجهة — لازم لأن Tkinter/
        CustomTkinter على ويندوز مفيهوش دعم كافٍ لعرض العربي المتصل
        تلقائياً، فبيظهر الحروف منفصلة أو النص معكوس الاتجاه. هذا التحويل
        للعرض المرئي فقط: كل عمليات النسخ/الحفظ/المطابقة الداخلية بتستخدم
        النص الأصلي السليم دايماً (غير مُعاد تشكيله).
        لو arabic_render_mode == "plain"، بيرجع النص الخام زي ما هو (راجع
        set_arabic_render_mode أعلاه).
        """
        if not text:
            return text
        if _ARABIC_RENDER_MODE[0] == "plain":
            return text
        try:
            def process_line(line):
                if not line:
                    return line
                emojis = _EMOJI_RUN.findall(line)
                core = _EMOJI_RUN.sub("", line).strip()
                if not core:
                    return line  # سطر إيموجي بس، مفيش عربي نشكّله أصلاً
                reshaped = _bidi_get_display(arabic_reshaper.reshape(core))
                if emojis:
                    return reshaped + " " + " ".join(emojis)
                return reshaped

            return "\n".join(process_line(line) for line in str(text).split("\n"))
        except Exception:
            return text
except ImportError:
    def _ar(text):
        return text

    def set_arabic_render_mode(mode: str):
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# خط الواجهة الافتراضي لأي عنصر عربي: CustomTkinter بيستخدم خط افتراضي
# مُجمَّع مع المكتبة (شبه "Roboto") لو معنديناش font= صريح — وهو خط ملوش
# تغطية كافية لحروف "أشكال العرض العربية" (Arabic Presentation Forms) اللي
# arabic_reshaper بيحوّلها ليها، فبتظهر الحروف مفكوكة عن بعض/غلط رغم إن
# النص نفسه بعد _ar() سليم منطقياً ومُرتَّب صح (اتأكّد بالاختبار المباشر).
# "Segoe UI" (خط ويندوز الافتراضي من فيستا) عنده تغطية عربية كاملة بما
# فيها أشكال العرض، ونفس الخط المستخدم فعلاً في جدول ttk.Treeview اللي
# بيظهر فيه النص صح تماماً بالفعل.
ARABIC_FONT_FAMILY = "Segoe UI"
ARABIC_FONT_DEFAULT_SIZE = 13


def _clean_copy_text(text: str) -> str:
    """
    يشيل أي مسافات زايدة (بادئة/لاحقة، أو مسافتين متتاليتين جوه النص) قبل
    النسخ/الاعتماد النهائي — مسافة زايدة واحدة كافية إن نظام المخازن ميلقاش
    الصنف مطابق تماماً حتى لو الاسم نفسه صح 100%. ملحوظة: ما بيتطبقش أثناء
    الكتابة الحية (على كل ضغطة زر) عشان ميمسحش مسافة فاصلة بين كلمتين
    المستخدم لسه بيكتبها — بس عند النسخ الفعلي أو عند اعتماد التعديل نهائياً.
    """
    return re.sub(r"\s+", " ", (text or "").strip())


def _Label(*args, **kwargs):
    """بديل عن ctk.CTkLabel بيضمن خط عربي سليم افتراضياً (بدون التأثير على
    أي استدعاء بيحدد font= بنفسه صراحة، زي العناوين الكبيرة بخط مخصوص)."""
    kwargs.setdefault("font", (ARABIC_FONT_FAMILY, ARABIC_FONT_DEFAULT_SIZE))
    return ctk.CTkLabel(*args, **kwargs)


def _Button(*args, **kwargs):
    """بديل عن ctk.CTkButton بنفس فكرة _Label أعلاه."""
    kwargs.setdefault("font", (ARABIC_FONT_FAMILY, ARABIC_FONT_DEFAULT_SIZE))
    return ctk.CTkButton(*args, **kwargs)


COLOR_HEX_LIGHT = {
    # ألوان أغمق/أكثر تشبّعاً من النسخة القديمة (كانت باهتة جداً وصعب
    # تمييزها عن بعض بسرعة في جدول مزدحم) - نفس الفكرة، تباين أوضح بس.
    "green": "#8FE3A8",
    "yellow": "#FFE066",
    "red": "#FF9B9B",
    "confirmed": "#C9A6F5",   # بنفسجي: صنف اتأكّد يدوياً (زر ✅ تأكيد)
    "ignored": "#ABABAB",     # رمادي: صنف مُستبعد (Blacklist) - مش هيتدخل على السيستم
    "controlled": "#FF7A00",  # برتقالي صارخ: صنف من "الأصناف المهمة" (أدوية جدول) - انتبه!
}

def _resource_root() -> str:
    """جذر البحث عن ملفات الموارد (زي الأيقونة). لازم يتعامل صح مع الحالة
    المُجمَّعة (PyInstaller onefile): وقتها الملفات بتتفك مؤقتاً في
    sys._MEIPASS، مش جنب __file__ العادي — استخدام __file__ وحده هنا كان
    هو سبب اختفاء الأيقونة من شريط العنوان/المهام رغم ظهورها على الـ exe
    نفسه من الخارج (المسار كان بيتحسب غلط جوه البناء المُجمَّع)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_PROJECT_ROOT = _resource_root()
ICON_ICO_PATH = os.path.join(_PROJECT_ROOT, "app_icon.ico")
# نستخدم نسخ مُصغَّرة مُجهَّزة مسبقاً (32/48 بكسل) بدل الصورة المصدرية
# الأصلية (1024×1024) لأيقونة النافذة (iconphoto) — تمرير صورة ضخمة
# لعنصر بحجم شريط العنوان الصغير كان بيخلّي Tk يصغّرها وقت العرض
# بجودة رديئة (تظهر مبكسلة/ضبابية)، بعكس تصغير عالي الجودة (LANCZOS)
# جاهز مسبقاً في الصور دي.
ICON_PNG_SMALL_PATH = os.path.join(_PROJECT_ROOT, "app_icon_32.png")
ICON_PNG_MEDIUM_PATH = os.path.join(_PROJECT_ROOT, "app_icon_48.png")


def _log_icon_issue(message: str):
    """يسجّل أي مشكلة في تطبيق الأيقونة في ملف تشخيصي بسيط جنب settings.json
    (بدل تجاهلها بصمت) — لو الأيقونة لسه مش ظاهرة جوه البرنامج، افتح
    data/icon_debug.log وابعتلي محتواه عشان نعرف السبب بالظبط."""
    try:
        log_path = os.path.join(DATA_DIR, "icon_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
    except Exception:
        pass


def _apply_icon(window):
    """
    يضبط أيقونة النافذة نفسها (مش بس أيقونة ملف الـ exe في الويندوز/الـ
    Explorer). CustomTkinter أحياناً يعيد ضبط الأيقونة الافتراضية بعد
    التهيئة، فبنطبّقها فوراً وبعد تأخير بسيط (after) لضمان ثباتها.
    """
    def _set():
        _log_icon_issue(
            f"--- icon attempt: frozen={getattr(sys, 'frozen', False)} "
            f"PROJECT_ROOT={_PROJECT_ROOT} ico_exists={os.path.exists(ICON_ICO_PATH)} "
            f"png32_exists={os.path.exists(ICON_PNG_SMALL_PATH)} "
            f"png48_exists={os.path.exists(ICON_PNG_MEDIUM_PATH)} ---"
        )
        if not os.path.exists(ICON_ICO_PATH):
            _log_icon_issue(f"ICON_ICO_PATH not found: {ICON_ICO_PATH}")
        else:
            try:
                window.iconbitmap(ICON_ICO_PATH)
            except Exception as exc:
                _log_icon_issue(f"iconbitmap failed for {ICON_ICO_PATH}: {exc!r}")
        try:
            imgs = []
            for path in (ICON_PNG_SMALL_PATH, ICON_PNG_MEDIUM_PATH):
                if os.path.exists(path):
                    imgs.append(tk.PhotoImage(file=path))
                else:
                    _log_icon_issue(f"icon png not found: {path}")
            if imgs:
                window.iconphoto(True, *imgs)
                window._icon_img_refs = imgs  # الاحتفاظ بمرجع يمنع جمع القمامة لها
        except Exception as exc:
            _log_icon_issue(f"iconphoto failed: {exc!r}")

    _set()
    try:
        # CustomTkinter بيعيد ضبط الأيقونة الافتراضية أكتر من مرة أثناء
        # التهيئة (مش مرة واحدة بس) على بعض الأجهزة/إصدارات ويندوز -
        # فبنعيد المحاولة على فترات متباعدة تغطي أول ثانيتين من عمر
        # النافذة، بدل محاولة واحدة بعد 200ms ممكن تتجاوزها إعادة ضبط لاحقة.
        for delay_ms in (200, 500, 1000, 2000):
            window.after(delay_ms, _set)
        window.bind("<Map>", lambda _e: _set(), add="+")
    except Exception:
        pass


# ============================================================ بوابة الدخول
class AuthGate(ctk.CTk):
    """نافذة تسجيل الدخول: كلمة مرور ثم كود تفعيل (لو لازم)."""

    def __init__(self, settings: dict):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("460x300")
        self.resizable(False, False)
        _apply_icon(self)

        self.settings = settings
        set_arabic_render_mode(settings.get("arabic_render_mode", "plain"))
        self.license_manager = LicenseManager(settings, cloud=CloudSync(settings.get("cloud_sync_url", "")))
        self.authenticated = False
        self.activation_info = None

        self._build_password_step()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _build_password_step(self):
        self._clear()
        _Label(self, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(pady=(30, 10))
        _Label(self, text=_ar("من فضلك أدخل كلمة المرور للمتابعة:")).pack(pady=(0, 8))
        self.pw_var = tk.StringVar()
        entry = ctk.CTkEntry(self, textvariable=self.pw_var, show="*", width=240, justify="center")
        entry.pack(pady=6)
        entry.bind("<Return>", lambda e: self._check_password())
        entry.focus()
        self.pw_error = _Label(self, text="", text_color="#e06666")
        self.pw_error.pack(pady=4)
        _Button(self, text=_ar("دخول"), command=self._check_password).pack(pady=10)

    def _check_password(self):
        if check_password(self.pw_var.get()):
            self._build_activation_step()
        else:
            self.pw_error.configure(text=_ar("كلمة المرور غير صحيحة."))

    def _build_activation_step(self):
        current = self.license_manager.current_activation()
        if current:
            self.authenticated = True
            self.activation_info = current
            self.destroy()
            return

        self._clear()
        _Label(self, text=_ar("تفعيل الأداة"), font=("Segoe UI", 20, "bold")).pack(pady=(30, 10))
        _Label(self, text=_ar("أدخل كود التفعيل الخاص بك (صالح 30 يوماً من الآن):")).pack(pady=(0, 8))
        self.code_var = tk.StringVar()
        entry = ctk.CTkEntry(self, textvariable=self.code_var, width=280, justify="center")
        entry.pack(pady=6)
        entry.bind("<Return>", lambda e: self._check_activation())
        entry.focus()
        self.act_error = _Label(self, text="", text_color="#e06666", wraplength=380)
        self.act_error.pack(pady=4)
        _Button(self, text=_ar("تفعيل"), command=self._check_activation).pack(pady=10)

    def _check_activation(self):
        ok, msg = self.license_manager.activate(self.code_var.get())
        if ok:
            # activate() ممكن يرجع True لمجرد إن الكود ده اتفعّل قبل كده
            # على نفس الجهاز (حالة idempotent) - من غير ما يجدد التاريخ.
            # لازم نتأكد إن التفعيل ده لسه فعلاً سارٍ (مش منتهي) قبل ما
            # نفتح البرنامج، وإلا كان ممكن حد يلف الـ30 يوم بمجرد إعادة
            # كتابة نفس الكود القديم تاني من غير كود جديد فعلاً.
            current = self.license_manager.current_activation()
            if current:
                self.authenticated = True
                self.activation_info = current
                self.destroy()
            else:
                self.act_error.configure(text=_ar(
                    "هذا الكود سبق استخدامه على هذا الجهاز وانتهت مدة الـ30 يوماً بالفعل. "
                    "من فضلك استخدم كوداً جديداً لتفعيل مدة إضافية."
                ))
        else:
            self.act_error.configure(text=_ar(msg))


def run_auth_gate(settings: dict):
    gate = AuthGate(settings)
    gate.mainloop()
    return gate.authenticated, gate.activation_info


# ================================================================ الإعدادات
class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: dict, on_save):
        super().__init__(master)
        self.title(_ar("الإعدادات"))
        self.geometry("700x680")
        self.minsize(600, 420)
        _apply_icon(self)
        self.settings = dict(settings)
        self.on_save = on_save

        self.products_var = tk.StringVar(value=self.settings.get("products_path", ""))
        self.exceptions_var = tk.StringVar(value=self.settings.get("exceptions_path", ""))
        self.shared_var = tk.StringVar(value=self.settings.get("shared_folder_path", ""))
        self.threshold_var = tk.DoubleVar(value=self.settings.get("match_threshold", 80.0))
        self.price_tol_var = tk.DoubleVar(value=self.settings.get("price_match_tolerance", 1.0))
        self.price_bonus_var = tk.DoubleVar(value=self.settings.get("price_match_bonus", 10.0))
        self.update_url_var = tk.StringVar(value=self.settings.get("update_url", ""))
        self.cloud_url_var = tk.StringVar(value=self.settings.get("cloud_sync_url", ""))
        self.arabic_mode_var = tk.StringVar(
            value=_ar("عرض عربي عادي (افتراضي)")
            if self.settings.get("arabic_render_mode", "plain") == "reshape_bidi"
            else _ar("عرض بديل (نص خام بدون معالجة)")
        )

        # عناصر الإعدادات كلها جوه فريم قابل للتمرير (Scroll) — عشان لو
        # عدد الإعدادات زاد أو الشاشة صغيرة، تفضل كل الأزرار (زي تصفير
        # النواقص والحفظ) ظاهرة ومتاحة دايماً، مش مقطوعة برة حدود النافذة
        # من غير ما المستخدم ياخد باله إنه محتاج يكبّر الشباك يدوياً.
        self.body = ctk.CTkScrollableFrame(self, width=660, height=560)
        self.body.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=(0, 10))

        body = self.body
        pad = {"padx": 14, "pady": 6}
        row = 0

        _Label(body, text=_ar("مسار شيت الأصناف (Excel/CSV):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.products_var, width=320).grid(row=row, column=1, **pad)
        _Button(body, text=_ar("استعراض"), width=80, command=self._browse_products).grid(row=row, column=2, **pad)
        row += 1

        _Label(body, text=_ar("مسار الاستثناءات المحلي (احتياطي):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.exceptions_var, width=320).grid(row=row, column=1, **pad)
        _Button(body, text=_ar("استعراض"), width=80, command=self._browse_exceptions).grid(row=row, column=2, **pad)
        row += 1

        _Label(body, text=_ar("📁 المجلد المشترك (شبكة/Drive) للاستثناءات\nوسجل التفعيل — يظهر فوراً لكل الأجهزة:"),
                     justify="right").grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.shared_var, width=320).grid(row=row, column=1, **pad)
        _Button(body, text=_ar("استعراض"), width=80, command=self._browse_shared).grid(row=row, column=2, **pad)
        row += 1

        _Label(body, text=_ar("حد نسبة المطابقة الأدنى (%):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.threshold_var, width=100).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        _Label(body, text=_ar("سماحية فرق السعر (جنيه):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.price_tol_var, width=100).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        _Label(body, text=_ar("زيادة الثقة عند تطابق السعر (%):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.price_bonus_var, width=100).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        _Label(body, text=_ar("رابط التحديث التلقائي (version.json):")).grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkEntry(body, textvariable=self.update_url_var, width=320).grid(row=row, column=1, **pad)
        row += 1

        _Label(body, text=_ar("☁️ رابط المزامنة السحابية (اختياري):")).grid(row=row, column=0, sticky="e", **pad)
        cloud_frame = ctk.CTkFrame(body, fg_color="transparent")
        cloud_frame.grid(row=row, column=1, sticky="w", **pad)
        ctk.CTkEntry(cloud_frame, textvariable=self.cloud_url_var, width=230).pack(side="left")
        self.cloud_test_label = _Label(cloud_frame, text="", text_color="#a0a0a0")
        _Button(cloud_frame, text=_ar("اختبار"), width=70, command=self._test_cloud).pack(side="left", padx=(6, 6))
        row += 1
        self.cloud_test_label.grid(row=row, column=0, columnspan=2, sticky="e", padx=14)
        row += 1
        _Label(body, text=_ar(
            "(اختياري: بيربط كل الأجهزة ببعض - تأكيد/استبعاد صنف على جهاز يظهر فوراً "
            "عند باقي الأجهزة حتى لو على شبكات منفصلة تماماً. راجع engine/cloud_sync.py "
            "للتعليمات - نفس الرابط لازم يتحط في كل الأجهزة.)"
        ), text_color="#a0a0a0", justify="right", wraplength=520).grid(
            row=row, column=0, columnspan=2, sticky="e", padx=14, pady=(0, 6))
        row += 1

        _Label(body, text=_ar("🔤 وضع عرض النص العربي (لو النص لسه بايظ):"),
                     justify="right").grid(row=row, column=0, sticky="e", **pad)
        ctk.CTkOptionMenu(
            body, variable=self.arabic_mode_var,
            values=[_ar("عرض عربي عادي (افتراضي)"), _ar("عرض بديل (نص خام بدون معالجة)")],
            width=260,
        ).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        _Label(body, text=_ar("(التغيير ده محتاج إغلاق البرنامج وفتحه تاني عشان يظهر بالكامل)"),
                     text_color="#a0a0a0", justify="right").grid(row=row, column=0, columnspan=2, sticky="e", padx=14)
        row += 1

        # ---- تصفير شيت النواقص (بعد سحبه ومراجعته دورياً) ----
        missing_count = self.master.missing_manager.count() if hasattr(self.master, "missing_manager") else 0
        reset_frame = ctk.CTkFrame(body)
        reset_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))
        _Label(reset_frame, text=_ar(f"🗑️ شيت النواقص حالياً فيه {missing_count} صنف")).pack(side="right", padx=10, pady=8)
        _Button(reset_frame, text=_ar("تصفير شيت النواقص"), fg_color="#a03030", hover_color="#c04040",
                command=self._clear_missing_items).pack(side="right", padx=10)
        row += 1

        # ---- مفتاح الخريطة (Legend): توضيح دلالة كل لون تلوين صف بالجدول ----
        legend_frame = ctk.CTkFrame(body)
        legend_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=14, pady=(4, 14))
        _Label(legend_frame, text=_ar("🎨 مفتاح الألوان (Legend):"),
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="e", padx=10, pady=(8, 4))
        legend_items = [
            ("controlled", "برتقالي 🔒 — صنف من قائمة الأصناف المهمة (أدوية جدول) - أولوية فوق أي لون تاني"),
            ("green", "أخضر — تطابق تام/عالي الثقة، جاهز للنسخ مباشرة"),
            ("yellow", "أصفر — تطابق تقريبي، يحتاج مراجعة قبل النسخ"),
            ("red", "أحمر — بلا تطابق كافٍ، يحتاج تدخل يدوي"),
            ("confirmed", "بنفسجي — اتأكّد يدوياً (زر ✅ تأكيد) وحُفظ كاستثناء دائم"),
            ("ignored", "رمادي — مُستبعد (زر 🚫 استبعاد): دائم ويترمّز تلقائياً بنفس اللون في كل الفواتير القادمة"),
        ]
        for i, (color, desc) in enumerate(legend_items, start=1):
            swatch = ctk.CTkFrame(legend_frame, width=22, height=16, fg_color=COLOR_HEX_LIGHT[color])
            swatch.grid(row=i, column=1, sticky="e", padx=(6, 10), pady=2)
            swatch.grid_propagate(False)
            _Label(legend_frame, text=_ar(desc), justify="right").grid(row=i, column=0, sticky="e", padx=10, pady=2)
        note = ("⚠️ ناقص: مجرد تسجيل بيانات الصنف في شيت متابعة منفصل (Missing_Items.xlsx) "
                "— لا يغيّر لون الصف الآن ولا مستقبلاً (بعكس الاستبعاد الدائم أعلاه).")
        _Label(legend_frame, text=_ar(note), justify="right", wraplength=520,
                     text_color="#a0a0a0").grid(row=len(legend_items) + 1, column=0, columnspan=2,
                                                 sticky="e", padx=10, pady=(6, 10))

        # زرار الحفظ ثابت في الأسفل دايماً (برة منطقة التمرير) - ظاهر
        # طول الوقت مهما كان طول المحتوى فوق.
        _Button(footer, text=_ar("💾 حفظ"), height=38, command=self._save).pack(fill="x")

    def _browse_products(self):
        path = filedialog.askopenfilename(title="اختر شيت الأصناف", filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")])
        if path:
            self.products_var.set(path)

    def _browse_exceptions(self):
        path = filedialog.askopenfilename(title="اختر ملف الاستثناءات", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.exceptions_var.set(path)

    def _browse_shared(self):
        path = filedialog.askdirectory(title="اختر المجلد المشترك")
        if path:
            self.shared_var.set(path)

    def _clear_missing_items(self):
        if not hasattr(self.master, "missing_manager"):
            return
        mgr = self.master.missing_manager
        count = mgr.count()
        if count == 0:
            messagebox.showinfo(_ar("تصفير شيت النواقص"), _ar("شيت النواقص فاضي أصلاً - مفيش حاجة تتصفَّر."))
            return
        confirmed = messagebox.askyesno(
            _ar("تصفير شيت النواقص"),
            _ar(f"هيتم حذف كل الـ{count} صنف المسجَّلين في شيت النواقص نهائياً "
                "(بعد ما سحبته وراجعته). الفاتورة الحالية والاستثناءات والاستبعاد مش هيتأثروا. متأكد؟"),
        )
        if not confirmed:
            return
        try:
            mgr.clear()
            messagebox.showinfo(_ar("تم"), _ar("تم تصفير شيت النواقص بنجاح."))
        except Exception as exc:
            messagebox.showwarning(_ar("تعذّر التصفير"), f"{exc}")

    def _test_cloud(self):
        from engine.cloud_sync import CloudSync
        cloud = CloudSync(self.cloud_url_var.get().strip())
        ok, msg = cloud.test_connection()
        self.cloud_test_label.configure(text=_ar(msg), text_color=("#7fd97f" if ok else "#e06666"))

    def _save(self):
        self.settings["products_path"] = self.products_var.get().strip()
        self.settings["exceptions_path"] = self.exceptions_var.get().strip()
        self.settings["shared_folder_path"] = self.shared_var.get().strip()
        self.settings["update_url"] = self.update_url_var.get().strip()
        self.settings["cloud_sync_url"] = self.cloud_url_var.get().strip()
        try:
            self.settings["match_threshold"] = float(self.threshold_var.get())
            self.settings["price_match_tolerance"] = float(self.price_tol_var.get())
            self.settings["price_match_bonus"] = float(self.price_bonus_var.get())
        except (tk.TclError, ValueError):
            pass
        self.settings["arabic_render_mode"] = (
            "reshape_bidi" if self.arabic_mode_var.get() == _ar("عرض عربي عادي (افتراضي)") else "plain"
        )
        self.on_save(self.settings)
        self.destroy()


# ==================================================================== App
class App(ctk.CTk):
    def __init__(self, activation_info=None):
        super().__init__()
        self.title(f"{APP_NAME} (v{APP_VERSION})")
        self.settings = load_settings()
        set_arabic_render_mode(self.settings.get("arabic_render_mode", "plain"))
        self.geometry(self.settings.get("window_geometry", "1150x680"))
        _apply_icon(self)

        self.activation_info = activation_info
        self.cloud = CloudSync(self.settings.get("cloud_sync_url", ""))

        effective_exceptions_path = resolve_exceptions_path(self.settings)
        self.pipeline = PharmaPipeline(
            products_path=self.settings.get("products_path"),
            exceptions_path=effective_exceptions_path,
            match_threshold=self.settings.get("match_threshold", 80.0),
            price_tolerance=self.settings.get("price_match_tolerance", 1.0),
            price_bonus=self.settings.get("price_match_bonus", 10.0),
            ignored_path=resolve_ignored_items_path(self.settings),
            reference_map_path=resolve_reference_map_path(self.settings),
            controlled_items_path=resolve_controlled_items_path(self.settings),
            cloud=self.cloud,
        )
        self.missing_manager = MissingItemsManager(resolve_missing_items_path(self.settings))

        # دفعة الفواتير الحالية (يمكن تكون فاتورة واحدة أو فولدر كامل)
        self.invoices = []          # كل عنصر: dict فيه path/results/copied/completed/pharmacy/edited
        self.current_index = None   # فهرس الفاتورة المعروضة حالياً في self.invoices
        self._editing_entry = None  # خانة التعديل المباشر المفتوحة حالياً (لو موجودة)

        self._build_top_bar()
        self._build_nav_bar()
        self._build_table()
        self._build_status_bar()
        self._bind_shortcuts()
        self._show_idle_state()

    # ------------------------------------------------------------------ UI
    def _build_top_bar(self):
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=10, pady=(10, 4))

        _Button(bar, text=_ar("📁 استيراد فولدر فواتير"), command=self.import_folder).pack(side="right", padx=6)
        _Button(bar, text=_ar("📄 استيراد فاتورة/فواتير"), command=self.import_files).pack(side="right", padx=6)
        _Button(bar, text=_ar("⚙️ الإعدادات"), command=self.open_settings).pack(side="right", padx=6)
        _Button(bar, text=_ar("🔄 فحص التحديثات"), command=self.check_updates).pack(side="right", padx=6)

        self.db_status_label = _Label(bar, text=_ar(self._db_status_text()))
        self.db_status_label.pack(side="left", padx=6)

        self.turbo_mode_var = tk.BooleanVar(value=bool(self.settings.get("turbo_mode", False)) and turbo.is_available())
        turbo_switch = ctk.CTkSwitch(
            bar, text=_ar("⚡ وضع التوربو"), variable=self.turbo_mode_var,
            command=self._on_turbo_toggle, font=(ARABIC_FONT_FAMILY, ARABIC_FONT_DEFAULT_SIZE),
        )
        turbo_switch.pack(side="left", padx=(16, 6))
        if not turbo.is_available():
            turbo_switch.configure(state="disabled")
            _Label(bar, text=_ar("(التوربو متاح على ويندوز بس)"), text_color="#a0a0a0").pack(side="left")

        if self.activation_info:
            days = self.activation_info.get("days_left", 0)
            self.days_left_label = _Label(
                bar, text=_ar(f"⏳ الأيام المتبقية: {days:.1f} يوم"),
                text_color="#f0c14b", font=("Segoe UI", 12, "bold"),
            )
            self.days_left_label.pack(side="left", padx=16)

    def _build_nav_bar(self):
        """شريط ثانٍ: التنقل بين الفواتير + اسم الصيدلية + عداد النسخ + إتمام/إغلاق."""
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=10, pady=(0, 8))

        _Button(bar, text=_ar("◀ السابقة"), width=90, command=self.show_previous_invoice).pack(side="right", padx=4)
        _Button(bar, text=_ar("التالية ▶"), width=90, command=self.show_next_invoice).pack(side="right", padx=4)

        self.nav_label = _Label(bar, text=_ar("لا توجد فواتير محمّلة"), font=("Segoe UI", 12, "bold"))
        self.nav_label.pack(side="right", padx=16)

        _Button(bar, text=_ar("❌ إغلاق الفاتورة"), width=120, fg_color="#7a2222",
                      hover_color="#932a2a", command=self.close_current_invoice).pack(side="left", padx=4)
        _Button(bar, text=_ar("✅ إتمام الفاتورة"), width=130, fg_color="#1f6e3d",
                      hover_color="#268a4c", command=self.complete_current_invoice).pack(side="left", padx=4)

        self.copied_count_label = _Label(bar, text="", font=("Segoe UI", 12, "bold"), text_color="#7fd4ff")
        self.copied_count_label.pack(side="left", padx=16)

        self.pharmacy_label = _Label(
            bar, text=_ar("🏥 لم يتم استيراد فاتورة بعد"),
            font=("Segoe UI", 13, "bold"), text_color="#7fd4ff",
        )
        self.pharmacy_label.pack(side="left", padx=16)

    def _db_status_text(self):
        return (f"قاعدة الأصناف: {len(self.pipeline.matcher)} صنف   |   "
                f"الاستثناءات: {len(self.pipeline.exceptions) if self.pipeline.exceptions else 0}")

    def _build_table(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b",
                         foreground="white", rowheight=30, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[("selected", "#3a6ea5")])

        columns = ("idx", "english", "invoice_price", "arabic", "quantity", "score",
                   "copy_action", "edit_action", "confirm_action", "missing_action", "ignore_action")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        headings = {
            "idx": "#", "english": _ar("الاسم الأصلي من Odoo"), "invoice_price": _ar("سعر الفاتورة"),
            "arabic": _ar("الاسم العربي المطابق (قابل للتعديل)"), "quantity": _ar("الكمية"),
            "score": _ar("نسبة الثقة"),
            "copy_action": _ar("نسخ"), "edit_action": _ar("تعديل"), "confirm_action": _ar("تأكيد"),
            "missing_action": _ar("ناقص"), "ignore_action": _ar("استبعاد"),
        }
        widths = {"idx": 40, "english": 240, "invoice_price": 90, "arabic": 290,
                  "quantity": 70, "score": 100,
                  "copy_action": 70, "edit_action": 75, "confirm_action": 75, "missing_action": 70,
                  "ignore_action": 80}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "center" if col not in ("english", "arabic") else "e"
            self.tree.column(col, width=widths[col], anchor=anchor)

        # خريطة عمود -> الإجراء المطلوب، مبنية من ترتيب الأعمدة نفسه (مش
        # أرقام ثابتة زي "#7") عشان تفضل صحيحة حتى لو اتغيّر ترتيب الأعمدة
        # لاحقاً. هذا التصميم بعمود مستقل لكل إجراء (بدل نص واحد مقسوم على
        # 3 أجزاء بالعرض) هو الحل الجذري لمشكلة حقيقية اكتُشفت: تشكيل
        # النص العربي للعرض (bidi) بيقلب ترتيب الكلمات المرئي، فكانت
        # المساحات الثابتة (يسار/وسط/يمين) بتشاور على الزرار الغلط.
        self._action_column_ids = {
            f"#{columns.index('copy_action') + 1}": self._copy_row,
            f"#{columns.index('edit_action') + 1}": self._inline_edit,
            f"#{columns.index('confirm_action') + 1}": self._save_row_as_exception,
            f"#{columns.index('missing_action') + 1}": self._mark_row_missing,
            f"#{columns.index('ignore_action') + 1}": self._mark_row_ignored,
        }

        for color, hexcode in COLOR_HEX_LIGHT.items():
            self.tree.tag_configure(color, background=hexcode, foreground="#000000")
        self.tree.tag_configure("copied", background="#3a5a4a", foreground="#ffffff")

        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value=_ar("جاهز. استورد فاتورة أو فولدر فواتير للبدء."))
        bar = ctk.CTkFrame(self, height=30)
        bar.pack(fill="x", side="bottom")
        _Label(bar, textvariable=self.status_var, anchor="w").pack(side="right", fill="x", expand=True, padx=10)
        _Label(bar, text=APP_AUTHORS_FOOTER, anchor="w",
                     font=("Segoe UI", 9), text_color="#888888").pack(side="left", padx=10)

    def _bind_shortcuts(self):
        self.bind("<space>", self._shortcut_copy_and_next)
        self.bind("<Return>", self._shortcut_copy_and_next)
        self.bind("<Control-e>", self._shortcut_inline_edit)
        self.bind("<Control-s>", self._shortcut_save_exception)
        self.bind("<Control-m>", self._shortcut_mark_missing)
        self.bind("<Control-i>", self._shortcut_mark_ignored)
        self.bind("<Down>", self._shortcut_move_down)
        self.bind("<Up>", self._shortcut_move_up)
        self.bind("<Prior>", lambda e: self.show_previous_invoice())   # Page Up
        self.bind("<Next>", lambda e: self.show_next_invoice())        # Page Down

    # ------------------------------------------------------------- إعدادات
    def open_settings(self):
        SettingsDialog(self, self.settings, self._on_settings_saved)

    def _on_settings_saved(self, new_settings: dict):
        self.settings = new_settings
        save_settings(self.settings)
        set_arabic_render_mode(self.settings.get("arabic_render_mode", "plain"))
        self.cloud = CloudSync(self.settings.get("cloud_sync_url", ""))
        self.pipeline.cloud = self.cloud
        self.pipeline.reload_products(self.settings.get("products_path"))
        self.pipeline.reload_exceptions(resolve_exceptions_path(self.settings))
        self.pipeline.reload_ignored(resolve_ignored_items_path(self.settings))
        self.pipeline.reload_reference_map(resolve_reference_map_path(self.settings))
        self.pipeline.reload_controlled_items(resolve_controlled_items_path(self.settings))
        self.missing_manager = MissingItemsManager(resolve_missing_items_path(self.settings))
        self.pipeline.match_threshold = self.settings.get("match_threshold", 80.0)
        self.pipeline.price_tolerance = self.settings.get("price_match_tolerance", 1.0)
        self.pipeline.price_bonus = self.settings.get("price_match_bonus", 10.0)
        self.db_status_label.configure(text=_ar(self._db_status_text()))
        self.status_var.set(_ar("تم تحديث الإعدادات وإعادة تحميل قواعد البيانات."))

    # -------------------------------------------------------- تحديث تلقائي
    def check_updates(self):
        update_url = self.settings.get("update_url", "")
        if not update_url:
            messagebox.showinfo("التحديثات", "لم يتم ضبط رابط التحديث بعد من شاشة الإعدادات.")
            return
        self.status_var.set(_ar("جاري التحقق من وجود إصدار جديد..."))
        self.update_idletasks()
        info = updater.check_for_update(update_url)
        if not info:
            messagebox.showinfo("التحديثات", "أنت تستخدم أحدث إصدار بالفعل.")
            self.status_var.set(_ar("جاهز."))
            return

        if not messagebox.askyesno(
            "يوجد تحديث جديد",
            f"الإصدار المتاح: {info.get('version')}\n{info.get('notes', '')}\n\nهل تريد التحديث الآن؟",
        ):
            return

        ok = updater.download_and_apply_update(info["url"])
        if ok:
            messagebox.showinfo("جاري التحديث", "سيتم إغلاق البرنامج وتحديثه تلقائياً الآن.")
            self.destroy()
        else:
            messagebox.showwarning(
                "تعذّر التحديث",
                "تعذّر تنزيل/تطبيق التحديث تلقائياً (قد يكون بسبب تشغيل الأداة كسكريبت بايثون "
                "وليس كملف .exe، أو مشكلة في الاتصال). يمكنك تنزيل آخر إصدار يدوياً من GitHub.",
            )

    # ----------------------------------------------------------- استيراد
    def import_files(self):
        """يفتح حوار اختيار ملفات يسمح باختيار فاتورة واحدة أو عدة فواتير معاً."""
        paths = filedialog.askopenfilenames(
            title="اختر فاتورة PDF واحدة أو أكثر", filetypes=[("PDF", "*.pdf")],
        )
        if not paths:
            return
        self._load_invoices(list(paths))

    def import_folder(self):
        """يفتح حوار اختيار فولدر، ويحمّل كل فواتير PDF الموجودة بداخله دفعة واحدة."""
        folder = filedialog.askdirectory(title="اختر فولدر يحتوي على فواتير PDF")
        if not folder:
            return
        pdf_paths = find_pdf_files_in_folder(folder)
        if not pdf_paths:
            messagebox.showwarning("لا توجد فواتير", "لم يتم العثور على أي ملف PDF داخل هذا الفولدر.")
            return
        self._load_invoices(pdf_paths)

    def _load_invoices(self, paths):
        self.status_var.set(_ar(f"جاري معالجة {len(paths)} فاتورة..."))
        self.update_idletasks()

        loaded = []
        failed = []
        for path in paths:
            try:
                raw_rows = extract_item_rows(path)
                if not raw_rows:
                    failed.append(os.path.basename(path))
                    continue
                header_text = extract_invoice_header_text(path)
                pharmacy_name, matched = resolve_pharmacy_name(header_text)
                results = self.pipeline.process_rows(raw_rows)
                loaded.append({
                    "path": path,
                    "filename": os.path.basename(path),
                    "results": results,
                    "copied": set(),
                    "confirmed": set(),   # فهارس الأصناف اللي اتأكّدت يدوياً (بنفسجي)
                    "ignored": set(),     # فهارس الأصناف اللي اتستبعدت يدوياً بهذه الفاتورة (رمادي)
                    "completed": False,
                    "pharmacy_name": pharmacy_name,
                    "pharmacy_matched": matched,
                    "edited": {},   # {idx: النص العربي المعدَّل يدوياً (منطقي غير مُعاد تشكيله)}
                })
            except Exception:
                failed.append(os.path.basename(path))

        if not loaded:
            messagebox.showwarning("لا توجد بيانات", "لم يتم العثور على أي أصناف داخل الملفات المختارة.")
            self.status_var.set(_ar("جاهز."))
            return

        self.invoices = loaded
        self.current_index = 0
        self._show_invoice(0)

        msg = f"تم تحميل {len(loaded)} فاتورة."
        if failed:
            msg += f" (تعذّرت قراءة {len(failed)}: {', '.join(failed[:5])}{'...' if len(failed) > 5 else ''})"
        self.status_var.set(_ar(msg))

    # -------------------------------------------------------- عرض/تنقل
    def _show_idle_state(self):
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        self.nav_label.configure(text=_ar("لا توجد فواتير محمّلة"))
        self.copied_count_label.configure(text="")
        self.pharmacy_label.configure(text=_ar("🏥 لم يتم استيراد فاتورة بعد"), text_color="#7fd4ff")

    def _current_invoice(self):
        if self.current_index is None or not (0 <= self.current_index < len(self.invoices)):
            return None
        return self.invoices[self.current_index]

    # ---- الاسم العربي "المنطقي" (غير المُعاد تشكيله) لكل صف — هو المصدر
    # الوحيد المستخدم في النسخ/الحفظ/التعديل. العرض المرئي فقط يمرّ على _ar() ----
    def _get_arabic(self, inv, idx) -> str:
        if idx in inv["edited"]:
            return inv["edited"][idx]
        return inv["results"][idx].suggested_arabic

    def _set_arabic(self, inv, idx, text: str):
        inv["edited"][idx] = text

    def _row_values(self, inv, idx):
        r = inv["results"][idx]
        invoice_price_txt = f"{r.invoice_price:.2f}" if r.invoice_price is not None else "-"
        quantity_txt = str(r.quantity) if r.quantity is not None else "-"
        score_txt = f"{r.score:.0f}%" + (" ✅" if r.price_verified else "")
        idx_display = f"{idx + 1} ✓" if idx in inv["copied"] else str(idx + 1)
        original_display = f"⚠️🔒 {r.original_text}" if r.controlled else r.original_text
        arabic_logical = self._get_arabic(inv, idx)
        if arabic_logical:
            arabic_display = _ar(f"🔒 {arabic_logical}" if r.controlled else arabic_logical)
        else:
            # مفيش صنف حقيقي مرتبط بالشيت خالص - ممنوع نعرض تخمين حر من
            # محرك التعريب؛ نعرض تنبيه واضح بدل خانة فاضية غامضة، ونسيب
            # المستخدم يكتب يدوياً (تعديل) أو يستبعد الصنف لو مش دواء أصلاً.
            arabic_display = _ar("⚠️ غير موجود بالشيت - أدخل يدوياً")
        return (idx_display, original_display, invoice_price_txt, arabic_display,
                quantity_txt, score_txt,
                _ar("📋 نسخ"), _ar("✏️ تعديل"), _ar("✅ تأكيد"), _ar("⚠️ ناقص"), _ar("🚫 استبعاد"))

    def _row_tag(self, inv, idx, r):
        """يحدد تاج التلوين النهائي للصف. الأولوية: أصناف مهمة (جدول،
        برتقالي صارخ - انتبه دايماً بغض النظر عن أي حالة تانية) > مؤكَّد
        يدوياً > مستبعد (رمادي، دائم) > نُسخ > لون الثقة الافتراضي.
        "ناقص" ليه أي تأثير على اللون إطلاقاً — بيتسجل في شيت متابعة
        منفصل بس (فرق متعمَّد عن "استبعاد" اللي بيتلوّن دائماً ويتذكَّر
        للفواتير القادمة)."""
        if r.controlled:
            return "controlled"
        if idx in inv["confirmed"]:
            return "confirmed"
        if idx in inv["ignored"] or r.ignored:
            return "ignored"
        if idx in inv["copied"]:
            return "copied"
        return r.color

    def _show_invoice(self, index):
        if not self.invoices:
            self._show_idle_state()
            return
        index = max(0, min(index, len(self.invoices) - 1))
        self.current_index = index
        inv = self.invoices[index]

        done_mark = " ✅" if inv["completed"] else ""
        self.nav_label.configure(
            text=_ar(f"فاتورة {index + 1} من {len(self.invoices)}: {inv['filename']}{done_mark}")
        )

        if inv["pharmacy_matched"]:
            self.pharmacy_label.configure(text=_ar(f"🏥 الفاتورة لصيدلية: {inv['pharmacy_name']}"), text_color="#7fd4ff")
        elif inv["pharmacy_name"]:
            self.pharmacy_label.configure(text=_ar(f"🏥 كود غير معروف بالفاتورة: {inv['pharmacy_name']}"), text_color="#f0c14b")
        else:
            self.pharmacy_label.configure(text=_ar("🏥 تعذّر تحديد اسم الصيدلية من هذه الفاتورة"), text_color="#f0c14b")

        self._refresh_table()

    def show_previous_invoice(self):
        if self.current_index is None or not self.invoices:
            return
        self._show_invoice(self.current_index - 1)

    def show_next_invoice(self):
        if self.current_index is None or not self.invoices:
            return
        self._show_invoice(self.current_index + 1)

    def complete_current_invoice(self):
        inv = self._current_invoice()
        if inv is None:
            return
        inv["completed"] = True
        self._show_invoice(self.current_index)
        self.status_var.set(_ar(f"✅ تم وضع علامة اكتمال على فاتورة: {inv['filename']}"))

    def close_current_invoice(self):
        """يغلق الفاتورة الحالية نهائياً من الدفعة الحالية (زي إغلاق تبويب) وينتقل للتالية تلقائياً."""
        if self.current_index is None or not self.invoices:
            return
        closed_name = self.invoices[self.current_index]["filename"]
        del self.invoices[self.current_index]

        if not self.invoices:
            self.current_index = None
            self._show_idle_state()
        else:
            self._show_invoice(min(self.current_index, len(self.invoices) - 1))

        self.status_var.set(_ar(f"❌ تم إغلاق فاتورة: {closed_name}"))

    def _refresh_table(self):
        inv = self._current_invoice()
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        if inv is None:
            self._update_copied_counter()
            return

        for i, r in enumerate(inv["results"]):
            tags = (self._row_tag(inv, i, r),)
            self.tree.insert("", "end", iid=str(i), values=self._row_values(inv, i), tags=tags)
        if inv["results"]:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
        self._update_copied_counter()

    def _update_copied_counter(self):
        inv = self._current_invoice()
        if inv is None:
            self.copied_count_label.configure(text="")
            return
        total = len(inv["results"])
        copied = len(inv["copied"])
        self.copied_count_label.configure(text=_ar(f"📋 الأصناف: {total}   |   نُسخ: {copied} من {total}"))

    def _on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        # الإجراءات دلوقتي كل واحد في عمود مستقل بذاته (بدل عمود واحد
        # مقسوم بالعرض)، فالتنفيذ بيعتمد على هوية العمود نفسه، مش على
        # موضع النقر النسبي — وده يمنع تماماً مشكلة تشكيل النص العربي
        # للعرض (bidi) اللي كانت بتقلب الترتيب المرئي للأزرار الثلاثة
        # فتخلي كل زرار ينفّذ إجراء غير اللي مكتوب عليه.
        handler = self._action_column_ids.get(col)
        if handler:
            handler(row_id)

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if region == "cell" and col == "#4" and row_id:  # عمود العربي: قابل للتعديل المباشر
            self._inline_edit(row_id)

    # ---- النسخ الذكي: دايماً بينسخ الاسم العربي المنطقي (غير المُعاد
    # تشكيله) — أبداً النص المُشكَّل للعرض، ولا يرجع للاسم الإنجليزي إلا لو
    # عمود العربي فاضي تماماً (حالة نادرة جداً) ----
    def _on_turbo_toggle(self):
        self.settings["turbo_mode"] = bool(self.turbo_mode_var.get())
        save_settings(self.settings)
        if self.turbo_mode_var.get():
            self.status_var.set(_ar(
                "⚡ وضع التوربو شغّال: ضغطة نسخ واحدة هتنسخ وتنقلك لنظام المخازن وتلصق وتضغط Enter تلقائياً - "
                "تأكد إن نظام المخازن هو آخر نافذة فاتحها قبل الأداة."
            ))

    def _copy_row(self, row_id):
        inv = self._current_invoice()
        if inv is None:
            return
        idx = int(row_id)
        r = inv["results"][idx]
        arabic_current = self._get_arabic(inv, idx)
        text_to_copy = _clean_copy_text(arabic_current) if arabic_current else r.original_text

        if _HAS_CLIPBOARD:
            try:
                pyperclip.copy(text_to_copy)
            except Exception:
                self.clipboard_clear()
                self.clipboard_append(text_to_copy)
        else:
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)

        inv["copied"].add(idx)
        if len(inv["copied"]) == len(inv["results"]):
            inv["completed"] = True
            self.nav_label.configure(
                text=_ar(f"فاتورة {self.current_index + 1} من {len(self.invoices)}: {inv['filename']} ✅")
            )

        self.tree.item(row_id, values=self._row_values(inv, idx), tags=(self._row_tag(inv, idx, r),))
        self._update_copied_counter()

        self.status_var.set(_ar(f"✅ تم نسخ: {text_to_copy}"))

        if self.turbo_mode_var.get() and turbo.is_available():
            turbo.run_sequence(self)

    def _save_row_as_exception(self, row_id):
        """
        زر 'تأكيد ✅': يحفظ الربط (الاسم كما ورد بالفاتورة -> الاسم العربي
        المعتمد) في ملف الاستثناءات — على المسار المشترك لو مضبوط، بحيث
        يظهر هذا الصنف تلقائياً بثقة 100% لأي مستخدم آخر من أول ظهور تالٍ له.
        """
        inv = self._current_invoice()
        if inv is None:
            return
        idx = int(row_id)
        r = inv["results"][idx]
        mapped = _clean_copy_text(self._get_arabic(inv, idx))
        self.pipeline.save_exception(r.original_text, mapped)
        inv["confirmed"].add(idx)
        row_id = str(idx)
        if self.tree.exists(row_id):
            self.tree.item(row_id, values=self._row_values(inv, idx), tags=(self._row_tag(inv, idx, r),))
        self.status_var.set(_ar(f"✅ تم تأكيد وحفظ: {r.original_text!r} -> {mapped!r} (سيظهر متطابقاً 100% تلقائياً بعد كده)"))
        self.db_status_label.configure(text=_ar(self._db_status_text()))

    def _mark_row_missing(self, row_id):
        """
        زر 'ناقص ⚠️': يسجّل بيانات الصنف في ملف Missing_Items.xlsx منفصل
        (متابعة لاحقة فقط للفريق) — بدون أي تأثير على الفاتورة، ولا على
        نتائج المطابقة، ولا على ملف الاستثناءات، **ولا على لون الصف**:
        الفرق عن "استبعاد" أن الناقص لا يُحفظ كحالة دائمة للصنف ولا يغيّر
        شكله الآن أو مستقبلاً — مجرد سطر في شيت متابعة فقط. لو نفس الصنف
        (بنفس الاسم الأصلي) مسجَّل بالفعل، مش بيتكرر خالص إلا بعد تصفير
        الشيت بالكامل من الإعدادات.
        """
        inv = self._current_invoice()
        if inv is None:
            return
        idx = int(row_id)
        r = inv["results"][idx]
        arabic_current = self._get_arabic(inv, idx)
        try:
            was_added = self.missing_manager.record(
                pharmacy_name=inv.get("pharmacy_name"),
                invoice_filename=inv.get("filename"),
                original_text=r.original_text,
                arabic_text=arabic_current,
                invoice_price=r.invoice_price,
                quantity=r.quantity,
            )
        except Exception as exc:
            messagebox.showwarning("تعذّر التسجيل", f"تعذّر حفظ الصنف الناقص في الملف:\n{exc}")
            return

        if was_added:
            self.status_var.set(_ar(f"⚠️ تم إرسال الصنف لشيت النواقص: {r.original_text!r} (شكل الصف هيفضل زي ما هو)"))
        else:
            self.status_var.set(_ar(
                f"ℹ️ الصنف {r.original_text!r} مسجَّل بالفعل في شيت النواقص - مش هيتكرر "
                "(هيتضاف تاني بس لو صفّرت الشيت من الإعدادات)."
            ))

    def _mark_row_ignored(self, row_id):
        """
        زر 'استبعاد 🚫': يضيف الصنف لقائمة Blacklist (Ignored_Items.xlsx)
        ويلوّن الصف رمادياً فوراً. من أول ظهور تالٍ لنفس الصنف — أو صنف
        مشابه له جداً — في أي فاتورة قادمة (حتى بجهاز تاني لو فيه مسار
        مشترك)، هيتلوّن رمادياً تلقائياً بمجرد المعالجة دون أي تدخل يدوي.
        """
        inv = self._current_invoice()
        if inv is None:
            return
        idx = int(row_id)
        r = inv["results"][idx]
        matched_name = r.suggested_arabic if r.source in ("database", "database_low_confidence") else None
        try:
            self.pipeline.add_ignored(r.original_text, matched_name)
        except Exception as exc:
            messagebox.showwarning("تعذّر الاستبعاد", f"تعذّر حفظ الصنف في قائمة الاستبعاد:\n{exc}")
            return

        r.ignored = True  # تفعيل فوري للتلوين الرمادي بدون انتظار إعادة معالجة الفاتورة
        inv["ignored"].add(idx)
        inv["confirmed"].discard(idx)
        self.tree.item(row_id, values=self._row_values(inv, idx), tags=(self._row_tag(inv, idx, r),))
        self.status_var.set(_ar(f"🚫 تم استبعاد الصنف: {r.original_text!r} (لن يظهر مطلوباً للإدخال في الفواتير القادمة)"))

    # ---- التعديل المباشر (Inline Edit) — من زر "تعديل" أو دبل كليك ----
    def _inline_edit(self, row_id):
        inv = self._current_invoice()
        if inv is None:
            return
        idx = int(row_id)

        col_box = self.tree.bbox(row_id, "#4")
        if not col_box:
            return
        x, y, width, height = col_box

        entry = tk.Entry(self.tree, justify="right")
        entry.insert(0, self._get_arabic(inv, idx))  # النص المنطقي الصحيح، مش المُشكَّل للعرض
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus()
        self._editing_entry = entry
        self._editing_after_id = None

        def sync_live(_event=None):
            """
            يحفظ أي حرف يُكتب أو يُلصق فوراً لحظة بلحظة — حتى لو المستخدم
            منضغطش تأكيد ولا حتى Enter، فمفيش أي احتمال لضياع أي حرف تحت
            أي ظرف (حتى لو حصل إغلاق غير متوقع للخانة).
            """
            if entry.winfo_exists():
                self._set_arabic(inv, idx, entry.get())

        def finish_edit():
            """
            عند الانتهاء الفعلي من التعديل (Enter أو الخروج من الخانة):
            نبحث في شيت الأصناف الحقيقي عن أقرب تطابق لما كتبه المستخدم —
            ولو لقينا تطابقاً معتمداً، نستبدل النص باسم الصنف الأصلي حرفياً
            من الشيت (بدل ما نسيب أي تخمين من عندنا)، ضماناً لتطابق تام مع
            نظامك. لو محصلش تطابق، يبقى النص كما كتبه المستخدم بالظبط.
            """
            if not entry.winfo_exists():
                return
            typed_text = _clean_copy_text(entry.get())
            final_text = typed_text
            if typed_text:
                try:
                    match = self.pipeline.matcher.match(typed_text, threshold=self.pipeline.match_threshold)
                except Exception:
                    match = {"matched": False}
                if match.get("matched"):
                    final_text = match["original_name"]
                    self.status_var.set(_ar(f"🔎 تم العثور على الصنف في الشيت واعتماد اسمه الأصلي: {final_text}"))
                else:
                    self.status_var.set(_ar("✏️ لم يُعثر على تطابق مطابق في الشيت — تم حفظ النص كما كتبته بالضبط."))
            self._set_arabic(inv, idx, final_text)
            entry.destroy()
            self._editing_entry = None
            self.tree.item(row_id, values=self._row_values(inv, idx))

        def on_return(_event=None):
            if self._editing_after_id:
                self.after_cancel(self._editing_after_id)
                self._editing_after_id = None
            finish_edit()

        def on_focus_out(_event=None):
            # تأخير بسيط قبل الإغلاق الفعلي، عشان لو الفوكس راح لقائمة
            # يمين-كليك (لصق/نسخ/قص) ييجي وقت كافٍ لتنفيذ الأمر على
            # الخانة وهي لسه موجودة، قبل ما نقفلها ونعتمد النص النهائي.
            self._editing_after_id = self.after(200, finish_edit)

        def cancel(_event=None):
            entry.destroy()
            self._editing_entry = None

        entry.bind("<KeyRelease>", sync_live)
        entry.bind("<<Paste>>", lambda e: self.after(10, sync_live))
        entry.bind("<Return>", on_return)
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Escape>", cancel)

        # قائمة يمين-كليك صريحة (قص/نسخ/لصق) — عشان اللصق يبقى واضح ومضمون
        # حتى لو حد مش عارف اختصار Ctrl+V من لوحة المفاتيح. Ctrl+V نفسه
        # شغّال افتراضياً من Tkinter بدون أي كود إضافي.
        menu = tk.Menu(entry, tearoff=0)
        menu.add_command(label=_ar("قص"), command=lambda: (entry.event_generate("<<Cut>>"), self.after(10, sync_live)))
        menu.add_command(label=_ar("نسخ"), command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label=_ar("لصق"), command=lambda: (entry.event_generate("<<Paste>>"), self.after(10, sync_live)))
        menu.add_separator()
        menu.add_command(label=_ar("تحديد الكل"), command=lambda: entry.select_range(0, "end"))

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
            return "break"

        entry.bind("<Button-3>", show_menu)

    def _is_editing(self) -> bool:
        """بيرجع True لو خانة التعديل المباشر مفتوحة حالياً — يمنع اختصارات
        لوحة المفاتيح العامة (Space/Enter/Ctrl+E/Ctrl+S/الأسهم) من التدخل
        أثناء الكتابة أو اللصق داخل اسم الصنف (كان بيحصل قبل كده مع أي
        مسافة بين كلمتين في الاسم)."""
        return getattr(self, "_editing_entry", None) is not None

    # ---- اختصارات لوحة المفاتيح ----
    def _current_row_id(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _shortcut_move_down(self, _event=None):
        if self._is_editing():
            return
        children = self.tree.get_children()
        if not children:
            return
        row_id = self._current_row_id() or children[0]
        idx = children.index(row_id)
        nxt = children[min(idx + 1, len(children) - 1)]
        self.tree.selection_set(nxt)
        self.tree.see(nxt)

    def _shortcut_move_up(self, _event=None):
        if self._is_editing():
            return
        children = self.tree.get_children()
        if not children:
            return
        row_id = self._current_row_id() or children[0]
        idx = children.index(row_id)
        prev = children[max(idx - 1, 0)]
        self.tree.selection_set(prev)
        self.tree.see(prev)

    def _shortcut_copy_and_next(self, _event=None):
        if self._is_editing():
            return  # سيب الحرف يتكتب عادي جوه خانة التعديل (خصوصاً المسافة)
        row_id = self._current_row_id()
        if row_id is None:
            return "break"
        self._copy_row(row_id)
        self._shortcut_move_down()
        return "break"

    def _shortcut_inline_edit(self, _event=None):
        if self._is_editing():
            return
        row_id = self._current_row_id()
        if row_id is not None:
            self._inline_edit(row_id)
        return "break"

    def _shortcut_save_exception(self, _event=None):
        if self._is_editing():
            return
        row_id = self._current_row_id()
        if row_id is not None:
            self._save_row_as_exception(row_id)
        return "break"

    def _shortcut_mark_missing(self, _event=None):
        if self._is_editing():
            return
        row_id = self._current_row_id()
        if row_id is not None:
            self._mark_row_missing(row_id)
        return "break"

    def _shortcut_mark_ignored(self, _event=None):
        if self._is_editing():
            return
        row_id = self._current_row_id()
        if row_id is not None:
            self._mark_row_ignored(row_id)
        return "break"


def _set_windows_app_id():
    """
    يربط العملية بمعرّف تطبيق مستقل (AppUserModelID) قبل ظهور أي نافذة —
    لازم على ويندوز عشان أيقونة شريط المهام (Taskbar) تتبع أيقونة برنامجنا
    فعلاً بدل ما تتجمّع تحت أيقونة بايثون العامة (مشكلة شائعة جداً في
    برامج PyInstaller onefile من غير النداء ده). مفيش تأثير على أي نظام
    غير ويندوز (بيتجاهل بهدوء).
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"YoussefAmr.{APP_NAME}.{APP_VERSION}")
    except Exception:
        pass  # نظام غير مدعوم/إصدار قديم من ويندوز - العنوان اليدوي (iconbitmap) هيفضل شغّال براحته


def main():
    _set_windows_app_id()  # قبل أي نافذة Tk نهائياً
    settings = load_settings()
    authenticated, activation_info = run_auth_gate(settings)
    if not authenticated:
        return
    app = App(activation_info=activation_info)
    app.mainloop()


if __name__ == "__main__":
    main()
