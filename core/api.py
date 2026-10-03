"""Mini App va veb sayt uchun JSON API.

Autentifikatsiya: `Authorization: Bearer <token>` sarlavhasi. Token cookie emas,
shuning uchun Telegram Web (iframe) ichida ham ishlaydi va CSRF kerak emas.
"""
import datetime as dt
import json
import re
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import activity, debtlink, rates, services
from .auth import make_api_token, user_from_request, verify_webapp_init_data
from .models import (
    Debt, DebtPayment, Expense, Feedback, Income, LessonProgress, LoginCode, RecurringExpense, Saving,
    TgUser, total_of,
)

MAX_AMOUNT = 10**13  # 10 trillion so'm - aqlga sig'maydigan qiymatlardan himoya
MAX_BODY = 32 * 1024  # API so'rovlari kichik JSON; kattasi — xato yoki hujum
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


class ApiError(Exception):
    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra


def endpoint(methods=("GET",), auth=True):
    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"error": "Metodga ruxsat yo'q"}, status=405)
            if len(request.body) > MAX_BODY:
                return JsonResponse({"error": "So'rov juda katta"}, status=413)
            request.data = {}
            if request.body and request.content_type == "application/json":
                try:
                    request.data = json.loads(request.body)
                except ValueError:
                    return JsonResponse({"error": "Noto'g'ri so'rov"}, status=400)
                if not isinstance(request.data, dict):
                    return JsonResponse({"error": "Noto'g'ri so'rov"}, status=400)
            if auth:
                request.tg_user = user_from_request(request)
                if request.tg_user is None:
                    return JsonResponse({"error": "Qaytadan kiring"}, status=401)
                # Bitta hisobdan haddan tashqari so'rov (skript/hujum) — 429
                uid = request.tg_user.pk
                writing = request.method != "GET"
                if not activity.allow(f"api:{uid}", 300, 60) or (writing and not activity.allow(f"api-w:{uid}", 60, 60)):
                    return JsonResponse({"error": "Juda ko'p so'rov. Bir daqiqadan keyin urinib ko'ring"}, status=429)
            elif not activity.allow(f"api-ip:{activity.client_ip(request)}", 120, 60):
                return JsonResponse({"error": "Juda ko'p so'rov. Bir daqiqadan keyin urinib ko'ring"}, status=429)
            try:
                return view(request, *args, **kwargs)
            except ApiError as e:
                return JsonResponse({"error": e.message, **e.extra}, status=e.status)

        return wrapper

    return decorator


# ---------------------------------------------------------------- yordamchilar

def amount_from(data, field="amount", allow_zero=False):
    raw = data.get(field)
    if isinstance(raw, str):
        raw = "".join(ch for ch in raw if ch.isdigit())
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("Summani to'g'ri kiriting")
    if value < 0 or (value == 0 and not allow_zero):
        raise ApiError("Summa noldan katta bo'lishi kerak")
    if value >= MAX_AMOUNT:
        raise ApiError("Summa juda katta")
    return value


def date_from(data, field="date"):
    raw = data.get(field)
    if not raw:
        return timezone.localdate()
    try:
        value = dt.date.fromisoformat(str(raw))
    except ValueError:
        raise ApiError("Sanani to'g'ri kiriting")
    if value > timezone.localdate() + dt.timedelta(days=1) or value.year < 2000:
        raise ApiError("Sana noto'g'ri")
    return value


def choice_from(data, field, choices, default):
    value = data.get(field) or default
    if value not in dict(choices):
        raise ApiError("Noto'g'ri tanlov")
    return value


def text_from(data, field, max_len=200):
    """Foydalanuvchi matni: boshqaruv va ko'rinmas (matn yo'nalishini buzuvchi) belgilar olib tashlanadi.

    HTML teglar saqlanaveradi, lekin hech qayerda HTML sifatida chiqarilmaydi: shablonlar avtomatik
    ekranlaydi, JS esa `esc()` orqali — shuning uchun XSS bo'lmaydi.
    """
    value = data.get(field)
    if value is None or isinstance(value, (dict, list)):
        return ""
    return CONTROL_CHARS.sub("", str(value)).strip()[:max_len]


def user_json(u):
    return {
        "id": str(u.uid),
        "tg_id": u.tg_id,
        "first_name": u.first_name,
        "name": u.display_name,
        "username": u.username,
        "photo_url": u.photo_url,
        "notify": u.notify,
        "monthly_income": u.monthly_income,
        "income_type": u.income_type,
        "save_percent": u.save_percent,
        "guard_months": u.guard_months,
        "currency": u.currency,
        "currency_chosen": u.currency_chosen,
        "accepted_disclaimer": u.accepted_disclaimer,
        "bot_started": u.bot_started,
    }


def income_json(i):
    return {"id": i.id, "type": "income", "amount": i.amount, "source": i.source,
            "label": i.get_source_display(), "note": i.note, "date": i.date.isoformat()}


def expense_json(e):
    return {"id": e.id, "type": "expense", "amount": e.amount, "category": e.category, "need": e.need,
            "label": e.get_category_display(), "note": e.note, "date": e.date.isoformat()}


def saving_json(s):
    return {"id": s.id, "type": "saving", "amount": s.amount, "bucket": s.bucket, "kind": s.kind,
            "label": f"{s.get_bucket_display()} · {s.get_kind_display().lower()}",
            "note": s.note, "date": s.date.isoformat()}


def credit_payload(d):
    return {"principal": d.principal, "interest_rate": str(d.interest_rate), "term_months": d.term_months,
            "extra_percent": d.extra_percent}


def debt_json(d):
    data = {
        "id": d.id, "name": d.name, "kind": d.kind, "kind_label": d.get_kind_display(),
        "total": d.total, "paid": d.paid, "remaining": d.remaining, "percent": d.percent,
        "monthly_payment": d.monthly_payment, "closed": d.remaining == 0, "credit": None,
        "lender": debtlink.first_name(d.lender) if d.lender_id else None,
        "pending": sum(1 for p in d.payments.all() if p.status == "pending") if d.lender_id else 0,
        "linkable": d.kind in debtlink.LINKABLE_KINDS and not d.lender_id and d.remaining > 0,
    }
    if d.is_credit:
        data["credit"] = services.debt_credit_calc(d)
    return data


def lesson_json(lesson, state, progress=None, full=False):
    data = {
        "number": lesson.number, "title": lesson.title, "state": state,
        "published_on": lesson.published_on.isoformat() if lesson.published_on else None,
        "task_title": lesson.task_title, "task_type": lesson.task_type,
    }
    if full and state in ("open", "done"):
        data.update({
            "summary": lesson.summary,
            "key_points": lesson.key_points_list,
            "tasks": lesson.tasks_list,
            "youtube_id": lesson.youtube_id,
            "video_url": lesson.video_url,
            "note_prompt": lesson.note_prompt,
            "note": progress.note if progress else "",
        })
    return data


def config_json():
    return {"bot_username": settings.BOT_USERNAME}


# ---------------------------------------------------------------- auth

@endpoint(["POST"], auth=False)
def auth_telegram(request):
    """Mini App ichidan kirish: initData tekshiriladi."""
    if not activity.allow(f"tg-auth:{activity.client_ip(request)}", 60, 60):
        raise ApiError("Juda ko'p so'rov. Birozdan keyin urinib ko'ring", 429)
    tg = verify_webapp_init_data(request.data.get("init_data", ""), settings.BOT_TOKEN)
    if not tg:
        raise ApiError("Telegram ma'lumotlari tasdiqlanmadi", 403)
    user, created = TgUser.upsert_from_telegram(tg)
    return login_response(user, "miniapp", created)


def login_response(user, source, created=False):
    if not user.is_active:
        raise ApiError("Hisobingiz vaqtincha o'chirilgan. Admin bilan bog'laning", 403)
    if created:
        activity.log(user, "register", source=source)
    activity.log(user, "login", source=source)
    return JsonResponse({"token": make_api_token(user), "user": user_json(user)})


@endpoint(["POST"], auth=False)
def auth_dev_login(request):
    """Dasturchi kirishi: Django admin foydalanuvchisi login/paroli bilan (faqat DEV_LOGIN=True)."""
    if not settings.DEV_LOGIN:
        raise ApiError("Topilmadi", 404)
    ip = request.META.get("REMOTE_ADDR", "")
    key = f"dev-login-fails:{ip}"
    if cache.get(key, 0) >= 10:
        raise ApiError("Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring", 429)

    staff = authenticate(request, username=text_from(request.data, "username", 150),
                         password=str(request.data.get("password") or ""))
    if staff is None or not staff.is_staff:
        cache.set(key, cache.get(key, 0) + 1, 600)
        raise ApiError("Login yoki parol noto'g'ri", 403)

    # Dasturchi hisoblari manfiy tg_id bilan saqlanadi — haqiqiy Telegram ID lar bilan to'qnashmaydi
    user, created = TgUser.objects.get_or_create(
        tg_id=-staff.pk, defaults={"first_name": staff.first_name or staff.username, "username": staff.username},
    )
    return login_response(user, "dev", created)


@endpoint(["POST"], auth=False)
def auth_login_code(request):
    """Saytga kirish: bir martalik kod yaratiladi, foydalanuvchi uni botda tasdiqlaydi."""
    if not settings.BOT_USERNAME:
        raise ApiError("Bot sozlanmagan (BOT_USERNAME)", 503)
    if not activity.allow(f"login-code:{activity.client_ip(request)}", 20, 600):
        raise ApiError("Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring", 429)
    cutoff = timezone.now() - dt.timedelta(seconds=settings.LOGIN_CODE_TTL * 3)
    LoginCode.objects.filter(created_at__lt=cutoff).delete()
    code = LoginCode.objects.create(code=secrets.token_urlsafe(24))
    return JsonResponse({
        "code": code.code,
        "bot_link": f"https://t.me/{settings.BOT_USERNAME}?start=login_{code.code}",
        "expires_in": settings.LOGIN_CODE_TTL,
    })


@endpoint(["GET"], auth=False)
def auth_login_status(request):
    code = LoginCode.objects.filter(code=request.GET.get("code", "")).select_related("user").first()
    if not code or code.consumed:
        return JsonResponse({"status": "invalid"})
    if (timezone.now() - code.created_at).total_seconds() > settings.LOGIN_CODE_TTL:
        return JsonResponse({"status": "expired"})
    if not code.confirmed or not code.user:
        return JsonResponse({"status": "pending"})
    code.consumed = True
    code.save(update_fields=["consumed"])
    response = login_response(code.user, "web")
    return JsonResponse({"status": "ok", **json.loads(response.content)})


# ---------------------------------------------------------------- profil / dashboard

@endpoint(["GET", "POST"])
def me(request):
    user = request.tg_user
    if request.method == "POST":
        fields = []
        for name in ("notify", "accepted_disclaimer", "onboarding_hidden"):
            if name in request.data:
                setattr(user, name, bool(request.data[name]))
                fields.append(name)
        if "income_type" in request.data:
            user.income_type = choice_from(request.data, "income_type", TgUser.INCOME_TYPES, "")
            fields.append("income_type")
            if user.income_type == "irregular":
                user.monthly_income = 0  # oylik olmaydi — faqat haqiqiy kirimlar bo'yicha hisoblanadi
                fields.append("monthly_income")
        if "monthly_income" in request.data and user.income_type != "irregular":
            user.monthly_income = amount_from(request.data, "monthly_income", allow_zero=True)
            fields.append("monthly_income")
        if "save_percent" in request.data:
            try:
                percent = int(request.data["save_percent"])
            except (TypeError, ValueError):
                raise ApiError("Foizni to'g'ri kiriting")
            if not 1 <= percent <= 50:
                raise ApiError("Foiz 1 dan 50 gacha bo'lishi kerak")
            user.save_percent = percent
            fields.append("save_percent")
        if "guard_months" in request.data:
            try:
                months = int(request.data["guard_months"])
            except (TypeError, ValueError):
                raise ApiError("Oylar sonini to'g'ri kiriting")
            if not 1 <= months <= 12:
                raise ApiError("Qo'riqchi pul 1 dan 12 oygacha bo'lishi kerak")
            user.guard_months = months
            fields.append("guard_months")
        if fields:
            fields = list(dict.fromkeys(fields))
            user.save(update_fields=fields)
            activity.log(user, "settings", fields=fields)

    activity.touch_last_seen(user)
    services.ensure_recurring(user)
    today = timezone.localdate()
    states = services.lesson_states(user)
    done = sum(1 for _, s, _ in states if s == "done")
    current = next(((l, s) for l, s, _ in states if s == "open"), None)
    return JsonResponse({
        "user": user_json(user),
        "config": config_json(),
        "lessons": {
            "done": done,
            "total": len(states),
            "current": lesson_json(*current) if current else None,
        },
        "reserve_total": total_of(user.savings),
        "savings": services.savings_summary(user),
        "onboarding": services.onboarding_steps(user),
        "rate": rates.usd_rate(),
        "recurring_total": total_of(user.recurring.filter(active=True)),
        "debts": services.debts_summary(user),
        "month": services.month_totals(user, today.year, today.month),
        "ask_rating": services.should_ask_rating(user),
    })


@endpoint(["POST"])
def feedback(request):
    """Baho (1–5) va ixtiyoriy fikr."""
    user = request.tg_user
    if not activity.allow(f"feedback:{user.pk}", 5, 86400):
        raise ApiError("Bugun yetarlicha fikr qoldirdingiz, rahmat!", 429)
    try:
        rating = int(request.data.get("rating"))
    except (TypeError, ValueError):
        raise ApiError("Bahoni tanlang")
    if not 1 <= rating <= 5:
        raise ApiError("Baho 1 dan 5 gacha bo'lishi kerak")
    item = Feedback.objects.create(
        user=user, rating=rating, comment=text_from(request.data, "comment", 1000),
        page=text_from(request.data, "page", 32),
    )
    user.rating_asked_at = timezone.now()
    user.save(update_fields=["rating_asked_at"])
    activity.log(user, "feedback", rating=rating)
    return JsonResponse({"ok": True, "id": item.pk})


@endpoint(["POST"])
def feedback_shown(request):
    """Baho oynasi ko'rsatildi (yoki "Keyinroq" bosildi) — bir hafta qayta so'ralmaydi."""
    user = request.tg_user
    user.rating_asked_at = timezone.now()
    user.rating_asks = min(user.rating_asks + 1, 100)
    user.save(update_fields=["rating_asked_at", "rating_asks"])
    return JsonResponse({"ok": True})


@endpoint(["POST"])
def logout_all(request):
    """Barcha qurilmalardan chiqish: eski tokenlar darhol ishlamay qoladi."""
    user = request.tg_user
    TgUser.objects.filter(pk=user.pk).update(token_version=F("token_version") + 1)
    activity.log(user, "logout_all")
    return JsonResponse({"ok": True})


@endpoint(["POST"])
def app_installed(request):
    """Ilova telefonga o'rnatildi (PWA o'zidan ochildi yoki brauzer "o'rnatildi" dedi). Faqat birinchi marta yoziladi."""
    user = request.tg_user
    platform = choice_from(request.data, "platform", [("android", ""), ("ios", ""), ("desktop", "")], "desktop")
    updated = TgUser.objects.filter(pk=user.pk, app_installed_at__isnull=True).update(app_installed_at=timezone.now())
    if updated:
        activity.log(user, "app_install", platform=platform)
    return JsonResponse({"ok": True})


@endpoint(["POST"])
def set_currency(request):
    """Hisob valyutasini tanlash/o'zgartirish.

    Ma'lumot bo'lsa, barcha summalar MB kursi bo'yicha yangi valyutaga o'tkaziladi — so'm va dollar
    hech qachon bitta hisobda aralashmaydi.
    """
    user = request.tg_user
    currency = choice_from(request.data, "currency", TgUser.CURRENCIES, "UZS")
    converted = False
    if currency != user.currency and services.user_has_money_data(user):
        rate = rates.usd_rate()
        if not rate:
            raise ApiError("Markaziy bank kursini olib bo'lmadi. Birozdan keyin urinib ko'ring", 503)
        services.convert_user_money(user, currency, rate["rate"])
        converted = True
    else:
        user.currency, user.currency_chosen = currency, True
        user.save(update_fields=["currency", "currency_chosen"])
    activity.log(user, "settings", fields=["currency"], currency=currency, converted=converted)
    user.refresh_from_db()
    return JsonResponse({"user": user_json(user), "converted": converted})


@endpoint(["GET"], auth=False)
def usd_rate(request):
    return JsonResponse({"rate": rates.usd_rate()})


REPORT_PERIODS = {"7": 7, "10": 10, "30": 30}


@endpoint(["GET"])
def report(request):
    """Umumiy hisobot: ?period=7|10|30 (oxirgi N kun) yoki ?period=month&month=YYYY-MM."""
    user = request.tg_user
    services.ensure_recurring(user)
    period = request.GET.get("period", "7")
    today = timezone.localdate()
    if period == "month":
        year, month = services.parse_month(request.GET.get("month"))
        start, end = services.month_bounds(year, month)
        end -= dt.timedelta(days=1)
        data = services.period_report(user, start, end)
        data["month"] = services.month_totals(user, year, month)
        data["month_key"] = f"{year:04d}-{month:02d}"
    elif period in REPORT_PERIODS:
        start = today - dt.timedelta(days=REPORT_PERIODS[period] - 1)
        data = services.period_report(user, start, today)
    else:
        raise ApiError("Noto'g'ri davr")
    return JsonResponse({"period": period, **data})


@endpoint(["GET"], auth=False)
def site_info(request):
    """«Loyiha haqida»: muallif sahifalari va biz bilan bog'lanish (admin panelda sozlanadi)."""
    from .seo import site_links

    return JsonResponse(site_links())


# ---------------------------------------------------------------- hamyon

PAGE_SIZE = 20
ENTRY_TYPES = ("income", "expense", "saving")


def month_entries(user, start, end, entry_type=""):
    """Oy tarixi (yangilari birinchi). Jamg'arma ichidagi o'tkazmalar bu yerda ko'rsatilmaydi."""
    entries = []
    if entry_type in ("", "income"):
        entries += [income_json(i) for i in user.incomes.filter(date__gte=start, date__lt=end)]
    if entry_type in ("", "expense"):
        entries += [expense_json(e) for e in user.expenses.filter(date__gte=start, date__lt=end)]
    if entry_type in ("", "saving"):
        entries += [saving_json(s) for s in user.savings.filter(date__gte=start, date__lt=end).exclude(kind="transfer")]
    entries.sort(key=lambda x: (x["date"], x["type"] != "income", x["id"]), reverse=True)
    return entries


def page_of(items, request):
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except ValueError:
        offset = 0
    chunk = items[offset:offset + PAGE_SIZE]
    return {"entries": chunk, "offset": offset, "has_more": offset + PAGE_SIZE < len(items), "count": len(items)}


@endpoint(["GET"])
def wallet(request):
    user = request.tg_user
    services.ensure_recurring(user)
    year, month = services.parse_month(request.GET.get("month"))
    start, end = services.month_bounds(year, month)
    expenses = list(user.expenses.filter(date__gte=start, date__lt=end))

    by_cat = {key: 0 for key, _ in Expense.CATEGORIES}
    by_need = {key: 0 for key, _ in Expense.NEEDS}
    by_need[""] = 0
    for e in expenses:
        by_cat[e.category] += e.amount
        by_need[e.need] += e.amount

    return JsonResponse({
        "month": f"{year:04d}-{month:02d}",
        "totals": services.month_totals(user, year, month),
        "reserve_total": total_of(user.savings),
        "categories": [
            {"key": k, "label": label, "amount": by_cat[k]} for k, label in Expense.CATEGORIES
        ],
        # Zarur / Kerak / Havas bo'yicha (unmarked — belgilanmagan xarajatlar)
        "needs": {**{k: by_need[k] for k, _ in Expense.NEEDS}, "unmarked": by_need[""]},
        "history": page_of(month_entries(user, start, end), request),
    })


@endpoint(["GET"])
def entries(request):
    """Tarix sahifalab: ?month=YYYY-MM&type=income|expense|saving&offset=20"""
    year, month = services.parse_month(request.GET.get("month"))
    start, end = services.month_bounds(year, month)
    entry_type = request.GET.get("type", "")
    if entry_type and entry_type not in ENTRY_TYPES:
        raise ApiError("Noto'g'ri filtr")
    return JsonResponse(page_of(month_entries(request.tg_user, start, end, entry_type), request))


@endpoint(["POST"])
def income_create(request):
    d = request.data
    income = Income.objects.create(
        user=request.tg_user,
        amount=amount_from(d),
        source=choice_from(d, "source", Income.SOURCES, "salary"),
        note=text_from(d, "note"),
        date=date_from(d),
    )
    activity.log(request.tg_user, "income_add", amount=income.amount)
    return JsonResponse({"income": income_json(income), "suggested_saving": services.save_amount(income.amount, request.tg_user.save_percent),
        "save_percent": request.tg_user.save_percent,
    })


@endpoint(["POST"])
def expense_create(request):
    d = request.data
    expense = Expense.objects.create(
        user=request.tg_user,
        amount=amount_from(d),
        category=choice_from(d, "category", Expense.CATEGORIES, "other"),
        need=choice_from(d, "need", Expense.NEEDS + [("", "")], ""),
        note=text_from(d, "note"),
        date=date_from(d),
    )
    activity.log(request.tg_user, "expense_add", amount=expense.amount, category=expense.category)
    return JsonResponse({"expense": expense_json(expense)})


def bucket_from(d, field="bucket", allow_auto=False, user=None):
    value = d.get(field) or ("auto" if allow_auto else "guard")
    if value == "auto" and allow_auto:
        return services.savings_summary(user)["suggested_bucket"]
    return choice_from({field: value}, field, Saving.BUCKETS, "guard")


def bucket_balance(user, bucket):
    return total_of(user.savings.filter(bucket=bucket))


def savings_response(user, **extra):
    return JsonResponse({**extra, "reserve_total": total_of(user.savings), "savings": services.savings_summary(user)})


@endpoint(["POST"])
def saving_create(request):
    """Jamg'armaga qo'shish. bucket: guard | grow | auto (qo'riqchi pul to'lguncha unga)."""
    d, user = request.data, request.tg_user
    income = None
    if d.get("income_id"):
        income = Income.objects.filter(pk=d["income_id"], user=user).first()
    saving = Saving.objects.create(
        user=user, amount=amount_from(d), income=income, kind="deposit",
        bucket=bucket_from(d, allow_auto=True, user=user),
        note=text_from(d, "note"), date=date_from(d),
    )
    activity.log(user, "saving_add", amount=saving.amount, bucket=saving.bucket)
    return savings_response(user, saving=saving_json(saving))


@endpoint(["POST"])
def saving_withdraw(request):
    """Jamg'armadan olish (masalan, og'ir kunda qo'riqchi puldan)."""
    d, user = request.data, request.tg_user
    bucket = bucket_from(d)
    amount = amount_from(d)
    if amount > bucket_balance(user, bucket):
        raise ApiError(f"{dict(Saving.BUCKETS)[bucket]}da buncha pul yo'q")
    saving = Saving.objects.create(
        user=user, amount=-amount, bucket=bucket, kind="withdraw",
        note=text_from(d, "note"), date=date_from(d),
    )
    activity.log(user, "saving_withdraw", amount=amount, bucket=bucket)
    return savings_response(user, saving=saving_json(saving))


@endpoint(["POST"])
def saving_transfer(request):
    """Qo'riqchi pul <-> o'sadigan pul o'rtasida o'tkazish."""
    d, user = request.data, request.tg_user
    source = bucket_from(d, "from")
    target = "grow" if source == "guard" else "guard"
    amount = amount_from(d)
    if amount > bucket_balance(user, source):
        raise ApiError(f"{dict(Saving.BUCKETS)[source]}da buncha pul yo'q")
    group = secrets.token_hex(8)
    note = text_from(d, "note")
    with transaction.atomic():
        Saving.objects.create(user=user, amount=-amount, bucket=source, kind="transfer", group=group, note=note)
        Saving.objects.create(user=user, amount=amount, bucket=target, kind="transfer", group=group, note=note)
    activity.log(user, "saving_transfer", amount=amount, source=source)
    return savings_response(user)


@endpoint(["GET"])
def jamgarma(request):
    user = request.tg_user
    items = [saving_json(s) for s in user.savings.all()]
    return JsonResponse({"savings": services.savings_summary(user), "history": page_of(items, request)})


@endpoint(["POST", "DELETE"])
def entry_detail(request, kind, pk):
    """Yozuvni tahrirlash (POST: kirim/xarajat) yoki o'chirish (DELETE)."""
    model = {"income": Income, "expense": Expense, "saving": Saving}.get(kind)
    if not model:
        raise ApiError("Topilmadi", 404)
    user = request.tg_user
    obj = get_object_or_404(model, pk=pk, user=user)

    if request.method == "DELETE":
        if kind == "saving" and obj.group:
            Saving.objects.filter(user=user, group=obj.group).delete()  # o'tkazmaning ikkala qismi
        else:
            obj.delete()
        activity.log(user, "entry_delete", kind=kind, amount=obj.amount)
        return JsonResponse({"ok": True})

    d = request.data
    if kind == "saving":
        raise ApiError("Jamg'arma yozuvini o'chirib, qaytadan kiriting")
    if "amount" in d:
        obj.amount = amount_from(d)
    if "note" in d:
        obj.note = text_from(d, "note")
    if "date" in d:
        obj.date = date_from(d)
    if kind == "income" and "source" in d:
        obj.source = choice_from(d, "source", Income.SOURCES, obj.source)
    if kind == "expense":
        if "category" in d:
            obj.category = choice_from(d, "category", Expense.CATEGORIES, obj.category)
        if "need" in d:
            obj.need = choice_from(d, "need", Expense.NEEDS + [("", "")], "")
    obj.save()
    activity.log(user, f"{kind}_edit", amount=obj.amount)
    return JsonResponse({kind: income_json(obj) if kind == "income" else expense_json(obj)})


# ---------------------------------------------------------------- oylik majburiy xarajatlar

def recurring_json(r):
    return {"id": r.id, "name": r.name, "amount": r.amount, "category": r.category, "need": r.need,
            "day": r.day, "active": r.active, "done_this_month": r.last_month == timezone.localdate().strftime("%Y-%m")}


def recurring_fill(item, d):
    if "name" in d:
        item.name = text_from(d, "name", 100)
        if not item.name:
            raise ApiError("Nomini kiriting")
    if "amount" in d:
        item.amount = amount_from(d)
    if "category" in d:
        item.category = choice_from(d, "category", Expense.CATEGORIES, "other")
    if "need" in d:
        item.need = choice_from(d, "need", Expense.NEEDS + [("", "")], "")
    if "day" in d:
        try:
            item.day = int(d["day"])
        except (TypeError, ValueError):
            raise ApiError("Kunni to'g'ri kiriting")
        if not 1 <= item.day <= 28:
            raise ApiError("Kun 1 dan 28 gacha bo'lishi kerak")
    if "active" in d:
        item.active = bool(d["active"])


@endpoint(["GET", "POST"])
def recurring(request):
    user = request.tg_user
    if request.method == "POST":
        if not request.data.get("name") or not request.data.get("amount"):
            raise ApiError("Nomi va summasini kiriting")
        item = RecurringExpense(user=user)
        recurring_fill(item, request.data)
        today = timezone.localdate()
        if item.day <= today.day and not request.data.get("this_month"):
            # To'lov kuni bu oy o'tib ketgan — odatda foydalanuvchi uni allaqachon yozgan: ikki marta yozmaymiz
            item.last_month = today.strftime("%Y-%m")
        item.save()
        services.ensure_recurring(user)
        item.refresh_from_db()
        activity.log(user, "recurring_add", amount=item.amount, name=item.name[:40])
        return JsonResponse({"item": recurring_json(item)})
    items = list(user.recurring.all())
    return JsonResponse({
        "items": [recurring_json(r) for r in items],
        "total": sum(r.amount for r in items if r.active),
        "suggestions": services.recurring_suggestions(user, items),
    })


@endpoint(["POST", "DELETE"])
def recurring_detail(request, pk):
    item = get_object_or_404(RecurringExpense, pk=pk, user=request.tg_user)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    recurring_fill(item, request.data)
    item.save()
    return JsonResponse({"item": recurring_json(item)})


# ---------------------------------------------------------------- qarzlar

def credit_params(d):
    """Kredit maydonlarini o'qiydi: olingan summa, yillik foiz, muddat (oy), qo'shib to'lash foizi."""
    principal = amount_from(d, "principal")
    try:
        rate = Decimal(str(d.get("interest_rate") or 0)).quantize(Decimal("0.01"))
        term = int(d.get("term_months") or 0)
        extra = int(d.get("extra_percent") or 0)
    except (InvalidOperation, TypeError, ValueError):
        raise ApiError("Kredit ma'lumotlarini to'g'ri kiriting")
    if not Decimal(0) <= rate <= Decimal(200):
        raise ApiError("Yillik foiz 0 dan 200 gacha bo'lishi kerak")
    if not 1 <= term <= 600:
        raise ApiError("Muddatni to'g'ri kiriting (1–600 oy)")
    if not 0 <= extra <= 300:
        raise ApiError("Qo'shib to'lash foizi 0 dan 300 gacha bo'lishi kerak")
    return principal, rate, term, extra


def setup_credit(debt, principal, rate, term, extra, paid):
    """Kredit bo'yicha oylik to'lov, qoldiq va jami summani hisoblab debt ga yozadi."""
    payment = services.annuity_payment(principal, rate, term)
    paid = min(paid, payment * term)
    balance = services.balance_after_paid(principal, rate, payment, paid)
    _, remaining = services.simulate_credit(balance, rate, payment)
    debt.principal, debt.interest_rate, debt.term_months, debt.extra_percent = principal, rate, term, extra
    debt.monthly_payment, debt.balance, debt.paid = payment, balance, paid
    debt.total = paid + (remaining or 0)


@endpoint(["GET", "POST"])
def debts(request):
    user = request.tg_user
    if request.method == "POST":
        d = request.data
        name = text_from(d, "name", 100)
        if not name:
            raise ApiError("Qarz nomini kiriting")
        kind = choice_from(d, "kind", Debt.KINDS, "credit")
        if kind == "credit" and d.get("principal"):
            principal, rate, term, extra = credit_params(d)
            payment = services.annuity_payment(principal, rate, term)
            if d.get("paid_months"):
                try:
                    paid = min(int(d["paid_months"]), term) * payment
                except (TypeError, ValueError):
                    raise ApiError("To'langan oylar sonini to'g'ri kiriting")
            else:
                paid = amount_from(d, "paid", allow_zero=True) if d.get("paid") else 0
            debt = Debt(user=user, name=name, kind=kind)
            setup_credit(debt, principal, rate, term, extra, paid)
            debt.closed_at = timezone.now() if debt.remaining == 0 else None
            debt.save()
            activity.log(user, "debt_add", kind=kind, amount=principal)
            return JsonResponse({"debt": debt_json(debt)})

        total = amount_from(d, "total")
        paid = amount_from(d, "paid", allow_zero=True) if d.get("paid") else 0
        if paid > total:
            raise ApiError("To'langan summa umumiy summadan katta bo'lishi mumkin emas")
        debt = Debt.objects.create(
            user=user, name=name, total=total, paid=paid, kind=kind,
            monthly_payment=amount_from(d, "monthly_payment", allow_zero=True) if d.get("monthly_payment") else 0,
            closed_at=timezone.now() if paid >= total else None,
        )
        activity.log(user, "debt_add", kind=kind, amount=total)
        return JsonResponse({"debt": debt_json(debt)})

    items = sorted(user.debts.select_related("lender").prefetch_related("payments"),
                   key=lambda x: (x.remaining == 0, x.remaining, x.id))
    lent = sorted(user.lent_debts.select_related("user").prefetch_related("payments"),
                  key=lambda x: (x.remaining == 0, -x.remaining, x.id))
    return JsonResponse({
        "debts": [debt_json(x) for x in items],
        "summary": services.debts_summary(user),
        "lent": [debtlink.lent_json(x) for x in lent],
        "invites": debtlink.open_invites(user),
        "can_link": bool(settings.BOT_USERNAME),
    })


@endpoint(["POST", "DELETE"])
def debt_detail(request, pk):
    debt = get_object_or_404(Debt, pk=pk, user=request.tg_user)
    if request.method == "DELETE":
        if debt.lender_id:
            raise ApiError("Bu qarz bog'langan. Avval bog'lanishni uzing — ikkinchi tomon xabar oladi")
        debt.delete()
        return JsonResponse({"ok": True})
    d = request.data
    if debt.lender_id and "total" in d and amount_from(d, "total") != debt.total:
        raise ApiError("Bog'langan qarzning summasini o'zgartirib bo'lmaydi. Avval bog'lanishni uzing")
    if "name" in d:
        debt.name = text_from(d, "name", 100) or debt.name
    if debt.is_credit or (debt.kind == "credit" and d.get("principal")):
        if d.get("principal"):
            principal, rate, term, extra = credit_params(d)
            setup_credit(debt, principal, rate, term, extra, debt.paid)
        elif "extra_percent" in d:
            debt.extra_percent = credit_params({**credit_payload(debt), "extra_percent": d["extra_percent"]})[3]
        debt.closed_at = (debt.closed_at or timezone.now()) if debt.remaining == 0 else None
        debt.save()
        return JsonResponse({"debt": debt_json(debt)})
    if "kind" in d:
        debt.kind = choice_from(d, "kind", Debt.KINDS, debt.kind)
    if "total" in d:
        debt.total = amount_from(d, "total")
    if "monthly_payment" in d:
        debt.monthly_payment = amount_from(d, "monthly_payment", allow_zero=True)
    debt.paid = min(debt.paid, debt.total)
    debt.closed_at = (debt.closed_at or timezone.now()) if debt.remaining == 0 else None
    debt.save()
    return JsonResponse({"debt": debt_json(debt)})


@endpoint(["POST"])
def debt_pay(request, pk):
    with transaction.atomic():
        debt = get_object_or_404(Debt.objects.select_for_update(), pk=pk, user=request.tg_user)
        if debt.remaining == 0:
            raise ApiError("Bu qarz allaqachon yopilgan")
        amount = amount_from(request.data)
        if debt.is_credit:
            # Qo'shimcha to'lov asosiy qarzni kamaytiradi -> qolgan foiz va jami summa qayta hisoblanadi
            amount = min(amount, services.payoff_amount(debt.balance, debt.interest_rate))
            debt.balance = services.apply_credit_payment(debt.balance, debt.interest_rate, debt.monthly_payment, amount)
            debt.paid += amount
            _, remaining = services.simulate_credit(debt.balance, debt.interest_rate, debt.monthly_payment)
            debt.total = debt.paid + (remaining or 0)
        else:
            amount = min(amount, debt.remaining)
            debt.paid += amount
        payment = DebtPayment.objects.create(debt=debt, amount=amount, date=date_from(request.data),
                                             status="pending" if debt.lender_id else "ok")
        just_closed = debt.remaining == 0
        if just_closed:
            debt.closed_at = timezone.now()
        debt.save()
    activity.log(request.tg_user, "debt_close" if just_closed else "debt_pay", amount=amount, debt=debt.name[:40])
    if debt.lender_id:
        debtlink.payment_created(payment)
    return JsonResponse({"debt": debt_json(debt), "paid_now": amount, "just_closed": just_closed})


# ---------------------------------------------------------------- qarzni bog'lash (core/debtlink.py)

def _link_response(link):
    url = debtlink.invite_url(link)
    if not url:
        raise ApiError("Bot sozlanmagan (BOT_USERNAME)")
    return JsonResponse({"url": url, "text": debtlink.share_text(link)})


@endpoint(["POST"])
def debt_invite(request, pk):
    debt = get_object_or_404(Debt, pk=pk, user=request.tg_user)
    try:
        return _link_response(debtlink.invite_for_debt(request.tg_user, debt))
    except debtlink.LinkError as e:
        raise ApiError(str(e))


@endpoint(["POST"])
def debt_lend(request):
    amount = amount_from(request.data)
    note = text_from(request.data, "note", 100)
    if not note:
        raise ApiError("Kimga qarz berganingizni yozing")
    try:
        return _link_response(debtlink.invite_lent(request.tg_user, amount, note))
    except debtlink.LinkError as e:
        raise ApiError(str(e))


@endpoint(["DELETE"])
def debt_invite_cancel(request, pk):
    try:
        debtlink.cancel_invite(request.tg_user, pk)
    except debtlink.LinkError as e:
        raise ApiError(str(e))
    return JsonResponse({"ok": True})


@endpoint(["POST"])
def debt_unlink(request, pk):
    from django.db.models import Q
    user = request.tg_user
    debt = get_object_or_404(Debt.objects.select_related("user", "lender"), Q(user=user) | Q(lender=user), pk=pk)
    try:
        debtlink.unlink(user, debt)
    except debtlink.LinkError as e:
        raise ApiError(str(e))
    return JsonResponse({"ok": True})


@endpoint(["POST"])
def debt_payment_review(request, pk):
    try:
        message = debtlink.review_payment(request.tg_user, pk, bool(request.data.get("ok")))
    except debtlink.LinkError as e:
        raise ApiError(str(e))
    return JsonResponse({"ok": True, "message": message})


@endpoint(["GET"])
def debt_plan(request):
    extra = request.GET.get("extra")
    extra = amount_from({"amount": extra}, allow_zero=True) if extra not in (None, "") else None
    return JsonResponse(services.snowball_plan(request.tg_user, extra))


# ---------------------------------------------------------------- saboqlar

@endpoint(["GET"])
def lessons(request):
    states = services.lesson_states(request.tg_user)
    return JsonResponse({"lessons": [lesson_json(l, s) for l, s, _ in states]})


@endpoint(["GET"])
def lesson_detail(request, number):
    for lesson, state, progress in services.lesson_states(request.tg_user):
        if lesson.number == number:
            if state == "locked":
                raise ApiError("Avval oldingi saboqning vazifasini bajaring — shunda bu saboq ochiladi", 403)
            return JsonResponse({"lesson": lesson_json(lesson, state, progress, full=True)})
    raise ApiError("Saboq topilmadi", 404)


@endpoint(["POST"])
def lesson_complete(request, number):
    user = request.tg_user
    states = services.lesson_states(user)
    for lesson, state, progress in states:
        if lesson.number != number:
            continue
        if state == "done":
            return JsonResponse({"ok": True, "already": True})
        if state == "locked":
            raise ApiError("Avval oldingi saboqning vazifasini bajaring — shunda bu saboq ochiladi", 403)
        ok, reason, page = services.task_requirement_met(user, lesson, request.data)
        if not ok:
            raise ApiError(reason, 400, need=page)
        LessonProgress.objects.get_or_create(
            user=user, lesson=lesson, defaults={"note": text_from(request.data, "note", 2000)},
        )
        activity.log(user, "lesson_complete", number=lesson.number)
        done = sum(1 for _, s, _ in states if s == "done") + 1
        return JsonResponse({"ok": True, "done": done, "total": len(states)})
    raise ApiError("Saboq topilmadi", 404)
