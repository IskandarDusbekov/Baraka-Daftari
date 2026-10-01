"""Bot menyusidagi qisqa hisobotlar: qancha qoldi, shu hafta, daromad, jamg'arma, qarz, kurs.

Har bir funksiya (matn, inline tugmalar) qaytaradi. Hisob-kitoblar Mini App bilan bir xil
`core.services` funksiyalaridan olinadi — bot va ilova hech qachon farqli raqam ko'rsatmaydi.
"""
import calendar
import datetime as dt
from html import escape

from django.db.models import Sum
from django.utils import timezone

from core import rates, services
from core.models import Expense, total_of

from .telegram import app_button

MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust",
          "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
CATEGORY_LABELS = dict(Expense.CATEGORIES)
NEED_LABELS = {"zarur": "🟢 Zarur", "kerak": "🟡 Kerak", "havas": "🔴 Havas"}


# ---------------------------------------------------------------- yordamchilar

def money(n, currency):
    n = int(n or 0)
    s = f"{abs(n):,}".replace(",", " ")
    sign = "−" if n < 0 else ""
    return f"{sign}${s}" if currency == "USD" else f"{sign}{s} so'm"


def other_currency(n, currency, rate):
    """Ikkinchi valyutadagi taxminiy qiymat: '≈ 11 171 015 so'm' yoki '≈ $945'."""
    if not rate or not n:
        return ""
    if currency == "USD":
        return f"≈ {money(round(n * rate['rate']), 'UZS')}"
    return f"≈ {money(round(n / rate['rate']), 'USD')}"


def bar(percent, width=10):
    filled = max(0, min(width, round(percent * width / 100)))
    return "▰" * filled + "▱" * (width - filled)


def refresh_row(key, path, label="📝 Batafsil"):
    return [{"text": "🔄 Yangilash", "callback_data": f"r:{key}"}, app_button(label, path)]


def _rows(*rows):
    result = [[b for b in row if b] for row in rows]
    return [r for r in result if r] or None


def _setup_income():
    text = (
        "💡 Hisob-kitob uchun avval <b>daromadingizni</b> kiriting — oylik summasini "
        "yoki birinchi kirimni.\n\nBu bir daqiqa oladi 👇"
    )
    return text, _rows([app_button("⚙️ Daromadni sozlash", "sozlamalar/")])


# ---------------------------------------------------------------- hisobotlar

def left_report(user):
    """💰 Bu oy qancha pul qoldi."""
    services.ensure_recurring(user)
    today = timezone.localdate()
    m = services.month_totals(user, today.year, today.month)
    if not m["base_income"]:
        return _setup_income()
    cur = user.currency
    rate = rates.usd_rate()
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day + 1
    free = m["free_after_planned"]

    lines = [
        f"💰 <b>{MONTHS[today.month - 1]} oyida qolgan pulingiz</b>\n",
        f"<b>{money(m['left'], cur)}</b>",
    ]
    alt = other_currency(m["left"], cur, rate)
    if alt:
        lines.append(f"<i>{alt}</i>")
    lines += [
        "",
        f"{bar(m['spent_percent'])} {m['spent_percent']}% sarflandi",
        "",
        f"📈 Daromad: <b>{money(m['base_income'], cur)}</b>" + (" <i>(oylik bo'yicha)</i>" if m["income_is_planned"] else ""),
        f"📉 Xarajat: <b>{money(m['expense'], cur)}</b>",
        f"🏦 Jamg'armaga: <b>{money(m['saved'], cur)}</b>",
    ]
    if m["withdrawn"]:
        lines.append(f"↩️ Jamg'armadan olingan: <b>{money(m['withdrawn'], cur)}</b>")
    if m["planned_pending"]:
        lines += [
            "",
            f"🔁 Hali to'lanadigan majburiy: <b>{money(m['planned_pending'], cur)}</b>",
            f"✅ Erkin pul: <b>{money(free, cur)}</b>",
        ]
    if free > 0:
        lines += ["", f"📆 Oy tugashiga {days_left} kun: kuniga taxminan <b>{money(free // days_left, cur)}</b> ishlatsangiz yetadi."]
    elif free < 0:
        lines += ["", "⚠️ Bu oy daromaddan ko'p sarflandi. Havas xarajatlarini kamaytirib ko'ring."]
    need_save = max(m["should_save"] - m["saved"], 0)
    if need_save:
        lines.append(f"\n💡 O'zingizga to'lash ({m['save_percent']}%): yana <b>{money(need_save, cur)}</b> qoldi.")
    return "\n".join(lines), _rows(refresh_row("left", "asosiy/"))


def week_report(user):
    """📅 Shu hafta (dushanbadan bugungacha) qancha sarflandi."""
    today = timezone.localdate()
    start = today - dt.timedelta(days=today.weekday())
    prev_start, prev_end = start - dt.timedelta(days=7), today - dt.timedelta(days=7)
    cur = user.currency

    week = user.expenses.filter(date__gte=start, date__lte=today)
    total = total_of(week)
    prev_total = total_of(user.expenses.filter(date__gte=prev_start, date__lte=prev_end))
    days = today.weekday() + 1

    lines = [f"📅 <b>Shu hafta</b> ({start:%d.%m} – {today:%d.%m})\n"]
    if not total:
        lines.append("Bu hafta hali xarajat yozilmagan.")
        if prev_total:
            lines.append(f"O'tgan haftaning shu kunlarida: {money(prev_total, cur)}")
        lines.append("\nXarajatlarni har kuni yozib borsangiz, hafta oxirida aniq manzarani ko'rasiz.")
        return "\n".join(lines), _rows([app_button("💸 Xarajat yozish", "hamyon/")])

    lines += [
        f"Sarflandi: <b>{money(total, cur)}</b>",
        f"Kuniga o'rtacha: <b>{money(total // days, cur)}</b>",
    ]
    if prev_total:
        diff = total - prev_total
        pct = round(abs(diff) * 100 / prev_total)
        if diff > 0:
            lines.append(f"🔺 O'tgan haftaning shu kunlaridan {pct}% ko'p (+{money(diff, cur)})")
        elif diff < 0:
            lines.append(f"🔻 O'tgan haftaning shu kunlaridan {pct}% kam (−{money(-diff, cur)}) — barakalla!")
        else:
            lines.append("➖ O'tgan hafta bilan bir xil")

    by_cat = week.values("category").annotate(s=Sum("amount")).order_by("-s")
    lines.append("\n<b>Nimalarga:</b>")
    for row in by_cat[:6]:
        pct = round(row["s"] * 100 / total)
        lines.append(f"{bar(pct, 6)} {escape(CATEGORY_LABELS.get(row['category'], row['category']))} — "
                     f"{money(row['s'], cur)} ({pct}%)")

    needs = {r["need"]: r["s"] for r in week.exclude(need="").values("need").annotate(s=Sum("amount"))}
    if needs:
        lines.append("\n" + " · ".join(f"{NEED_LABELS[k]} {round(needs[k] * 100 / total)}%"
                                       for k in ("zarur", "kerak", "havas") if k in needs))

    biggest = week.order_by("-amount").first()
    if biggest:
        what = biggest.note or CATEGORY_LABELS.get(biggest.category, "")
        lines.append(f"\n🔝 Eng katta xarajat: {escape(what)} — {money(biggest.amount, cur)} ({biggest.date:%d.%m})")
    return "\n".join(lines), _rows(refresh_row("week", "hamyon/"))


def income_report(user):
    """📈 Daromad va o'zingizga to'lash."""
    today = timezone.localdate()
    m = services.month_totals(user, today.year, today.month)
    cur = user.currency
    lines = ["📈 <b>Daromadingiz</b>\n"]
    if user.income_type == "salary" and user.monthly_income:
        lines.append(f"Oylik: <b>{money(user.monthly_income, cur)}</b>")
    elif user.income_type == "irregular":
        lines.append("Daromad turi: <b>o'zgaruvchan</b> (har kirimni alohida yozasiz)")
    else:
        return _setup_income()

    incomes = list(user.incomes.filter(date__gte=today.replace(day=1)).order_by("-date", "-id")[:5])
    lines.append(f"{MONTHS[today.month - 1]} oyidagi kirimlar: <b>{money(m['income'], cur)}</b>")
    for inc in incomes:
        note = inc.note or inc.get_source_display()
        lines.append(f"  • {inc.date:%d.%m}: {money(inc.amount, cur)} — {escape(note)}")
    if not incomes:
        lines.append("  <i>Bu oy hali kirim yozilmagan</i>")

    percent = round(m["saved"] * 100 / m["should_save"]) if m["should_save"] else 0
    lines += [
        "",
        f"💎 <b>O'zingizga to'lash — {m['save_percent']}%</b>",
        f"Reja: {money(m['should_save'], cur)}",
        f"To'landi: {money(m['saved'], cur)}",
        f"{bar(percent)} {min(percent, 100)}%",
    ]
    if m["saved"] >= m["should_save"] and m["should_save"]:
        lines.append("✅ Bu oy o'zingizga to'ladingiz. Zo'r!")
    return "\n".join(lines), _rows(refresh_row("income", "hamyon/"))


def savings_report(user):
    """🏦 Jamg'arma: qo'riqchi va o'sadigan pul."""
    s = services.savings_summary(user)
    cur = user.currency
    rate = rates.usd_rate()
    lines = ["🏦 <b>Jamg'armangiz</b>\n", f"Jami: <b>{money(s['total'], cur)}</b>"]
    alt = other_currency(s["total"], cur, rate)
    if alt:
        lines.append(f"<i>{alt}</i>")
    lines += [
        "",
        "🛡 <b>Qo'riqchi pul</b> — kutilmagan holatlar uchun",
        f"{money(s['guard'], cur)}" + (f" / {money(s['guard_target'], cur)}" if s["guard_target"] else ""),
    ]
    if s["guard_target"]:
        lines.append(f"{bar(s['guard_percent'])} {s['guard_percent']}%")
        lines.append(f"<i>{s['months_covered']} oylik xarajatni qoplaydi (maqsad: {s['guard_months']} oy)</i>")
    lines += ["", "🌱 <b>O'sadigan pul</b> — sarmoya uchun", money(s["grow"], cur)]
    if not s["total"]:
        lines.append("\n💡 Har kirimdan kichik foizni o'zingizga to'lashdan boshlang — jamg'arma shundan o'sadi.")
    elif s["suggested_bucket"] == "guard":
        lines.append("\n💡 Avval qo'riqchi pulni to'ldiring, keyin o'sadigan pulga o'tasiz.")
    return "\n".join(lines), _rows(refresh_row("savings", "jamgarma/"))


def debts_report(user):
    """💳 Qarzlar va qarzdan qutulish rejasi bo'yicha navbatdagi nishon."""
    cur = user.currency
    debts = [d for d in user.debts.all() if d.remaining > 0]
    if not debts:
        text = "💳 <b>Qarzlaringiz</b>\n\n🎉 Faol qarz yo'q. Shunday davom eting!"
        return text, _rows(refresh_row("debts", "qarzlar/"))
    s = services.debts_summary(user)
    lines = [
        "💳 <b>Qarzlaringiz</b>\n",
        f"Qolgan: <b>{money(s['remaining'], cur)}</b>",
        f"{bar(s['percent'])} {s['percent']}% to'landi",
        "",
    ]
    debts.sort(key=lambda d: d.remaining)
    for d in debts[:8]:
        monthly = f" · oyiga {money(d.monthly_payment, cur)}" if d.monthly_payment else ""
        lines.append(f"• <b>{escape(d.name)}</b> — {money(d.remaining, cur)}{monthly}")
    if len(debts) > 8:
        lines.append(f"<i>…yana {len(debts) - 8} ta</i>")
    lines.append(f"\n🎯 <b>Qarzdan qutulish:</b> hammasiga minimal to'lab, ortiqcha pulni avval "
                 f"«{escape(debts[0].name)}» ga yo'naltiring.")
    return "\n".join(lines), _rows(refresh_row("debts", "qarzlar/"))


def rate_report(user):
    """💱 Markaziy bank dollar kursi."""
    rate = rates.usd_rate()
    if not rate:
        return "💱 Markaziy bank kursini hozir olib bo'lmadi. Birozdan keyin urinib ko'ring.", None
    r = rate["rate"]
    diff = rate.get("diff") or 0
    arrow = "🔺" if diff > 0 else "🔻" if diff < 0 else "➖"
    rate_text = f"{r:,.2f}".replace(",", " ").replace(".", ",")
    diff_text = f"{diff:+.2f}".replace(".", ",")
    date = rate.get("date", "")
    lines = [
        "💱 <b>Dollar kursi</b> — O'zbekiston Markaziy banki\n",
        f"1 $ = <b>{rate_text} so'm</b>",
        f"{arrow} {diff_text} so'm · {date}" if diff else f"➖ o'zgarishsiz · {date}",
        "",
        f"$100 = {money(round(100 * r), 'UZS')}",
        f"$1 000 = {money(round(1000 * r), 'UZS')}",
        f"1 mln so'm = {money(round(1_000_000 / r), 'USD')}",
    ]
    if rate.get("stale"):
        lines.append("\n<i>⚠️ Oxirgi ma'lum kurs ko'rsatildi (cbu.uz hozir javob bermayapti).</i>")
    lines.append(f"\nHisobingiz: <b>{'dollarda' if user.currency == 'USD' else 'so‘mda'}</b>")
    return "\n".join(lines), _rows([{"text": "🔄 Yangilash", "callback_data": "r:rate"}])


REPORTS = {
    "left": left_report,
    "week": week_report,
    "income": income_report,
    "savings": savings_report,
    "debts": debts_report,
    "rate": rate_report,
}
