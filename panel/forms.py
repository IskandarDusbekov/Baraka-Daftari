import re

from django import forms

from core.models import Broadcast, Lesson, SeoSettings, SiteSettings
from core.seo import VERIFICATION_NAME

YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class LessonForm(forms.ModelForm):
    # To'liq havola ham qabul qilinadi (ID clean_youtube_id da ajratiladi), shuning uchun uzunroq
    youtube_id = forms.CharField(
        label="YouTube video (havola yoki ID)", required=False, max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "https://youtu.be/… yoki havolani shu yerga qo'ying"}),
    )

    class Meta:
        model = Lesson
        fields = [
            "number", "title", "published_on", "youtube_id", "is_published",
            "summary", "key_points", "tasks", "task_type", "note_prompt",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Masalan: Avval o'zingizga to'lang", "data-count": "150"}),
            "published_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "summary": forms.Textarea(attrs={"rows": 5, "placeholder": "Videoning qisqacha mazmuni — 3–5 gap"}),
            "key_points": forms.Textarea(attrs={"rows": 6, "placeholder": "Har bir saboq alohida qatorda\nMasalan: Daromadning 10% ini avval o'zingizga ajrating"}),
            "tasks": forms.Textarea(attrs={"rows": 5, "placeholder": "Har bir vazifa alohida qatorda\nBirinchi qator — bot va bosh sahifada ko'rinadi"}),
            "note_prompt": forms.TextInput(attrs={"placeholder": "Masalan: Bu oy qaysi xarajatdan voz kechasiz?"}),
        }

    def clean_youtube_id(self):
        """To'liq havola kiritilsa ham ID ni ajratib oladi va shaklini tekshiradi."""
        value = (self.cleaned_data.get("youtube_id") or "").strip()
        for marker in ("v=", "youtu.be/", "/embed/", "/shorts/", "/live/"):
            if marker in value:
                value = value.split(marker, 1)[1]
                break
        value = value.split("&")[0].split("?")[0].split("/")[0].split("#")[0]
        if value and not YOUTUBE_ID.match(value):
            raise forms.ValidationError("YouTube havolasini tekshiring — video ID 11 belgidan iborat bo'ladi")
        return value

    def clean(self):
        data = super().clean()
        if data.get("task_type") == "note" and not (data.get("note_prompt") or "").strip():
            self.add_error("note_prompt", "«Fikr yozish» vazifasi uchun savolni yozing")
        if data.get("is_published") and not (data.get("tasks") or "").strip():
            self.add_error("tasks", "Nashr qilinadigan saboqda kamida bitta vazifa bo'lsin")
        return data


class BroadcastForm(forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = ["text", "audience"]
        widgets = {"text": forms.Textarea(attrs={"rows": 5, "placeholder": "Xabar matni…"})}

    def clean_text(self):
        text = (self.cleaned_data.get("text") or "").strip()
        if len(text) < 3:
            raise forms.ValidationError("Xabar matnini yozing")
        if len(text) > 3500:
            raise forms.ValidationError("Xabar juda uzun (3500 belgigacha)")
        return text


class MessageForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Foydalanuvchiga xabar…"}), max_length=3500)


class SeoForm(forms.ModelForm):
    class Meta:
        model = SeoSettings
        fields = [
            "site_url", "title", "description", "keywords", "og_title", "og_description",
            "google_verification", "yandex_verification", "analytics_id", "allow_indexing", "robots_extra",
        ]
        widgets = {
            "site_url": forms.URLInput(attrs={"placeholder": "https://baraka.uz"}),
            "title": forms.TextInput(attrs={"data-count": "60"}),
            "description": forms.Textarea(attrs={"rows": 3, "data-count": "160"}),
            "keywords": forms.TextInput(attrs={"placeholder": "moliyaviy savodxonlik, xarajat daftari, baraka daftari"}),
            "og_description": forms.Textarea(attrs={"rows": 2}),
            "google_verification": forms.TextInput(attrs={"placeholder": "faqat content=\"…\" ichidagi qiymat"}),
            "robots_extra": forms.Textarea(attrs={"rows": 3, "placeholder": "Disallow: /maxfiy/"}),
        }

    def clean_google_verification(self):
        return _meta_token(self.cleaned_data.get("google_verification"))

    def clean_yandex_verification(self):
        return _meta_token(self.cleaned_data.get("yandex_verification"))

    def clean_analytics_id(self):
        value = (self.cleaned_data.get("analytics_id") or "").strip().upper()
        if value and not re.fullmatch(r"G-[A-Z0-9]{4,20}", value):
            raise forms.ValidationError("Google Analytics 4 ID shakli: G-XXXXXXXXXX")
        return value

    def clean_robots_extra(self):
        allowed = ("allow:", "disallow:", "user-agent:", "crawl-delay:", "sitemap:", "#")
        lines = [line.strip() for line in (self.cleaned_data.get("robots_extra") or "").splitlines() if line.strip()]
        for line in lines:
            if not line.lower().startswith(allowed):
                raise forms.ValidationError(f"Noto'g'ri qator: «{line[:40]}». Faqat Allow/Disallow/User-agent/Sitemap")
        return "\n".join(lines)


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "author_youtube", "author_instagram", "author_telegram",
            "contact_telegram", "contact_channel", "contact_instagram", "contact_phone", "contact_email", "contact_hours",
        ]
        widgets = {
            "author_youtube": forms.URLInput(attrs={"placeholder": "https://www.youtube.com/@…"}),
            "author_instagram": forms.URLInput(attrs={"placeholder": "https://www.instagram.com/…"}),
            "author_telegram": forms.URLInput(attrs={"placeholder": "https://t.me/…"}),
            "contact_telegram": forms.TextInput(attrs={"placeholder": "@username"}),
            "contact_channel": forms.URLInput(attrs={"placeholder": "https://t.me/…"}),
            "contact_instagram": forms.URLInput(attrs={"placeholder": "https://www.instagram.com/…"}),
        }

    def clean(self):
        data = super().clean()
        # Sahifada faqat xavfsiz https havolalar chiqadi
        for name in ("author_youtube", "author_instagram", "author_telegram", "contact_channel", "contact_instagram"):
            value = (data.get(name) or "").strip()
            if value and not value.startswith("https://"):
                self.add_error(name, "Havola https:// bilan boshlanishi kerak")
        return data

    def clean_contact_telegram(self):
        value = (self.cleaned_data.get("contact_telegram") or "").strip()
        username = value.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@").strip("/")
        if username and not re.fullmatch(r"[A-Za-z0-9_]{4,32}", username):
            raise forms.ValidationError("Telegram username: faqat harf, raqam va _ (masalan @baraka_admin)")
        return f"@{username}" if username else ""

    def clean_contact_phone(self):
        value = (self.cleaned_data.get("contact_phone") or "").strip()
        if value and not re.fullmatch(r"\+?[\d\s()\-]{7,20}", value):
            raise forms.ValidationError("Telefon raqamini tekshiring (masalan +998 90 123 45 67)")
        return value


def _meta_token(value):
    """To'liq <meta … content="X"> qo'yilsa ham faqat X ni oladi."""
    value = (value or "").strip()
    found = re.search(r'content=["\']([^"\']+)["\']', value)
    if found:
        value = found.group(1)
    if value and not re.fullmatch(r"[A-Za-z0-9_\-]{8,120}", value):
        raise forms.ValidationError("Kodni tekshiring — faqat harf, raqam, - va _")
    return value


class VerificationUploadForm(forms.Form):
    file = forms.FileField(label="Tasdiqlash fayli", help_text="Google Search Console bergan google….html fayl")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not VERIFICATION_NAME.match(f.name or ""):
            raise forms.ValidationError(
                "Fayl nomi google1234abcd.html, yandex_1234abcd.html yoki BingSiteAuth.xml ko'rinishida bo'lishi kerak")
        if f.size > 10_000:
            raise forms.ValidationError("Fayl juda katta — tasdiqlash fayli bir necha bayt bo'ladi")
        try:
            content = f.read().decode("utf-8")
        except UnicodeDecodeError:
            raise forms.ValidationError("Fayl matn ko'rinishida emas")
        lowered = content.lower()
        if "<script" in lowered or "javascript:" in lowered or "<iframe" in lowered:
            raise forms.ValidationError("Faylda skript bor — bu tasdiqlash fayli emas")
        f.text = content
        return f
