"""Boshqaruv paneli uchun tahlillar: foydalanuvchi profili va umumiy dashboard.

Grafiklar serverda tayyorlanadi (CSS bilan chiziladi) — panelga JS kutubxona kerak emas.
So'm va dollar hech qachon qo'shilmaydi: umumiy tahlillar summalar emas, yozuvlar soni bo'yicha.
"""
import datetime as dt

from django.db.models import Count, Exists, F, OuterRef, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone

from core import services
from core.models import (
    ActivityLog, Debt, Expense, LessonProgress, RecurringExpense, Saving, TgUser, total_of,
)

# Ilovadagi bilan bir xil (static/js/common.js → CATS, NEEDS, BUCKETS)
CATS = {
    "food": ("cart", "#22c55e"), "rent": ("home2", "#0ea5e9"), "utility": ("bulb", "#f59e0b"),
    "transport": ("bus", "#3b82f6"), "clothes": ("shirt", "#ec4899"), "health": ("heart", "#ef4444"),
    "education": ("cap", "#6366f1"), "phone": ("phone", "#14b8a6"), "events": ("gift", "#d946ef"),
    "charity": ("hand", "#84cc16"), "shopping": ("bag", "#f97316"), "other": ("box", "#94a3b8"),
}
NEEDS = {"zarur": ("Zarur", "#16a34a"), "kerak": ("Kerak", "#2563eb"), "havas": ("Havas", "#ea580c"),
         "unmarked": ("Belgilanmagan", "#cbd5e1")}
BUCKETS = {"guard": ("Qo'riqchi pulga", "shield", "#0ea5e9"), "grow": ("O'sadigan pulga", "sprout", "#16a34a")}
SOURCES = {"salary": "Oylik maosh", "extra": "Qo'shimcha", "business": "Biznes / savdo", "other": "Boshqa"}


def pct(part, whole):
    return round(part * 100 / whole) if whole else 0


def donut(items):
    """[{amount, color}] → CSS conic-gradient (aylana diagramma)."""
    total = sum(i["amount"] for i in items)
    if not total:
        return ""
    stops, acc = [], 0
    for i in items:
        start = acc * 360 / total
        acc += i["amount"]
        stops.append(f"{i['color']} {start:.1f}deg {acc * 360 / total:.1f}deg")
    return "conic-gradient(" + ", ".join(stops) + ")"


def bars(values, key="value"):
    """Ustunli grafik uchun balandlik (%) qo'shadi."""
    peak = max([1] + [v[key] for v in values])
    for v in values:
        v["h"] = round(v[key] * 100 / peak)
    return values


def initials(user):
    parts = [p for p in (user.first_name, user.last_name) if p]
    if parts:
        return "".join(p[0] for p in parts[:2]).upper()
    return (user.username or "?")[:1].upper()


# ---------------------------------------------------------------- foydalanuvchi profili

def user_profile(u):
    today = timezone.localdate()
    start = today - dt.timedelta(days=29)
    report = services.period_report(u, start, today)

    cats = [{**c, "icon": CATS.get(c["key"], CATS["other"])[0], "color": CATS.get(c["key"], CATS["other"])[1],
             "pct": pct(c["amount"], report["expense"])} for c in report["by_category"]]
    marked = sum(report["by_need"].values())
    needs = [{"key": k, "label": label, "color": color, "amount": report["by_need"].get(k, 0),
              "pct": pct(report["by_need"].get(k, 0), marked)}
             for k, (label, color) in NEEDS.items() if report["by_need"].get(k)]

    daily = bars([{"date": dt.date.fromisoformat(d["date"]), "value": d["amount"]} for d in report["daily"]])

    start_dt = timezone.make_aware(dt.datetime.combine(start, dt.time.min))
    acts = dict(u.activity.filter(created_at__gte=start_dt).annotate(d=TruncDate("created_at"))
                .values("d").annotate(c=Count("id")).values_list("d", "c"))
    activity = bars([{"date": start + dt.timedelta(days=i), "value": acts.get(start + dt.timedelta(days=i), 0)}
                     for i in range(30)])

    month = services.month_totals(u, today.year, today.month)
    savings = services.savings_summary(u)
    debts = list(u.debts.select_related("lender"))
    lessons = services.lesson_states(u)
    lessons_done = sum(1 for _, state, _ in lessons if state == "done")

    return {
        "initials": initials(u),
        "report": report, "cats": cats, "cats_donut": donut(cats), "needs": needs, "needs_marked": marked,
        "daily": daily, "activity": activity, "active_days": sum(1 for a in activity if a["value"]),
        "month": month, "spent_pct": min(pct(month["expense"], month["base_income"]), 100),
        "save_pct": min(pct(month["saved"], month["should_save"]), 100),
        "savings": savings, "debts": debts, "debt_summary": services.debts_summary(u),
        "lent": list(u.lent_debts.select_related("user")),
        "lessons": lessons, "lessons_done": lessons_done, "lessons_pct": pct(lessons_done, len(lessons)),
        "entries": recent_entries(u),
        "totals": {
            "income": total_of(u.incomes.all()), "expense": total_of(u.expenses.all()),
            "incomes_count": u.incomes.count(), "expenses_count": u.expenses.count(),
        },
    }


def recent_entries(u, limit=10):
    """Ilovadagi «Tarix» kabi: kirim, xarajat, jamg'arma — bitta ro'yxatda."""
    labels = dict(Expense.CATEGORIES)
    rows = []
    for e in u.expenses.order_by("-date", "-id")[:limit]:
        icon, color = CATS.get(e.category, CATS["other"])
        rows.append({"date": e.date, "id": e.id, "kind": "minus", "sign": "−", "amount": e.amount, "icon": icon,
                     "color": color, "title": labels.get(e.category, e.category), "note": e.note,
                     "need": NEEDS.get(e.need) if e.need else None})
    for i in u.incomes.order_by("-date", "-id")[:limit]:
        rows.append({"date": i.date, "id": i.id, "kind": "plus", "sign": "+", "amount": i.amount, "icon": "up",
                     "color": "#2563eb", "title": SOURCES.get(i.source, "Kirim"), "note": i.note, "need": None})
    for s in u.savings.order_by("-date", "-id")[:limit]:
        label, icon, color = BUCKETS.get(s.bucket, BUCKETS["guard"])
        out = s.amount < 0
        rows.append({"date": s.date, "id": s.id, "kind": "plus" if out else "save", "sign": "←" if out else "→",
                     "amount": abs(s.amount), "icon": icon, "color": color,
                     "title": f"Jamg'armadan olindi" if out else label, "note": "", "need": None})
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------- umumiy dashboard

def dashboard_insights():
    now = timezone.now()
    today = timezone.localdate()
    users = TgUser.objects.all()
    total = users.count()
    day = dt.timedelta(days=1)

    # O'sish: shu hafta vs o'tgan hafta
    new_7 = users.filter(created_at__gte=now - 7 * day).count()
    new_prev_7 = users.filter(created_at__gte=now - 14 * day, created_at__lt=now - 7 * day).count()

    # Qaytib kelish (retention): ro'yxatdan o'tgandan N kun keyin ham kirganlar
    retention = []
    for n, label in ((1, "Ertasi kuni"), (7, "1 haftadan keyin"), (30, "1 oydan keyin")):
        base = users.filter(created_at__lte=now - n * day, created_at__gte=now - (n + 90) * day)
        cohort = base.count()
        back = base.filter(last_seen__gte=F("created_at") + n * day).count()
        retention.append({"label": label, "days": n, "cohort": cohort, "back": back, "pct": pct(back, cohort)})

    dau = users.filter(last_seen__gte=now - day).count()
    mau = users.filter(last_seen__gte=now - 30 * day).count()

    # Funksiyalardan foydalanish
    u = OuterRef("pk")
    adoption = [
        ("Daromadini sozlagan", users.filter(~Q(income_type="")).count()),
        ("Xarajat yozgan", users.filter(Exists(Expense.objects.filter(user=u))).count()),
        ("Jamg'armaga pul qo'ygan", users.filter(Exists(Saving.objects.filter(user=u, kind="deposit"))).count()),
        ("Saboq yakunlagan", users.filter(Exists(LessonProgress.objects.filter(user=u))).count()),
        ("Qarz kiritgan", users.filter(Exists(Debt.objects.filter(user=u))).count()),
        ("Qarzini bog'lagan", users.filter(Q(Exists(Debt.objects.filter(user=u, lender__isnull=False)))
                                           | Q(Exists(Debt.objects.filter(lender=u)))).count()),
        ("Majburiy xarajat qo'shgan", users.filter(Exists(RecurringExpense.objects.filter(user=u))).count()),
        ("Botdan foydalanadi", users.filter(bot_started=True, bot_blocked=False).count()),
    ]
    adoption = [{"label": l, "count": c, "pct": pct(c, total)} for l, c in adoption]

    # Toifalar va Zarur/Kerak/Havas — yozuvlar soni bo'yicha (valyutadan qat'i nazar)
    month_ago = today - dt.timedelta(days=29)
    recent = Expense.objects.filter(date__gte=month_ago)
    exp_count = recent.count()
    labels = dict(Expense.CATEGORIES)
    cats = [{"key": r["category"], "label": labels.get(r["category"], r["category"]), "amount": r["c"],
             "icon": CATS.get(r["category"], CATS["other"])[0], "color": CATS.get(r["category"], CATS["other"])[1],
             "pct": pct(r["c"], exp_count)}
            for r in recent.values("category").annotate(c=Count("id")).order_by("-c")]
    need_counts = {r["need"] or "unmarked": r["c"] for r in recent.values("need").annotate(c=Count("id"))}
    needs = [{"label": label, "color": color, "pct": pct(need_counts.get(k, 0), exp_count)}
             for k, (label, color) in NEEDS.items() if need_counts.get(k)]

    # Soat bo'yicha faollik (Toshkent vaqti) — xabar yuborish vaqtini tanlash uchun
    hours = dict(ActivityLog.objects.filter(created_at__gte=now - 30 * day)
                 .annotate(h=ExtractHour("created_at")).values("h").annotate(c=Count("id")).values_list("h", "c"))
    hourly = bars([{"hour": h, "value": hours.get(h, 0)} for h in range(24)])
    peak_hour = max(hourly, key=lambda x: x["value"]) if any(h["value"] for h in hourly) else None

    return {
        "growth": {"new_7": new_7, "new_prev_7": new_prev_7,
                   "change": pct(new_7 - new_prev_7, new_prev_7) if new_prev_7 else None},
        "retention": retention, "dau": dau, "mau": mau, "stickiness": pct(dau, mau),
        "adoption": adoption, "exp_count": exp_count,
        "cats": cats[:8], "cats_donut": donut(cats), "needs": needs,
        "hourly": hourly, "peak_hour": peak_hour,
    }
