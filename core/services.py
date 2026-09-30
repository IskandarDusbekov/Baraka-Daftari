"""Biznes mantiq: saboqlar yo'lkasi, statistikalar, qor bo'lagi rejasi."""
import datetime as dt
import math

from django.core.cache import cache
from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Debt, DebtPayment, Expense, Income, Lesson, Saving, total_of

DEFAULT_SAVE_PERCENT = 10
SAVE_PERCENT_CHOICES = (5, 10, 15, 20)  # tavsiya etiladigan variantlar; 1–50 oralig'idagi istalgan foiz mumkin


def month_bounds(year, month):
    start = dt.date(year, month, 1)
    end = dt.date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def parse_month(value):
    """'2026-09' -> (2026, 9). Noto'g'ri bo'lsa joriy oy."""
    today = timezone.localdate()
    try:
        y, m = (int(x) for x in (value or "").split("-"))
        if 2000 <= y <= 2100 and 1 <= m <= 12:
            return y, m
    except ValueError:
        pass
    return today.year, today.month


def save_amount(amount, percent=DEFAULT_SAVE_PERCENT):
    """Daromaddan o'ziga to'lanadigan summa ("o'zingga to'la")."""
    return amount * percent // 100


# ---------------------------------------------------------------- saboqlar

LESSONS_CACHE_KEY = "lessons:published:v1"


def published_lessons():
    """Nashr qilingan saboqlar (kam o'zgaradi — keshda, Lesson saqlanganda tozalanadi)."""
    return cache.get_or_set(LESSONS_CACHE_KEY, lambda: list(Lesson.objects.filter(is_published=True)), 600)


def clear_lessons_cache():
    cache.delete(LESSONS_CACHE_KEY)


def lesson_states(user, lessons=None):
    """Har bir saboq uchun holat: done / open / wait (ertaga ochiladi) / locked.

    Qoida: saboqlar ketma-ket o'tiladi va kuniga faqat bitta yangi saboq ochiladi —
    keyingisi oldingisi bajarilgan kundan keyingi kunda ochiladi.
    """
    lessons = list(lessons if lessons is not None else published_lessons())
    done = {p.lesson_id: p for p in user.progress.all()}
    today = timezone.localdate()
    result = []
    prev_done_date = None
    current_found = False
    for index, lesson in enumerate(lessons):
        progress = done.get(lesson.id)
        if progress:
            state = "done"
            prev_done_date = timezone.localdate(progress.completed_at)
        elif not current_found:
            current_found = True
            if index == 0 or (prev_done_date and prev_done_date < today):
                state = "open"
            else:
                state = "wait"
        else:
            state = "locked"
        result.append((lesson, state, progress))
    return result


def current_lesson(user):
    """Joriy (birinchi bajarilmagan) saboq va uning holati."""
    for lesson, state, _ in lesson_states(user):
        if state in ("open", "wait"):
            return lesson, state
    return None, "finished"


def task_requirement_met(user, lesson, payload):
    """Vazifa bajarilganini tekshiradi. (ok, sabab, kerakli sahifa)."""
    t = lesson.task_type
    if t == "income" and not user.monthly_income and not user.incomes.exists():
        return False, "Avval daromadingizni kiriting (oylik yoki birinchi kirim).", "hamyon"
    if t == "expense" and not user.expenses.exists():
        return False, "Avval xarajatlaringizni kiriting.", "hamyon"
    if t == "save" and not user.savings.exists():
        return False, "Avval daromadingizdan o'zingizga to'lang (zaxiraga o'tkazing).", "hamyon"
    if t == "debt_list" and not user.debts.exists() and not payload.get("no_debt"):
        return False, "Qarzlaringizni ro'yxatga kiriting yoki \"Qarzim yo'q\" ni belgilang.", "qarzlar"
    if t == "debt_pay":
        has_active = user.debts.filter(closed_at__isnull=True).exists()
        if has_active and not DebtPayment.objects.filter(debt__user=user).exists():
            return False, "Avval qarzlaringizdan biriga to'lov kiriting.", "qarzlar"
    if t == "note" and len((payload.get("note") or "").strip()) < 3:
        return False, "Iltimos, javobingizni yozing.", None
    return True, "", None


# ---------------------------------------------------------------- statistika

def debts_summary(user):
    debts = list(user.debts.all())
    total = sum(d.total for d in debts)
    paid = sum(min(d.paid, d.total) for d in debts)
    remaining = sum(d.remaining for d in debts)
    return {
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "percent": round(paid * 100 / total) if total else 0,
        "count_active": sum(1 for d in debts if d.remaining > 0),
    }


def month_totals(user, year, month):
    """Oy yakunlari.

    Hisob uchun daromad (`base_income`): shu oyda yozilgan kirimlar, agar ular bo'lmasa —
    foydalanuvchi kiritgan oylik daromad. Shunda odam har oy kirim yozmasa ham 10% hisoblanadi.
    """
    start, end = month_bounds(year, month)
    income = total_of(user.incomes.filter(date__gte=start, date__lt=end))
    expense = total_of(user.expenses.filter(date__gte=start, date__lt=end))
    agg = user.savings.filter(date__gte=start, date__lt=end).aggregate(
        saved=Sum("amount", filter=Q(kind="deposit")),
        withdrawn=Sum("amount", filter=Q(kind="withdraw")),
    )
    saved = agg["saved"] or 0
    withdrawn = -(agg["withdrawn"] or 0)
    base_income = income or user.monthly_income
    today = timezone.localdate()
    is_current = (year, month) == (today.year, today.month)
    # Shu oy hali yozilmagan majburiy xarajatlar (ijara va h.k.) — "qolgan pul"dan oldindan ayiriladi
    planned_pending = total_of(
        user.recurring.filter(active=True).exclude(last_month=f"{year:04d}-{month:02d}")
    ) if is_current else 0
    left = base_income - expense - saved + withdrawn
    return {
        "income": income,
        "monthly_income": user.monthly_income,
        "income_type": user.income_type,
        "save_percent": user.save_percent,
        "base_income": base_income,
        "income_is_planned": not income and bool(user.monthly_income),
        "expense": expense,
        "saved": saved,
        "withdrawn": withdrawn,
        "should_save": save_amount(base_income, user.save_percent),
        # Qolgan pul: daromad − xarajatlar − jamg'armaga o'tkazilgan + jamg'armadan olingan
        "left": left,
        "planned_pending": planned_pending,
        "free_after_planned": left - planned_pending,
        "spent_percent": min(100, round(expense * 100 / base_income)) if base_income else 0,
        # 4-saboq: ro'zg'or (barcha uy xarajatlari) uchun 70% chegara
        "household_limit": base_income * 70 // 100,
    }


# ---------------------------------------------------------------- baho so'rash

RATING_MIN_VISITS = 3       # 3-marta qaytib kirganda…
RATING_MIN_DAYS = 3         # …yoki ro'yxatdan o'tganiga 3 kun bo'lganda
RATING_REPEAT_DAYS = 7      # "Keyinroq" desa, bir haftadan keyin qayta
RATING_MAX_ASKS = 3         # 3 martadan ortiq bezovta qilmaymiz


def should_ask_rating(user, now=None):
    now = now or timezone.now()
    if user.rating_asks >= RATING_MAX_ASKS:
        return False
    if user.rating_asked_at and now - user.rating_asked_at < dt.timedelta(days=RATING_REPEAT_DAYS):
        return False
    if user.visits < RATING_MIN_VISITS and now - user.created_at < dt.timedelta(days=RATING_MIN_DAYS):
        return False
    return not user.feedback.exists()


# ---------------------------------------------------------------- tanishtiruv ("Boshlash yo'li")

def onboarding_steps(user):
    """Yangi foydalanuvchi uchun yo'l: nimani qildi, keyin nima qilishi kerak."""
    has_debt_step = user.debts.exists() or user.progress.filter(lesson__task_type="debt_list").exists()
    steps = [
        ("currency", "Hisob valyutasini tanlang", "So'm yoki dollar — raqamlar aralashmaydi", "/sozlamalar/#valyuta",
         user.currency_chosen),
        ("income", "Daromadingizni sozlang", "Oylik bormi va necha foizini o'zingizga to'laysiz", "/sozlamalar/",
         bool(user.income_type)),
        ("expense", "Birinchi xarajatni yozing", "Xarajatni yozmaguncha uni boshqarib bo'lmaydi", "/hamyon/#xarajat",
         user.expenses.exists()),
        ("saving", "Avval o'zingizga to'lang", "Daromadning bir qismini jamg'armaga o'tkazing", "/jamgarma/",
         user.savings.filter(kind="deposit").exists()),
        ("debts", "Qarzlaringizni kiriting", "Qarz bo'lmasa — 3-saboqda «Qarzim yo'q» ni belgilang", "/qarzlar/",
         has_debt_step),
        ("lesson", "1-saboqni o'ting", "Videoni ko'ring va vazifalarni bajaring", "/saboqlar/",
         user.progress.exists()),
    ]
    items = [{"key": k, "title": t, "hint": h, "href": href, "done": bool(d)} for k, t, h, href, d in steps]
    done = sum(1 for i in items if i["done"])
    return {"steps": items, "done": done, "total": len(items), "hidden": user.onboarding_hidden,
            "next": next((i["key"] for i in items if not i["done"]), None)}


def user_has_money_data(user):
    return bool(user.monthly_income) or any(
        qs.exists() for qs in (user.incomes, user.expenses, user.savings, user.debts, user.recurring)
    )


def convert_user_money(user, to_currency, rate):
    """Foydalanuvchining barcha summalarini MB kursi bo'yicha boshqa valyutaga o'tkazadi (bitta tranzaksiyada)."""
    from django.db import transaction
    from django.db.models import BigIntegerField, F
    from django.db.models.functions import Cast, Round

    from .models import DebtPayment, RecurringExpense

    factor = (1 / rate) if to_currency == "USD" else rate

    def conv(field):
        return Cast(Round(F(field) * factor), BigIntegerField())

    with transaction.atomic():
        user.incomes.update(amount=conv("amount"))
        user.expenses.update(amount=conv("amount"))
        user.savings.update(amount=conv("amount"))
        RecurringExpense.objects.filter(user=user).update(amount=conv("amount"))
        DebtPayment.objects.filter(debt__user=user).update(amount=conv("amount"))
        user.debts.update(
            total=conv("total"), paid=conv("paid"), monthly_payment=conv("monthly_payment"),
            principal=conv("principal"), balance=conv("balance"),
        )
        user.monthly_income = round(user.monthly_income * factor)
        user.currency = to_currency
        user.currency_chosen = True
        user.save(update_fields=["monthly_income", "currency", "currency_chosen"])


# ---------------------------------------------------------------- jamg'arma

def monthly_need(user):
    """Bir oylik ro'zg'or xarajati (qo'riqchi pul maqsadini hisoblash uchun).

    Oxirgi 3 to'liq oy xarajatlarining o'rtachasi va majburiy xarajatlar yig'indisidan kattasi;
    ma'lumot bo'lmasa — daromadning 70% i.
    """
    today = timezone.localdate()
    first = today.replace(day=1)
    three_back = first
    for _ in range(3):
        three_back = (three_back - dt.timedelta(days=1)).replace(day=1)
    # Bitta so'rov: oxirgi 3 to'liq oy xarajatlari oylar bo'yicha
    months = [
        row["s"] for row in user.expenses.filter(date__gte=three_back, date__lt=first)
        .annotate(m=TruncMonth("date")).values("m").annotate(s=Sum("amount")) if row["s"]
    ]
    average = sum(months) // len(months) if months else 0
    recurring = total_of(user.recurring.filter(active=True))
    need = max(average, recurring)
    if not need:
        need = total_of(user.expenses.filter(date__gte=first)) or user.monthly_income * 70 // 100
    return need


def savings_summary(user):
    agg = user.savings.aggregate(
        guard=Sum("amount", filter=Q(bucket="guard")), grow=Sum("amount", filter=Q(bucket="grow")),
    )
    guard, grow = agg["guard"] or 0, agg["grow"] or 0
    need = monthly_need(user)
    target = need * user.guard_months
    return {
        "total": guard + grow,
        "guard": guard,
        "grow": grow,
        "guard_months": user.guard_months,
        "monthly_need": need,
        "guard_target": target,
        "guard_percent": min(100, round(guard * 100 / target)) if target else 0,
        "months_covered": round(guard / need, 1) if need else 0,
        # Qo'riqchi pul maqsadga yetguncha yangi pul unga, keyin o'sadigan pulga
        "suggested_bucket": "guard" if not target or guard < target else "grow",
    }


def ensure_recurring(user, today=None):
    """Kuni kelgan oylik majburiy xarajatlarni shu oy uchun bir marta yozadi."""
    today = today or timezone.localdate()
    key = f"{today.year:04d}-{today.month:02d}"
    created = 0
    for item in user.recurring.filter(active=True, day__lte=today.day).exclude(last_month=key):
        Expense.objects.create(
            user=user, amount=item.amount, category=item.category, need=item.need,
            note=item.name, date=today.replace(day=min(item.day, 28)),
        )
        item.last_month = key
        item.save(update_fields=["last_month"])
        created += 1
    return created


def badges(user, lessons_done, lessons_total):
    has_payment = DebtPayment.objects.filter(debt__user=user).exists()
    items = [
        ("sprout", "Birinchi saboq", lessons_done >= 1),
        ("safe", "Zaxira egasi", user.savings.exists()),
        ("receipt", "Hisobchi", user.expenses.count() >= 10),
        ("target", "Qarz jangchisi", has_payment),
        ("check-circle", "Bir qarzdan ozod", user.debts.filter(closed_at__isnull=False).exists()),
        ("flame", "Bir oylik intizom", lessons_done >= 4),
        ("trophy", "Hamma saboqlar", lessons_total > 0 and lessons_done >= lessons_total),
    ]
    # icon — SVG sprite'dagi ikonka nomi (templates/partials/icons.html)
    return [{"icon": i, "title": t, "earned": e} for i, t, e in items]


# ---------------------------------------------------------------- bank krediti

MAX_CREDIT_MONTHS = 1200


def monthly_rate(annual_rate):
    return float(annual_rate) / 100 / 12


def annuity_payment(principal, annual_rate, months):
    """Bankning har oylik teng (annuitet) to'lovi."""
    if months <= 0 or principal <= 0:
        return 0
    r = monthly_rate(annual_rate)
    if r == 0:
        return -(-principal // months)  # yuqoriga yaxlitlash
    # Yuqoriga yaxlitlanadi (banklardagidek) — oxirgi to'lov biroz kichik bo'ladi, muddat oshmaydi
    return math.ceil(principal * r / (1 - (1 + r) ** -months))


def simulate_credit(balance, annual_rate, payment):
    """Qoldiqni `payment` dan to'lab borilsa: (oylar soni, jami to'lanadigan summa).

    To'lov oylik foizni ham yopa olmasa — (None, None).
    """
    r = monthly_rate(annual_rate)
    months, total = 0, 0.0
    balance = float(balance)
    while balance > 0.5 and months < MAX_CREDIT_MONTHS:
        interest = balance * r
        if payment <= interest:
            return None, None
        pay = min(payment, balance + interest)
        balance = balance + interest - pay
        total += pay
        months += 1
    return months, round(total)


def apply_credit_payment(balance, annual_rate, standard_payment, amount):
    """Bitta to'lovdan keyingi asosiy qarz qoldig'i.

    Oylik foiz to'lov ulushiga mutanosib hisoblanadi (bir oylik to'lovdan ko'p bo'lsa ham
    bir oylik foizdan oshmaydi) — shuning uchun qo'shimcha to'lov to'liq asosiy qarzga ketadi.
    """
    r = monthly_rate(annual_rate)
    share = min(1.0, amount / standard_payment) if standard_payment else 1.0
    interest = balance * r * share
    return max(0, round(balance + interest - amount))


def balance_after_paid(principal, annual_rate, payment, paid):
    """Standart to'lovlar bilan `paid` summa to'langandan keyingi asosiy qarz qoldig'i."""
    balance, left = principal, paid
    while left > 0 and balance > 0:
        pay = min(payment, left)
        balance = apply_credit_payment(balance, annual_rate, payment, pay)
        left -= pay
    return balance


def payoff_amount(balance, annual_rate):
    """Kreditni hozir to'liq yopish uchun kerakli summa (qoldiq + bir oylik foiz)."""
    return round(balance * (1 + monthly_rate(annual_rate)))


def credit_calc(principal, annual_rate, term_months, paid=0, extra_percent=0, balance=None):
    """Kredit bo'yicha to'liq hisob: bank foizi bilan jami, qolgani, qo'shib to'lasa qancha yutadi."""
    payment = annuity_payment(principal, annual_rate, term_months)
    if balance is None:
        balance = balance_after_paid(principal, annual_rate, payment, paid)
    months_left, remaining = simulate_credit(balance, annual_rate, payment)
    extra_amount = payment * extra_percent // 100
    months_extra, remaining_extra = simulate_credit(balance, annual_rate, payment + extra_amount)
    today = timezone.localdate()
    schedule_total = payment * term_months
    return {
        "principal": principal,
        "interest_rate": float(annual_rate),
        "term_months": term_months,
        "monthly_payment": payment,
        "total_with_interest": schedule_total,
        "overpay": schedule_total - principal,
        "paid": paid,
        "months_paid": min(term_months, paid // payment) if payment else 0,
        "balance": balance,
        "remaining": remaining or 0,
        "months_left": months_left or 0,
        "finish_date": _add_months(today, months_left).isoformat() if months_left else None,
        "extra_percent": extra_percent,
        "extra_amount": extra_amount,
        "extra_payment": payment + extra_amount,
        "months_with_extra": months_extra or 0,
        "remaining_with_extra": remaining_extra or 0,
        "finish_date_extra": _add_months(today, months_extra).isoformat() if months_extra else None,
        "months_saved": (months_left or 0) - (months_extra or 0),
        "saved": (remaining or 0) - (remaining_extra or 0),
    }


def debt_credit_calc(debt):
    return credit_calc(debt.principal, debt.interest_rate, debt.term_months, debt.paid,
                       debt.extra_percent, balance=debt.balance)


# ---------------------------------------------------------------- qor bo'lagi

def simulate_snowball(balances, minimums, extra, max_months=600):
    """Qarzlar kichigidan kattasiga tartiblangan bo'lishi kerak.

    Har oy: barcha qarzlarga minimal to'lov, ortgan pul (qo'shimcha summa va
    yopilgan qarzlardan bo'shagan to'lovlar) eng kichik qarzga yo'naltiriladi.
    Qaytaradi: (oylar soni yoki None, har bir qarz yopiladigan oy ro'yxati).
    """
    balances = list(balances)
    payoff = [0 if b <= 0 else None for b in balances]
    budget = sum(minimums) + max(extra, 0)
    if not any(b > 0 for b in balances):
        return 0, payoff
    if budget <= 0:
        return None, payoff
    month = 0
    while any(b > 0 for b in balances) and month < max_months:
        month += 1
        available = budget
        for i, bal in enumerate(balances):
            if bal > 0:
                pay = min(minimums[i], bal, available)
                balances[i] -= pay
                available -= pay
        for i, bal in enumerate(balances):
            if bal > 0 and available > 0:
                pay = min(bal, available)
                balances[i] -= pay
                available -= pay
        for i, bal in enumerate(balances):
            if bal <= 0 and payoff[i] is None:
                payoff[i] = month
    if any(b > 0 for b in balances):
        return None, payoff
    return month, payoff


def snowball_plan(user, extra=None):
    today = timezone.localdate()
    active = sorted(
        (d for d in user.debts.all() if d.remaining > 0),
        key=lambda d: (d.remaining, d.id),
    )
    totals = month_totals(user, today.year, today.month)
    # Daromad: shu oy kirimlari -> kiritilgan oylik daromad -> o'tgan oy kirimlari
    income = totals["base_income"]
    if not income:
        prev = today.replace(day=1) - dt.timedelta(days=1)
        income = month_totals(user, prev.year, prev.month)["income"]
    save = save_amount(income, user.save_percent)
    expense = totals["expense"]
    minimums_total = sum(min(d.monthly_payment, d.remaining) for d in active)
    free = income - save - expense - minimums_total
    suggested_extra = max(free, 0)
    if extra is None:
        extra = suggested_extra

    months, payoff = simulate_snowball(
        [d.remaining for d in active],
        [min(d.monthly_payment, d.remaining) for d in active],
        extra,
    )
    months_min_only, _ = simulate_snowball(
        [d.remaining for d in active],
        [min(d.monthly_payment, d.remaining) for d in active],
        0,
    )

    order = []
    for i, d in enumerate(active):
        order.append({
            "id": d.id,
            "name": d.name,
            "remaining": d.remaining,
            "monthly_payment": d.monthly_payment,
            "payoff_month": payoff[i],
            "payoff_date": _add_months(today, payoff[i]).isoformat() if payoff[i] else None,
            "target": i == 0,
        })

    return {
        "income": income,
        "save": save,
        "save_percent": user.save_percent,
        # 4-saboq, Sobir hojining qoidasi: 70% ro'zg'orga, 20% qarzga qo'shimcha, 10% o'zingizga
        "rule_70_20_10": {"home": income * 70 // 100, "debt": income * 20 // 100, "self": income * 10 // 100},
        "expense": expense,
        "minimums_total": minimums_total,
        "free": free,
        "suggested_extra": suggested_extra,
        "extra": extra,
        "months": months,
        "months_min_only": months_min_only,
        "free_date": _add_months(today, months).isoformat() if months else None,
        "order": order,
    }


def _add_months(date, months):
    if not months:
        return date
    m = date.month - 1 + months
    return dt.date(date.year + m // 12, m % 12 + 1, 1)
