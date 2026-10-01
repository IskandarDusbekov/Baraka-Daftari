"""Django admin ("Ma'lumotlar bazasi") — xom ma'lumotlarni ko'rish va tuzatish uchun.

Kundalik ishlar (foydalanuvchilar, saboqlar, xabarlar, adminlar, zaxira) — /boshqaruv/ panelida.
100 000+ foydalanuvchida sahifalar sekinlashmasligi uchun: foydalanuvchi maydonlari ro'yxat
o'rniga ID bilan (raw_id), umumiy sonni hisoblash o'chirilgan.
"""
from django.contrib import admin, messages
from django.db.models import F

from .models import (
    ActivityLog, Broadcast, Debt, DebtPayment, Expense, Feedback, Income, Lesson, LessonProgress, RecurringExpense,
    Saving, TgUser,
)

admin.site.site_header = "Baraka Daftari — ma'lumotlar bazasi"
admin.site.site_title = "Baraka Daftari"
admin.site.index_title = "Bo'limlar (kundalik ishlar uchun «Boshqaruv paneli»ga qayting)"
admin.site.site_url = "/boshqaruv/"


class FastAdmin(admin.ModelAdmin):
    """Katta jadvallar uchun: foydalanuvchi tanlash — ID bo'yicha, umumiy son hisoblanmaydi."""
    list_per_page = 50
    show_full_result_count = False
    raw_id_fields = ("user",)
    list_select_related = ("user",)


@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    list_display = ("display_name", "username", "tg_id", "currency", "status", "visits", "last_seen", "created_at")
    list_filter = ("is_active", "currency", "income_type", "bot_started", "bot_blocked", "notify")
    search_fields = ("tg_id", "first_name", "last_name", "username")
    readonly_fields = ("uid", "tg_id", "created_at", "last_seen", "visits", "token_version", "rating_asked_at", "rating_asks")
    date_hierarchy = "created_at"
    list_per_page = 50
    show_full_result_count = False
    actions = ["block", "unblock", "logout_everywhere"]
    fieldsets = [
        ("Foydalanuvchi", {"fields": ("first_name", "last_name", "username", "tg_id", "uid", "is_active", "admin_note")}),
        ("Hisob sozlamalari", {"fields": ("currency", "income_type", "monthly_income", "save_percent", "guard_months", "notify")}),
        ("Bot", {"fields": ("bot_started", "bot_blocked")}),
        ("Texnik", {"classes": ("collapse",), "fields": (
            "created_at", "last_seen", "visits", "token_version", "rating_asked_at", "rating_asks",
            "accepted_disclaimer", "currency_chosen", "onboarding_hidden")}),
    ]

    @admin.display(description="Holati")
    def status(self, obj):
        return "✅ faol" if obj.is_active else "⛔️ bloklangan"

    @admin.action(description="Bloklash (ilova va bot yopiladi)")
    def block(self, request, queryset):
        n = queryset.update(is_active=False, token_version=F("token_version") + 1)
        self.message_user(request, f"{n} ta foydalanuvchi bloklandi", messages.SUCCESS)

    @admin.action(description="Blokdan chiqarish")
    def unblock(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} ta foydalanuvchi blokdan chiqarildi", messages.SUCCESS)

    @admin.action(description="Barcha qurilmalardan chiqarish")
    def logout_everywhere(self, request, queryset):
        n = queryset.update(token_version=F("token_version") + 1)
        self.message_user(request, f"{n} ta foydalanuvchining sessiyalari yopildi", messages.SUCCESS)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "published_on", "task_type", "has_video", "is_published")
    list_editable = ("is_published",)
    search_fields = ("title", "summary", "key_points", "tasks")
    actions = ["announce"]
    fieldsets = [
        (None, {"fields": ("number", "title", "published_on", "youtube_id", "is_published")}),
        ("Mazmun", {"fields": ("summary", "key_points")}),
        ("Amaliy vazifa", {"fields": ("tasks", "task_type", "note_prompt")}),
    ]

    @admin.action(description="Tanlangan saboq haqida barchaga bot orqali xabar yuborish")
    def announce(self, request, queryset):
        # Navbatga qo'yiladi — bot jarayoni fon oqimida yuboradi (100k+ foydalanuvchida ham so'rov kutmaydi)
        for lesson in queryset.filter(is_published=True):
            Broadcast.objects.create(lesson=lesson, created_by=request.user.username)
            self.message_user(request, f"{lesson}: e'lon navbatga qo'yildi", messages.SUCCESS)

    @admin.display(boolean=True, description="Video")
    def has_video(self, obj):
        return bool(obj.youtube_id)


class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0


@admin.register(Debt)
class DebtAdmin(FastAdmin):
    list_display = ("name", "user", "kind", "total", "paid", "monthly_payment", "closed_at")
    list_filter = ("kind",)
    search_fields = ("name", "user__username", "user__tg_id")
    inlines = [DebtPaymentInline]


@admin.register(Income)
class IncomeAdmin(FastAdmin):
    list_display = ("user", "amount", "source", "date", "note")
    list_filter = ("source",)
    date_hierarchy = "date"


@admin.register(Expense)
class ExpenseAdmin(FastAdmin):
    list_display = ("user", "amount", "category", "need", "date", "note")
    list_filter = ("category", "need")
    date_hierarchy = "date"


@admin.register(Saving)
class SavingAdmin(FastAdmin):
    list_display = ("user", "amount", "bucket", "kind", "date")
    list_filter = ("bucket", "kind")
    raw_id_fields = ("user", "income")


@admin.register(RecurringExpense)
class RecurringAdmin(FastAdmin):
    list_display = ("user", "name", "amount", "day", "active", "last_month")


@admin.register(LessonProgress)
class LessonProgressAdmin(FastAdmin):
    list_display = ("user", "lesson", "completed_at")
    list_filter = ("lesson",)


@admin.register(ActivityLog)
class ActivityLogAdmin(FastAdmin):
    list_display = ("created_at", "user", "action")
    list_filter = ("action",)


@admin.register(Feedback)
class FeedbackAdmin(FastAdmin):
    list_display = ("created_at", "user", "rating", "comment", "is_read")
    list_filter = ("rating", "is_read")


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("created_at", "audience", "status", "sent", "failed", "total")
    list_filter = ("status",)
