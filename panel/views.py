"""Boshqaruv paneli (/boshqaruv/): statistika, voronka, foydalanuvchilar, amallar, saboqlar, xabarlar.

Faqat staff foydalanuvchilar uchun. Og'ir hisob-kitoblar (dashboard, voronka) 60 soniya keshlanadi —
100 000+ foydalanuvchida ham panel yengil ishlaydi.
"""
import csv
import datetime as dt
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Exists, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import activity, seo, services
from core.models import (
    ActivityLog, Broadcast, Debt, Expense, Feedback, Lesson, LessonProgress, RecurringExpense, Saving,
    SeoSettings, SiteSettings, TgUser, VerificationFile, total_of,
)

from . import analytics
from .forms import (
    AdminCreateForm, BroadcastForm, LessonForm, MessageForm, PasswordSetForm, SeoForm, SiteSettingsForm,
    VerificationUploadForm,
)

LOGIN_URL = "/boshqaruv/kirish/"
security_log = logging.getLogger("security")
audit_log = logging.getLogger("panel.audit")


def audit(request, action, **meta):
    """Admin amallari jurnali (kim, qachon, nima qildi) — server logiga yoziladi."""
    audit_log.info("%s | %s | ip=%s | %s", request.user.username, action, activity.client_ip(request), meta)


def staff(view):
    return staff_member_required(view, login_url=LOGIN_URL)


def cached(key, seconds, fn):
    return cache.get_or_set(f"panel:{key}", fn, seconds)


# ---------------------------------------------------------------- kirish

LOGIN_FAILS_LIMIT = 5      # IP yoki login bo'yicha
LOGIN_BLOCK_SECONDS = 900  # 15 daqiqa


class LoginView(auth_views.LoginView):
    """Admin kirishi: 5 ta noto'g'ri urinishdan keyin IP ham, login ham 15 daqiqaga bloklanadi."""

    template_name = "panel/login.html"
    redirect_authenticated_user = True

    def _keys(self, request):
        username = (request.POST.get("username") or "").strip().lower()[:150]
        return [f"panel-fail:ip:{activity.client_ip(request)}", f"panel-fail:user:{username}"]

    def post(self, request, *args, **kwargs):
        if any(cache.get(k, 0) >= LOGIN_FAILS_LIMIT for k in self._keys(request)):
            security_log.warning("Panel kirishi bloklangan: ip=%s", activity.client_ip(request))
            return HttpResponseForbidden("Juda ko'p noto'g'ri urinish. 15 daqiqadan keyin qayta urinib ko'ring.")
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for key in self._keys(self.request):
            cache.set(key, cache.get(key, 0) + 1, LOGIN_BLOCK_SECONDS)
        security_log.warning("Panelga noto'g'ri kirish: ip=%s login=%s", activity.client_ip(self.request),
                             (self.request.POST.get("username") or "")[:50])
        return super().form_invalid(form)

    def form_valid(self, form):
        if not form.get_user().is_staff:
            form.add_error(None, "Bu hisobga boshqaruv paneliga kirish ruxsati yo'q")
            return self.form_invalid(form)
        for key in self._keys(self.request):
            cache.delete(key)
        security_log.info("Panelga kirildi: %s ip=%s", form.get_user().username, activity.client_ip(self.request))
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or "/boshqaruv/"


logout_view = auth_views.LogoutView.as_view(next_page=LOGIN_URL)


def admin_login(request, extra_context=None):
    """Django admin kirishi → panel kirishi (bitta, cheklangan kirish nuqtasi)."""
    return redirect_to_login(request.GET.get("next") or request.path, LOGIN_URL)


# ---------------------------------------------------------------- dashboard

def _dashboard_stats():
    now = timezone.now()
    today = timezone.localdate()
    day_start = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    users = TgUser.objects.all()
    counts = users.aggregate(
        total=Count("id"),
        new_today=Count("id", filter=Q(created_at__gte=day_start)),
        new_7=Count("id", filter=Q(created_at__gte=now - dt.timedelta(days=7))),
        new_30=Count("id", filter=Q(created_at__gte=now - dt.timedelta(days=30))),
        active_today=Count("id", filter=Q(last_seen__gte=day_start)),
        active_7=Count("id", filter=Q(last_seen__gte=now - dt.timedelta(days=7))),
        active_30=Count("id", filter=Q(last_seen__gte=now - dt.timedelta(days=30))),
        bot_started=Count("id", filter=Q(bot_started=True)),
        bot_blocked=Count("id", filter=Q(bot_blocked=True)),
        disabled=Count("id", filter=Q(is_active=False)),
        income_set=Count("id", filter=~Q(income_type="")),
    )

    start = today - dt.timedelta(days=29)
    start_dt = timezone.make_aware(dt.datetime.combine(start, dt.time.min))
    reg = dict(users.filter(created_at__gte=start_dt).annotate(d=TruncDate("created_at"))
               .values("d").annotate(c=Count("id")).values_list("d", "c"))
    logins = dict(ActivityLog.objects.filter(action="login", created_at__gte=start_dt)
                  .annotate(d=TruncDate("created_at")).values("d").annotate(c=Count("user", distinct=True))
                  .values_list("d", "c"))
    days = [start + dt.timedelta(days=i) for i in range(30)]
    chart = [{"day": d, "reg": reg.get(d, 0), "active": logins.get(d, 0)} for d in days]
    peak = max([1] + [max(c["reg"], c["active"]) for c in chart])
    for c in chart:
        c["reg_h"] = round(c["reg"] * 100 / peak)
        c["active_h"] = round(c["active"] * 100 / peak)

    week_ago = now - dt.timedelta(days=7)
    top_actions = list(ActivityLog.objects.filter(created_at__gte=week_ago)
                       .values("action").annotate(c=Count("id")).order_by("-c")[:8])
    labels = dict(ActivityLog.ACTIONS)
    for a in top_actions:
        a["label"] = labels.get(a["action"], a["action"])

    # So'm va dollar hech qachon qo'shilmaydi — har valyuta alohida
    month_start = today.replace(day=1)
    money = []
    for code, label in TgUser.CURRENCIES:
        money.append({
            "code": code, "label": label,
            "users": users.filter(currency=code).count(),
            "expenses_month": total_of(Expense.objects.filter(user__currency=code, date__gte=month_start)),
            "saved_total": total_of(Saving.objects.filter(user__currency=code)),
            "debts_left": Debt.objects.filter(user__currency=code).aggregate(s=Sum(F("total") - F("paid")))["s"] or 0,
        })
    rating = Feedback.objects.aggregate(avg=Avg("rating"), c=Count("id"), unread=Count("id", filter=Q(is_read=False)))
    return {"counts": counts, "chart": chart, "top_actions": top_actions, "money": money,
            "lessons_done": LessonProgress.objects.count(), "rating": rating, **analytics.dashboard_insights()}


@staff
def dashboard(request):
    stats = cached("dashboard", 60, _dashboard_stats)
    latest = TgUser.objects.order_by("-created_at")[:8]
    broadcasts = Broadcast.objects.filter(status__in=["pending", "sending"])[:3]
    return render(request, "panel/dashboard.html", {"nav": "dashboard", **stats, "latest": latest, "broadcasts": broadcasts})


# ---------------------------------------------------------------- voronka

PERIODS = {"7": 7, "30": 30, "90": 90, "all": None}


def _funnel(period):
    qs = TgUser.objects.all()
    days = PERIODS.get(period)
    if days:
        qs = qs.filter(created_at__gte=timezone.now() - dt.timedelta(days=days))
    user = OuterRef("pk")
    # Ketma-ket voronka: har bosqichga faqat oldingi bosqichlarni o'tganlar kiradi
    steps = [
        ("Ro'yxatdan o'tdi", Q()),
        ("Shartlarni qabul qildi", Q(accepted_disclaimer=True)),
        ("Daromadini sozladi", ~Q(income_type="")),
        ("Birinchi xarajatni yozdi", Q(Exists(Expense.objects.filter(user=user)))),
        ("Jamg'armaga pul qo'ydi", Q(Exists(Saving.objects.filter(user=user, kind="deposit")))),
        ("1-saboqni yakunladi", Q(Exists(LessonProgress.objects.filter(user=user)))),
        ("Ertasi kuni qaytib keldi", Q(last_seen__gte=F("created_at") + dt.timedelta(days=1))),
    ]
    rows = []
    first = None
    prev = None
    step_qs = qs
    for label, condition in steps:
        step_qs = step_qs.filter(condition)
        count = step_qs.count()
        first = count if first is None else first
        rows.append({
            "label": label, "count": count,
            "of_first": round(count * 100 / first) if first else 0,
            "of_prev": round(count * 100 / prev) if prev else 100,
        })
        prev = count
    extra = {
        "debts": qs.filter(Exists(Debt.objects.filter(user=user))).count(),
        "credit": qs.filter(Exists(Debt.objects.filter(user=user, kind="credit", principal__gt=0))).count(),
        "recurring": qs.filter(Exists(RecurringExpense.objects.filter(user=user))).count(),
        "bot": qs.filter(bot_started=True).count(),
    }
    return {"rows": rows, "extra": extra}


@staff
def funnel(request):
    period = request.GET.get("period", "30")
    if period not in PERIODS:
        period = "30"
    data = cached(f"funnel:{period}", 60, lambda: _funnel(period))
    return render(request, "panel/funnel.html", {"nav": "funnel", "period": period, **data})


# ---------------------------------------------------------------- foydalanuvchilar

@staff
def users(request):
    qs = TgUser.objects.all()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    sort = request.GET.get("sort", "new")
    now = timezone.now()
    currency = request.GET.get("currency", "")
    if q:
        cond = Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q.lstrip("@"))
        if q.lstrip("-").isdigit():
            cond |= Q(tg_id=int(q))
        try:
            cond |= Q(uid=uuid.UUID(q))
        except ValueError:
            pass
        qs = qs.filter(cond)
    if currency in dict(TgUser.CURRENCIES):
        qs = qs.filter(currency=currency)
    if status == "active7":
        qs = qs.filter(last_seen__gte=now - dt.timedelta(days=7))
    elif status == "inactive30":
        qs = qs.filter(last_seen__lt=now - dt.timedelta(days=30))
    elif status == "blocked":
        qs = qs.filter(bot_blocked=True)
    elif status == "disabled":
        qs = qs.filter(is_active=False)
    elif status == "no_income":
        qs = qs.filter(income_type="")
    elif status == "rated":
        qs = qs.filter(Exists(Feedback.objects.filter(user=OuterRef("pk"))))
    elif status == "loyal":
        qs = qs.filter(visits__gte=10)
    qs = qs.order_by({"seen": "-last_seen", "old": "created_at", "visits": "-visits"}.get(sort, "-created_at"))
    qs = qs.annotate(
        lessons_done=Subquery(
            LessonProgress.objects.filter(user=OuterRef("pk")).values("user").annotate(c=Count("id")).values("c")[:1]
        ),
        rating=Subquery(Feedback.objects.filter(user=OuterRef("pk")).order_by("-created_at").values("rating")[:1]),
    )
    if request.GET.get("export") == "csv":
        return _users_csv(request, qs)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "panel/users.html", {
        "nav": "users", "page": page, "q": q, "status": status, "sort": sort, "currency": currency,
        "params": params.urlencode(), "currencies": TgUser.CURRENCIES,
    })


def _users_csv(request, qs):
    """Filtrlangan ro'yxatni CSV qilib yuklab olish (faqat superuser — shaxsiy ma'lumot)."""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Eksport faqat bosh administrator uchun")
    audit(request, "users_export", count=qs.count())
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="foydalanuvchilar.csv"'
    response.write("﻿")  # Excel UTF-8 ni to'g'ri ochishi uchun
    writer = csv.writer(response)
    writer.writerow(["UUID", "Ism", "Username", "Telegram ID", "Valyuta", "Ro'yxatdan", "Oxirgi kirish",
                     "Kirishlar", "Saboqlar", "Baho", "Bot", "Faol"])
    for u in qs[:50_000].iterator(chunk_size=2000):
        writer.writerow([
            u.uid, _csv_safe(u.display_name), _csv_safe(u.username), u.tg_id, u.currency,
            timezone.localtime(u.created_at).strftime("%d.%m.%Y"), timezone.localtime(u.last_seen).strftime("%d.%m.%Y %H:%M"),
            u.visits, u.lessons_done or 0, u.rating or "", "ha" if u.bot_started else "yo'q", "ha" if u.is_active else "yo'q",
        ])
    return response


def _csv_safe(value):
    """CSV injection: Excel "=", "+", "-", "@" bilan boshlangan katakni formula deb bajaradi."""
    value = str(value or "")
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@staff
def user_detail(request, uid):
    u = get_object_or_404(TgUser, uid=uid)
    log_page = Paginator(u.activity.all(), 30).get_page(request.GET.get("page"))
    return render(request, "panel/user_detail.html", {
        "nav": "users", "u": u, **analytics.user_profile(u),
        "recurring": list(u.recurring.all()),
        "log_page": log_page, "labels": dict(ActivityLog.ACTIONS), "message_form": MessageForm(),
        "feedback": list(u.feedback.all()[:5]),
    })


@staff
@require_POST
def user_action(request, uid):
    u = get_object_or_404(TgUser, uid=uid)
    action = request.POST.get("action")
    audit(request, f"user_{action}", user=str(u.uid))
    if action == "toggle_active":
        u.is_active = not u.is_active
        u.token_version += 1  # o'chirilganda ochiq sessiyalar ham darhol yopiladi
        u.save(update_fields=["is_active", "token_version"])
        messages.success(request, "Blokdan chiqarildi" if u.is_active else "Bloklandi — ilovaga ham, botga ham kira olmaydi")
    elif action == "logout_all":
        u.token_version += 1
        u.save(update_fields=["token_version"])
        messages.success(request, "Barcha qurilmalardagi sessiyalar yopildi — qayta kirish kerak bo'ladi")
    elif action == "toggle_notify":
        u.notify = not u.notify
        u.save(update_fields=["notify"])
        messages.success(request, "Eslatmalar yoqildi" if u.notify else "Eslatmalar o'chirildi")
    elif action == "note":
        u.admin_note = request.POST.get("admin_note", "")[:5000]
        u.save(update_fields=["admin_note"])
        messages.success(request, "Izoh saqlandi")
    elif action == "message":
        form = MessageForm(request.POST)
        if form.is_valid():
            messages_result = _send_direct(u, form.cleaned_data["text"])
            (messages.success if messages_result is True else messages.error)(
                request, "Xabar yuborildi" if messages_result is True else messages_result)
    return redirect("panel:user", uid=u.uid)


def _send_direct(user, text):
    from html import escape

    from bot.telegram import BotAPI, TelegramError

    if not user.bot_started or user.tg_id < 0:
        return "Foydalanuvchi botni ishga tushirmagan"
    try:
        BotAPI().send(user.tg_id, escape(text))
        return True
    except (RuntimeError, TelegramError) as e:
        return f"Yuborilmadi: {e}"


# ---------------------------------------------------------------- amallar / kirishlar

@staff
def activity_log(request, only_auth=False):
    qs = ActivityLog.objects.select_related("user")
    action = request.GET.get("action", "")
    if only_auth:
        qs = qs.filter(action__in=["register", "login"])
        if action in ("register", "login"):
            qs = qs.filter(action=action)
    elif action:
        qs = qs.filter(action=action)
    # Keyset sahifalash: katta jadvalda COUNT(*) va OFFSET qilmaymiz
    before = request.GET.get("before")
    if before and before.isdigit():
        qs = qs.filter(id__lt=int(before))
    rows = list(qs.order_by("-id")[:51])
    has_more = len(rows) > 50
    rows = rows[:50]
    labels = dict(ActivityLog.ACTIONS)
    for r in rows:
        r.label = labels.get(r.action, r.action)
    return render(request, "panel/activity.html", {
        "nav": "auth" if only_auth else "activity", "rows": rows, "has_more": has_more,
        "next_before": rows[-1].id if rows else None, "action": action, "only_auth": only_auth,
        "actions": [(k, v) for k, v in ActivityLog.ACTIONS if not only_auth or k in ("register", "login")],
    })


@staff
def auth_log(request):
    return activity_log(request, only_auth=True)


# ---------------------------------------------------------------- saboqlar

@staff
def lessons(request):
    items = Lesson.objects.annotate(done=Count("progress")).order_by("number")
    return render(request, "panel/lessons.html", {"nav": "lessons", "items": items})


@staff
def lesson_edit(request, pk=None):
    lesson = get_object_or_404(Lesson, pk=pk) if pk else None
    initial = {}
    if lesson is None:
        last = Lesson.objects.order_by("-number").first()
        initial = {"number": (last.number + 1) if last else 1, "published_on": timezone.localdate(), "is_published": True}
    form = LessonForm(request.POST or None, instance=lesson, initial=initial)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        audit(request, "lesson_save", number=saved.number, created=lesson is None)
        if request.POST.get("then") == "announce" and saved.is_published:
            Broadcast.objects.create(lesson=saved, created_by=request.user.username)
            messages.success(request, f"{saved.number}-saboq saqlandi va e'loni navbatga qo'yildi")
            return redirect("panel:broadcasts")
        messages.success(request, f"{saved.number}-saboq saqlandi")
        if request.POST.get("then") == "preview":
            return redirect("panel:lesson_preview", pk=saved.pk)
        return redirect("panel:lessons")
    return render(request, "panel/lesson_form.html", {
        "nav": "lessons", "form": form, "lesson": lesson,
        "done_count": lesson.progress.count() if lesson else 0,
    })


@staff
def lesson_preview(request, pk):
    """Saboq foydalanuvchiga qanday ko'rinishi (nashrdan oldin tekshirish uchun)."""
    lesson = get_object_or_404(Lesson, pk=pk)
    return render(request, "panel/lesson_preview.html", {"nav": "lessons", "lesson": lesson})


@staff
@require_POST
def lesson_action(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    action = request.POST.get("action")
    audit(request, f"lesson_{action}", number=lesson.number)
    if action == "toggle":
        lesson.is_published = not lesson.is_published
        lesson.save(update_fields=["is_published"])
        messages.success(request, f"{lesson.number}-saboq " + ("nashr qilindi" if lesson.is_published else "yashirildi"))
    elif action == "delete":
        done = lesson.progress.count()
        if done and request.POST.get("confirm") != str(lesson.number):
            messages.error(request, f"Bu saboqni {done} kishi yakunlagan. O'chirish uchun saboq raqamini yozing.")
            return redirect("panel:lesson_edit", pk=lesson.pk)
        lesson.delete()
        messages.success(request, f"{lesson.number}-saboq o'chirildi")
    return redirect("panel:lessons")


@staff
@require_POST
def lesson_announce(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, is_published=True)
    if Broadcast.objects.filter(lesson=lesson, status__in=["pending", "sending"]).exists():
        messages.error(request, "Bu saboq e'loni allaqachon yuborilmoqda")
        return redirect("panel:broadcasts")
    Broadcast.objects.create(lesson=lesson, created_by=request.user.username)
    audit(request, "lesson_announce", number=lesson.number)
    messages.success(request, f"«{lesson.title}» e'loni navbatga qo'yildi — bot fon rejimida yuboradi")
    return redirect("panel:broadcasts")


# ---------------------------------------------------------------- baholar

@staff
def feedback_list(request):
    qs = Feedback.objects.select_related("user")
    rating = request.GET.get("rating", "")
    if rating in ("1", "2", "3", "4", "5"):
        qs = qs.filter(rating=int(rating))
    if request.GET.get("with_comment"):
        qs = qs.exclude(comment="")
    stats = cached("feedback", 60, lambda: {
        **Feedback.objects.aggregate(avg=Avg("rating"), total=Count("id")),
        "dist": dict(Feedback.objects.values_list("rating").annotate(c=Count("id"))),
    })
    total = stats["total"] or 0
    dist = [{"stars": s, "count": stats["dist"].get(s, 0),
             "pct": round(stats["dist"].get(s, 0) * 100 / total) if total else 0} for s in (5, 4, 3, 2, 1)]
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "panel/feedback.html", {
        "nav": "feedback", "page": page, "stats": stats, "dist": dist, "rating": rating,
        "with_comment": bool(request.GET.get("with_comment")), "params": params.urlencode(),
        "asked": TgUser.objects.filter(rating_asks__gt=0).count(),
    })


@staff
@require_POST
def feedback_read(request):
    Feedback.objects.filter(is_read=False).update(is_read=True)
    cache.delete("panel:dashboard")
    return redirect("panel:feedback")


# ---------------------------------------------------------------- SEO

@staff
def seo_settings(request):
    settings_obj = SeoSettings.load()
    form = SeoForm(request.POST or None, instance=settings_obj, prefix="seo")
    upload = VerificationUploadForm(prefix="vf")
    if request.method == "POST" and request.POST.get("section") == "file":
        upload = VerificationUploadForm(request.POST, request.FILES, prefix="vf")
        form = SeoForm(instance=settings_obj, prefix="seo")
        if upload.is_valid():
            f = upload.cleaned_data["file"]
            VerificationFile.objects.update_or_create(filename=f.name, defaults={"content": f.text})
            audit(request, "seo_file_upload", filename=f.name)
            messages.success(request, f"{f.name} yuklandi. Endi Search Console'da «Tasdiqlash» ni bosing.")
            return redirect("panel:seo")
    elif request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "seo_save")
        messages.success(request, "SEO sozlamalari saqlandi")
        return redirect("panel:seo")
    data = seo.seo_data()
    base = data["site_url"] or f"{request.scheme}://{request.get_host()}"
    return render(request, "panel/seo.html", {
        "nav": "seo", "form": form, "upload": upload, "files": VerificationFile.objects.all(),
        "base": base, "checks": _seo_checks(settings_obj, data),
    })


def _seo_checks(s, data):
    """Oddiy SEO nazorat ro'yxati: nima to'g'ri, nima yetishmaydi."""
    title_len, desc_len = len(data["title"]), len(data["description"])
    return [
        ("Sayt manzili ko'rsatilgan (canonical, sitemap)", bool(s.site_url), "«Sayt manzili» ga https://… yozing"),
        ("Sayt manzili HTTPS", s.site_url.startswith("https://"), "Google HTTPS saytlarni yuqoriroq qo'yadi"),
        ("Sarlavha uzunligi 30–60 belgi", 30 <= title_len <= 60, f"Hozir {title_len} belgi"),
        ("Tavsif uzunligi 70–160 belgi", 70 <= desc_len <= 160, f"Hozir {desc_len} belgi"),
        ("Google tasdiqlangan (fayl yoki meta-teg)",
         bool(s.google_verification) or VerificationFile.objects.filter(filename__startswith="google").exists(),
         "Search Console → «HTML fayl» usuli → faylni pastda yuklang"),
        ("Qidiruv tizimlariga ochiq", s.allow_indexing, "Hozir sayt indekslanmaydi (robots: Disallow /)"),
    ]


@staff
def site_settings(request):
    """Muallif sahifalari va «Biz bilan bog'lanish» — «Loyiha haqida» sahifasida ko'rinadi."""
    form = SiteSettingsForm(request.POST or None, instance=SiteSettings.load())
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "site_settings_save")
        messages.success(request, "Sozlamalar saqlandi — «Loyiha haqida» sahifasida darhol ko'rinadi")
        return redirect("panel:settings")
    return render(request, "panel/settings.html", {"nav": "settings", "form": form})


# ---------------------------------------------------------------- adminlar (faqat bosh admin)

def superuser(view):
    """Faqat bosh admin (superuser): adminlarni boshqarish, zaxira nusxa, eksport."""
    @staff
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden("Bu bo'lim faqat bosh admin uchun")
        return view(request, *args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper


@superuser
def admins(request):
    from django.contrib.auth.models import User

    initial = {}
    tg_uid = request.GET.get("from")
    if tg_uid:
        try:
            tg = TgUser.objects.filter(uid=uuid.UUID(tg_uid)).first()
        except ValueError:
            tg = None
        if tg:
            initial = {"username": tg.username or f"tg{tg.tg_id}", "first_name": tg.first_name}
    form = AdminCreateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(d["username"], password=d["password1"], first_name=d["first_name"])
        user.is_staff = True
        user.is_superuser = d["role"] == "superuser"
        user.save()
        audit(request, "admin_create", username=user.username, role=d["role"])
        messages.success(request, f"«{user.username}» admin qilindi. U /boshqaruv/kirish/ orqali shu login va parol bilan kiradi.")
        return redirect("panel:admins")
    items = User.objects.filter(is_staff=True).order_by("-is_superuser", "username")
    return render(request, "panel/admins.html", {"nav": "admins", "items": items, "form": form,
                                                  "password_form": PasswordSetForm()})


@superuser
@require_POST
def admin_action(request, pk):
    from django.contrib.auth.models import User

    target = get_object_or_404(User, pk=pk, is_staff=True)
    action = request.POST.get("action")
    is_self = target.pk == request.user.pk
    last_super = target.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1
    if is_self and action in ("toggle_active", "make_staff", "remove"):
        messages.error(request, "O'zingizni bloklay yoki huquqingizni olib tashlay olmaysiz")
        return redirect("panel:admins")
    if last_super and action in ("toggle_active", "make_staff", "remove"):
        messages.error(request, "Kamida bitta faol bosh admin qolishi kerak")
        return redirect("panel:admins")

    if action == "toggle_active":
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        messages.success(request, f"«{target.username}» " + ("blokdan chiqarildi" if target.is_active else "bloklandi — panelga kira olmaydi"))
    elif action == "make_super":
        target.is_superuser = True
        target.save(update_fields=["is_superuser"])
        messages.success(request, f"«{target.username}» bosh admin qilindi")
    elif action == "make_staff":
        target.is_superuser = False
        target.save(update_fields=["is_superuser"])
        messages.success(request, f"«{target.username}» oddiy admin qilindi")
    elif action == "remove":
        target.is_staff = target.is_superuser = False
        target.save(update_fields=["is_staff", "is_superuser"])
        messages.success(request, f"«{target.username}» adminlikdan olindi")
    elif action == "password":
        form = PasswordSetForm(request.POST, user=target)
        if not form.is_valid():
            messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
            return redirect("panel:admins")
        target.set_password(form.cleaned_data["password1"])
        target.save(update_fields=["password"])
        messages.success(request, f"«{target.username}» paroli o'zgartirildi")
    audit(request, f"admin_{action}", username=target.username)
    return redirect("panel:admins")


# ---------------------------------------------------------------- zaxira nusxa (faqat bosh admin)

@superuser
def backups(request):
    from core import backup

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            try:
                name = backup.create_backup()
                audit(request, "backup_create", name=name)
                messages.success(request, f"Zaxira nusxa tayyor: {name}")
            except backup.BackupError as e:
                messages.error(request, str(e))
        elif action == "delete":
            name = request.POST.get("name", "")
            if backup.delete_backup(name):
                audit(request, "backup_delete", name=name)
                messages.success(request, f"{name} o'chirildi")
        elif action == "telegram":
            name = request.POST.get("name", "")
            try:
                sent = backup.send_to_telegram(name)
                audit(request, "backup_telegram", name=name)
                messages.success(request, f"{name} Telegram'ga yuborildi ({sent} ta chat)")
            except backup.BackupError as e:
                messages.error(request, str(e))
        return redirect("panel:backups")
    return render(request, "panel/backups.html", {
        "nav": "backups", "items": backup.list_backups(), "keep": backup.KEEP,
        "telegram": backup.telegram_enabled(),
        "engine": "PostgreSQL" if "postgresql" in settings.DATABASES["default"]["ENGINE"] else "SQLite",
    })


@superuser
def backup_download(request, name):
    from django.http import FileResponse, Http404

    from core import backup

    path = backup.path_of(name)
    if not path:
        raise Http404
    audit(request, "backup_download", name=name)
    response = FileResponse(open(path, "rb"), as_attachment=True, filename=name, content_type="application/octet-stream")
    response["Cache-Control"] = "no-store"
    return response


@staff
@require_POST
def seo_file_delete(request, pk):
    item = get_object_or_404(VerificationFile, pk=pk)
    audit(request, "seo_file_delete", filename=item.filename)
    item.delete()
    messages.success(request, f"{item.filename} o'chirildi")
    return redirect("panel:seo")


# ---------------------------------------------------------------- ommaviy xabarlar

@staff
def broadcasts(request):
    form = BroadcastForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        b = form.save(commit=False)
        b.created_by = request.user.username
        b.save()
        messages.success(request, "Xabar navbatga qo'yildi — bot fon rejimida yuboradi")
        return redirect("panel:broadcasts")
    items = Broadcast.objects.select_related("lesson")[:50]
    sending = any(b.status in ("pending", "sending") for b in items)
    return render(request, "panel/broadcasts.html", {"nav": "broadcasts", "form": form, "items": items, "sending": sending})
