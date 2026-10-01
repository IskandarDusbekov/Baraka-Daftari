import datetime as dt
import uuid

from django.db import IntegrityError, models
from django.db.models import Sum
from django.utils import timezone


class TgUser(models.Model):
    """Telegram orqali kirgan foydalanuvchi."""

    # Tashqi identifikator: tokenlar va admin panel havolalarida ketma-ket raqam (1, 2, 3…) o'rniga
    # ishlatiladi — boshqa foydalanuvchi ID sini taxmin qilib bo'lmaydi va ID lar chalkashmaydi.
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tg_id = models.BigIntegerField("Telegram ID", unique=True)
    first_name = models.CharField("Ism", max_length=128, blank=True)
    last_name = models.CharField("Familiya", max_length=128, blank=True)
    username = models.CharField(max_length=64, blank=True)
    photo_url = models.URLField(max_length=512, blank=True)

    CURRENCIES = [
        ("UZS", "So'm"),
        ("USD", "Dollar"),
    ]
    # Hisob valyutasi: barcha summalar faqat shu valyutada saqlanadi (aralashmaydi)
    currency = models.CharField("Hisob valyutasi", max_length=3, choices=CURRENCIES, default="UZS")
    currency_chosen = models.BooleanField("Valyutani tanlagan", default=False)
    onboarding_hidden = models.BooleanField("«Boshlash yo'li» yashirilgan", default=False)

    INCOME_TYPES = [
        ("", "Tanlanmagan"),
        ("salary", "Oylik oladi"),
        ("irregular", "Oylik olmaydi (daromadi o'zgaruvchan)"),
    ]
    income_type = models.CharField("Daromad turi", max_length=16, choices=INCOME_TYPES, blank=True, default="")
    monthly_income = models.BigIntegerField(
        "Oylik daromad", default=0, help_text="Foydalanuvchi o'zi kiritadi; zaxira va qarz rejasi shunga qarab hisoblanadi",
    )
    save_percent = models.PositiveSmallIntegerField(
        "O'ziga to'lash foizi", default=10, help_text="Daromadning necha foizi zaxiraga ajratiladi (1–50)",
    )
    guard_months = models.PositiveSmallIntegerField(
        "Qo'riqchi pul necha oylik", default=3, help_text="Qo'riqchi pul necha oylik xarajatga yetishi kerak (3–6)",
    )
    notify = models.BooleanField("Eslatmalar yoqilgan", default=True)
    accepted_disclaimer = models.BooleanField(default=False)
    bot_started = models.BooleanField("Botni ishga tushirgan", default=False)
    bot_blocked = models.BooleanField("Botni bloklagan", default=False)
    last_morning_date = models.DateField(null=True, blank=True)
    last_evening_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True, help_text="O'chirilsa, foydalanuvchi ilovaga kira olmaydi")
    admin_note = models.TextField("Admin izohi", blank=True)
    # Oshirilsa, barcha eski tokenlar bekor bo'ladi ("barcha qurilmalardan chiqarish")
    token_version = models.PositiveIntegerField(default=1)
    visits = models.PositiveIntegerField("Kirishlar soni", default=1, help_text="30 daqiqadan uzoq tanaffusdan keyingi har kirish")
    rating_asked_at = models.DateTimeField("Baho so'ralgan", null=True, blank=True)
    rating_asks = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=["notify", "bot_started", "bot_blocked"], name="tguser_reminder_idx"),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or (f"@{self.username}" if self.username else str(self.tg_id))

    @classmethod
    def upsert_from_telegram(cls, data):
        """Telegram `user` obyektidan foydalanuvchini yaratadi yoki yangilaydi. (user, yangimi)"""
        now = timezone.now()
        fields = {
            "first_name": str(data.get("first_name") or "")[:128],
            "last_name": str(data.get("last_name") or "")[:128],
            "username": str(data.get("username") or "")[:64],
            "photo_url": str(data.get("photo_url") or "")[:512],
        }
        user = cls.objects.filter(tg_id=int(data["id"])).first()
        if user is None:
            try:
                return cls.objects.create(tg_id=int(data["id"]), last_seen=now, **fields), True
            except IntegrityError:  # shu soniyada parallel so'rov yaratib ulgurdi
                user = cls.objects.get(tg_id=int(data["id"]))
        if now - user.last_seen > dt.timedelta(minutes=30):
            user.visits += 1  # uzoq tanaffusdan keyingi yangi tashrif
        for name, value in fields.items():
            setattr(user, name, value)
        user.last_seen = now
        user.save(update_fields=[*fields, "last_seen", "visits"])
        return user, False


class Income(models.Model):
    SOURCES = [
        ("salary", "Oylik maosh"),
        ("extra", "Qo'shimcha daromad"),
        ("business", "Biznes / savdo"),
        ("other", "Boshqa"),
    ]

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="incomes")
    amount = models.BigIntegerField("Summa (so'm)")
    source = models.CharField(max_length=16, choices=SOURCES, default="salary")
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Daromad"
        verbose_name_plural = "Daromadlar"
        indexes = [models.Index(fields=["user", "date"], name="income_user_date_idx")]


class Saving(models.Model):
    """Jamg'arma harakati ("o'zingga to'la").

    3-saboq: jamg'arma ikkiga bo'linadi — qo'riqchi pul (og'ir kun uchun, 3–6 oylik xarajat)
    va o'sadigan pul (mehnat, savdo, sheriklikka ishlaydigan pul).
    `amount` ishorali: qo'shish musbat, olish manfiy. O'tkazish — bir `group` dagi ikki yozuv.
    """

    BUCKETS = [
        ("guard", "Qo'riqchi pul"),
        ("grow", "O'sadigan pul"),
    ]
    KINDS = [
        ("deposit", "Qo'shildi"),
        ("withdraw", "Olindi"),
        ("transfer", "O'tkazildi"),
    ]

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="savings")
    amount = models.BigIntegerField("Summa (so'm)")
    bucket = models.CharField("Qism", max_length=8, choices=BUCKETS, default="guard")
    kind = models.CharField("Turi", max_length=10, choices=KINDS, default="deposit")
    group = models.CharField(max_length=32, blank=True, help_text="O'tkazmaning ikki yozuvini bog'laydi")
    income = models.ForeignKey(Income, on_delete=models.SET_NULL, null=True, blank=True, related_name="savings")
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Jamg'arma harakati"
        verbose_name_plural = "Jamg'arma harakatlari"
        indexes = [
            models.Index(fields=["user", "date"], name="saving_user_date_idx"),
            models.Index(fields=["user", "bucket"], name="saving_user_bucket_idx"),
        ]


class Expense(models.Model):
    CATEGORIES = [
        ("food", "Oziq-ovqat"),
        ("rent", "Ijara / uy"),
        ("utility", "Kommunal"),
        ("transport", "Yo'lkira"),
        ("clothes", "Kiyim-kechak"),
        ("health", "Sog'liq"),
        ("education", "Ta'lim"),
        ("phone", "Aloqa / internet"),
        ("events", "To'y-marosim"),
        ("charity", "Sadaqa / ehson"),
        ("shopping", "Xaridlar"),  # mayda xaridlar: ichimlik, shirinlik, uy-ro'zg'or buyumlari
        ("other", "Boshqalar"),
    ]

    # 2-saboq: xarajatni "Zarur — Kerak — Havas" tarzida saralash
    NEEDS = [
        ("zarur", "Zarur"),
        ("kerak", "Kerak"),
        ("havas", "Havas"),
    ]

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="expenses")
    amount = models.BigIntegerField("Summa (so'm)")
    category = models.CharField(max_length=16, choices=CATEGORIES, default="other")
    need = models.CharField("Zarur/Kerak/Havas", max_length=8, choices=NEEDS, blank=True, default="")
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Xarajat"
        verbose_name_plural = "Xarajatlar"
        indexes = [models.Index(fields=["user", "date"], name="expense_user_date_idx")]


class RecurringExpense(models.Model):
    """Har oy takrorlanadigan majburiy xarajat (ijara, kommunal, internet...).

    Belgilangan kuni shu oy uchun avtomatik Expense yoziladi (ixtiyoriy funksiya).
    """

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="recurring")
    name = models.CharField("Nomi", max_length=100)
    amount = models.BigIntegerField("Summa (so'm)")
    category = models.CharField(max_length=16, choices=Expense.CATEGORIES, default="other")
    need = models.CharField(max_length=8, choices=Expense.NEEDS, blank=True, default="zarur")
    day = models.PositiveSmallIntegerField("Oyning qaysi kuni", default=1)
    active = models.BooleanField(default=True)
    last_month = models.CharField("Oxirgi yozilgan oy", max_length=7, blank=True, help_text="YYYY-MM")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "id"]
        verbose_name = "Oylik majburiy xarajat"
        verbose_name_plural = "Oylik majburiy xarajatlar"

    def __str__(self):
        return self.name


class Debt(models.Model):
    KINDS = [
        ("credit", "Bank krediti"),
        ("personal", "Tanishdan qarz"),
        ("nasiya", "Nasiya"),
        ("other", "Boshqa"),
    ]

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="debts")
    name = models.CharField("Nomi", max_length=100)
    kind = models.CharField(max_length=16, choices=KINDS, default="credit")
    total = models.BigIntegerField("Umumiy summa")
    paid = models.BigIntegerField("To'langan", default=0)
    monthly_payment = models.BigIntegerField("Oylik to'lov", default=0)
    # Bank krediti uchun (annuitet): olingan summa, yillik foiz, muddat va asosiy qarz qoldig'i
    principal = models.BigIntegerField("Olingan summa", default=0)
    interest_rate = models.DecimalField("Yillik foiz", max_digits=5, decimal_places=2, default=0)
    term_months = models.PositiveSmallIntegerField("Muddat (oy)", default=0)
    balance = models.BigIntegerField("Asosiy qarz qoldig'i", default=0)
    extra_percent = models.PositiveSmallIntegerField("Qo'shib to'lash foizi", default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Qarz"
        verbose_name_plural = "Qarzlar"

    def __str__(self):
        return self.name

    @property
    def is_credit(self):
        """Foiz va muddat bilan hisoblanadigan bank krediti."""
        return self.kind == "credit" and self.principal > 0 and self.term_months > 0

    @property
    def remaining(self):
        return max(self.total - self.paid, 0)

    @property
    def percent(self):
        if self.total <= 0:
            return 100
        return min(100, round(self.paid * 100 / self.total))


class DebtPayment(models.Model):
    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name="payments")
    amount = models.BigIntegerField()
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Qarz to'lovi"
        verbose_name_plural = "Qarz to'lovlari"
        indexes = [models.Index(fields=["debt", "date"], name="debtpay_debt_date_idx")]


class Lesson(models.Model):
    """Saboq — Abdukarim Mirzayevning haftalik «Baraka Daftari» videosi asosida."""

    TASK_TYPES = [
        ("read", "Faqat ko'rish va belgilash"),
        ("note", "Fikr yozish"),
        ("income", "Daromad kiritish"),
        ("expense", "Xarajat kiritish"),
        ("save", "10% zaxiraga ajratish"),
        ("debt_list", "Qarzlar ro'yxatini tuzish"),
        ("debt_plan", "Qarz rejasini ko'rish"),
        ("debt_pay", "Qarzga to'lov qilish"),
    ]

    number = models.PositiveIntegerField("Saboq raqami", unique=True)
    title = models.CharField("Mavzu", max_length=150)
    published_on = models.DateField("Video chiqqan sana", null=True, blank=True)
    youtube_id = models.CharField(
        "YouTube video ID", max_length=32, blank=True,
        help_text="Masalan https://youtu.be/AbCdEf12345 uchun: AbCdEf12345",
    )
    summary = models.TextField("Qisqacha mazmun")
    key_points = models.TextField("Saboqlar", blank=True, help_text="Har bir saboq alohida qatorda")
    tasks = models.TextField("Nima qilish kerak", blank=True, help_text="Har bir vazifa alohida qatorda")
    task_type = models.CharField(
        "Ilovadagi amal", max_length=16, choices=TASK_TYPES, default="read",
        help_text="Saboqni yakunlash uchun ilovada nima qilingan bo'lishi kerak",
    )
    note_prompt = models.CharField("Savol (fikr yozish uchun)", max_length=200, blank=True)
    is_published = models.BooleanField("Foydalanuvchilarga ko'rinadi", default=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Saboq"
        verbose_name_plural = "Saboqlar"

    def __str__(self):
        return f"{self.number}-saboq: {self.title}"

    @staticmethod
    def _lines(text):
        return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]

    @property
    def key_points_list(self):
        return self._lines(self.key_points)

    @property
    def tasks_list(self):
        return self._lines(self.tasks)

    @property
    def task_title(self):
        """Qisqa ko'rinish (bot va bosh sahifa uchun): birinchi vazifa."""
        tasks = self.tasks_list
        return tasks[0] if tasks else "Videoni ko'ring va saboqlarni o'qing"

    @property
    def video_url(self):
        if self.youtube_id:
            return f"https://www.youtube.com/watch?v={self.youtube_id}"
        return "https://www.youtube.com/@XizrAbdulkarim/videos"


class LessonProgress(models.Model):
    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    completed_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("user", "lesson")]
        verbose_name = "Bajarilgan saboq"
        verbose_name_plural = "Bajarilgan saboqlar"


class ActivityLog(models.Model):
    """Foydalanuvchi amallari jurnali (admin panel: amallar, kirishlar, ro'yxatdan o'tishlar)."""

    ACTIONS = [
        ("register", "Ro'yxatdan o'tdi"),
        ("login", "Kirdi"),
        ("income_add", "Kirim yozdi"),
        ("income_edit", "Kirimni tahrirladi"),
        ("expense_add", "Xarajat yozdi"),
        ("expense_edit", "Xarajatni tahrirladi"),
        ("entry_delete", "Yozuvni o'chirdi"),
        ("saving_add", "Jamg'armaga qo'shdi"),
        ("saving_withdraw", "Jamg'armadan oldi"),
        ("saving_transfer", "Jamg'arma ichida o'tkazdi"),
        ("debt_add", "Qarz qo'shdi"),
        ("debt_pay", "Qarz to'ladi"),
        ("debt_close", "Qarzni yopdi"),
        ("lesson_complete", "Saboqni yakunladi"),
        ("settings", "Sozlamalarni o'zgartirdi"),
        ("recurring_add", "Majburiy xarajat qo'shdi"),
        ("bot_start", "Botni ishga tushirdi"),
        ("bot_block", "Botni blokladi"),
        ("bot_report", "Botda hisobot ko'rdi"),
        ("feedback", "Baho qoldirdi"),
        ("logout_all", "Barcha qurilmalardan chiqdi"),
    ]

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="activity")
    action = models.CharField(max_length=24, choices=ACTIONS)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Amal"
        verbose_name_plural = "Amallar jurnali"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="activity_user_idx"),
            models.Index(fields=["action", "-created_at"], name="activity_action_idx"),
            models.Index(fields=["-created_at"], name="activity_created_idx"),
        ]


class Broadcast(models.Model):
    """Bot orqali ommaviy xabar. Bot jarayoni fon oqimida navbat bilan yuboradi (100k+ foydalanuvchi)."""

    STATUSES = [
        ("pending", "Navbatda"),
        ("sending", "Yuborilmoqda"),
        ("done", "Yuborildi"),
        ("failed", "Xato"),
    ]
    AUDIENCES = [
        ("all", "Barcha (eslatmalari yoqilgan)"),
        ("active7", "Oxirgi 7 kunda kirganlar"),
        ("inactive7", "7 kundan beri kirmaganlar"),
    ]

    text = models.TextField("Matn", blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Saboq e'loni")
    audience = models.CharField(max_length=16, choices=AUDIENCES, default="all")
    status = models.CharField(max_length=10, choices=STATUSES, default="pending", db_index=True)
    total = models.PositiveIntegerField(default=0)
    sent = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    last_user_id = models.BigIntegerField(default=0, help_text="Qayta ishga tushganda shu yerdan davom etadi")
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ommaviy xabar"
        verbose_name_plural = "Ommaviy xabarlar"


class LoginCode(models.Model):
    """Saytga bot orqali kirish uchun bir martalik kod."""

    code = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, null=True, blank=True)
    confirmed = models.BooleanField(default=False)
    consumed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Feedback(models.Model):
    """Foydalanuvchi bahosi (1–5 yulduz) va fikri. Ilovada modal oynada so'raladi."""

    user = models.ForeignKey(TgUser, on_delete=models.CASCADE, related_name="feedback")
    rating = models.PositiveSmallIntegerField("Baho")
    comment = models.TextField("Fikr", blank=True, max_length=1000)
    page = models.CharField(max_length=32, blank=True)
    is_read = models.BooleanField("Ko'rildi", default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Baho"
        verbose_name_plural = "Baholar"


class SeoSettings(models.Model):
    """SEO sozlamalari (bitta yozuv, pk=1). Admin panel → SEO bo'limida tahrirlanadi."""

    site_url = models.URLField("Sayt manzili", blank=True, help_text="https://baraka.uz — canonical va sitemap uchun")
    title = models.CharField("Sarlavha (title)", max_length=70, blank=True,
                             help_text="Google natijasida ko'rinadi. 50–60 belgi ideal")
    description = models.CharField("Tavsif (meta description)", max_length=170, blank=True,
                                   help_text="Google natijasida sarlavha ostida. 140–160 belgi ideal")
    keywords = models.CharField("Kalit so'zlar", max_length=255, blank=True)
    og_title = models.CharField("Ulashishda sarlavha", max_length=90, blank=True)
    og_description = models.CharField("Ulashishda tavsif", max_length=200, blank=True)
    google_verification = models.CharField("Google meta-teg kodi", max_length=120, blank=True,
                                           help_text="google-site-verification content qiymati (fayl o'rniga)")
    yandex_verification = models.CharField("Yandex meta-teg kodi", max_length=120, blank=True)
    analytics_id = models.CharField("Google Analytics ID", max_length=32, blank=True, help_text="G-XXXXXXXXXX")
    robots_extra = models.TextField("robots.txt qo'shimcha qatorlari", blank=True)
    allow_indexing = models.BooleanField("Qidiruv tizimlariga ochiq", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO sozlamalari"
        verbose_name_plural = "SEO sozlamalari"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SiteSettings(models.Model):
    """Sayt sozlamalari (bitta yozuv, pk=1): muallif sahifalari va biz bilan bog'lanish.

    Admin panel → Sozlamalar bo'limida tahrirlanadi; «Loyiha haqida» sahifasida ko'rinadi.
    """

    author_youtube = models.URLField("Abdukarim Mirzayev — YouTube", blank=True)
    author_instagram = models.URLField("Abdukarim Mirzayev — Instagram", blank=True)
    author_telegram = models.URLField("Abdukarim Mirzayev — Telegram kanal", blank=True)
    contact_telegram = models.CharField("Telegram (admin)", max_length=64, blank=True, help_text="@username — savollar uchun")
    contact_channel = models.URLField("Bizning Telegram kanal", blank=True)
    contact_instagram = models.URLField("Bizning Instagram", blank=True)
    contact_phone = models.CharField("Telefon", max_length=32, blank=True, help_text="+998 90 123 45 67")
    contact_email = models.EmailField("Email", blank=True)
    contact_hours = models.CharField("Ish vaqti", max_length=80, blank=True, help_text="Masalan: Har kuni 9:00–21:00")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sayt sozlamalari"
        verbose_name_plural = "Sayt sozlamalari"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class VerificationFile(models.Model):
    """Google / Yandex / Bing sayt egaligini tasdiqlash fayli (masalan google1a2b3c.html).

    Fayl mazmuni bazada saqlanadi va sayt ildizida (/google1a2b3c.html) beriladi — serverga
    qo'lda fayl yuklash shart emas.
    """

    filename = models.CharField("Fayl nomi", max_length=100, unique=True)
    content = models.TextField("Mazmuni", max_length=10_000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["filename"]
        verbose_name = "Tasdiqlash fayli"
        verbose_name_plural = "Tasdiqlash fayllari"

    def __str__(self):
        return self.filename


def total_of(qs, field="amount"):
    return qs.aggregate(s=Sum(field))["s"] or 0
