from django.contrib import admin, messages

from .models import (
    ActivityLog, Broadcast, Debt, DebtPayment, Expense, Income, Lesson, LessonProgress, RecurringExpense, Saving, TgUser,
)

admin.site.site_header = "Elektron Baraka Daftari — ma'lumotlar bazasi"
admin.site.site_url = "/boshqaruv/"


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


@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    list_display = ("tg_id", "display_name", "username", "monthly_income", "notify", "bot_started", "created_at")
    search_fields = ("tg_id", "first_name", "last_name", "username")
    list_filter = ("notify", "bot_started", "bot_blocked")


class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "total", "paid", "monthly_payment", "closed_at")
    inlines = [DebtPaymentInline]


for model in (Income, Expense):
    admin.site.register(model, list_display=("user", "amount", "date"))
admin.site.register(Saving, list_display=("user", "amount", "bucket", "kind", "date"))
admin.site.register(RecurringExpense, list_display=("user", "name", "amount", "day", "active", "last_month"))

admin.site.register(LessonProgress, list_display=("user", "lesson", "completed_at"))
admin.site.register(ActivityLog, list_display=("user", "action", "created_at"), list_filter=("action",),
                    raw_id_fields=("user",), show_full_result_count=False)
admin.site.register(Broadcast, list_display=("created_at", "audience", "status", "sent", "failed", "total"))
