"""Botning o'zida xarajat va daromad yozish.

Oqim: «➖ Xarajat» → summani yozadi («45000 non») → toifani tanlaydi → yozildi.
«➕ Daromad» → summa → manba → yozildi + "10% ini o'zingizga to'lang" taklifi.
Menyusiz ham ishlaydi: shunchaki summa yozilsa, xarajatmi yoki daromadmi deb so'raladi.

Kutilayotgan qadam keshda saqlanadi (bazaga yozilmaydi) va 15 daqiqada o'z-o'zidan unutiladi.
"""
import re
from decimal import Decimal, InvalidOperation
from html import escape

from django.core.cache import cache
from django.utils import timezone

from core import activity, services
from core.models import Expense, Income, Saving

from .reports import money

MAX_AMOUNT = 10**13
STATE_TTL = 15 * 60

CATEGORY_BUTTONS = [
    ("food", "🍞 Oziq-ovqat"), ("rent", "🏠 Ijara / uy"),
    ("utility", "💡 Kommunal"), ("transport", "🚌 Yo'lkira"),
    ("clothes", "👕 Kiyim"), ("health", "💊 Sog'liq"),
    ("education", "🎓 Ta'lim"), ("phone", "📱 Aloqa"),
    ("events", "🎉 To'y-marosim"), ("charity", "🤲 Sadaqa"),
    ("other", "📦 Boshqa"),
]
SOURCE_BUTTONS = [
    ("salary", "💼 Oylik maosh"), ("extra", "➕ Qo'shimcha"),
    ("business", "🏪 Biznes / savdo"), ("other", "📦 Boshqa"),
]
CATEGORY_LABELS = dict(CATEGORY_BUTTONS)
SOURCE_LABELS = dict(SOURCE_BUTTONS)

MULTIPLIERS = {"k": 1000, "к": 1000, "ming": 1000, "минг": 1000, "тысяч": 1000,
               "mln": 10**6, "million": 10**6, "млн": 10**6}
AMOUNT_RE = re.compile(
    r"^\s*\$?\s*(\d[\d\s]*(?:[.,]\d+)*)\s*(mln|million|млн|ming|минг|тысяч|k|к)?\.?(?:\s+|$)(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def parse_amount(text):
    """'45000 non' -> (45000, 'non'); '45 000' / '45.000' -> 45000; '1.5 mln' -> 1500000.

    Tushunarsiz yoki noldan kichik bo'lsa (None, '').
    """
    m = AMOUNT_RE.match(text or "")
    if not m:
        return None, ""
    raw, suffix, note = m.group(1).replace(" ", ""), (m.group(2) or "").lower(), m.group(3).strip()
    # "45.000" / "1,250,000" — minglik ajratgich; "1.5" / "12,5" — kasr
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw) and not suffix:
        raw = re.sub(r"[.,]", "", raw)
    else:
        raw = raw.replace(",", ".")
        if raw.count(".") > 1:
            return None, ""
    try:
        value = Decimal(raw) * MULTIPLIERS.get(suffix, 1)
    except InvalidOperation:
        return None, ""
    value = int(value.to_integral_value())
    if value <= 0 or value >= MAX_AMOUNT:
        return None, ""
    return value, note[:200]


# ---------------------------------------------------------------- holat (kesh)

def _key(user):
    return f"bot:entry:{user.pk}"


def get_state(user):
    return cache.get(_key(user))


def set_state(user, **state):
    cache.set(_key(user), state, STATE_TTL)


def clear_state(user):
    cache.delete(_key(user))


def _grid(items, prefix, per_row=2):
    buttons = [{"text": label, "callback_data": f"{prefix}{code}"} for code, label in items]
    rows = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]
    rows.append([{"text": "✖️ Bekor qilish", "callback_data": "x"}])
    return rows


def _example(user):
    return "15" if user.currency == "USD" else "45000"


# ---------------------------------------------------------------- qadamlar

def start(user, kind):
    """«➖ Xarajat» / «➕ Daromad» bosildi — summani so'raymiz."""
    set_state(user, step="amount", kind=kind)
    ex = _example(user)
    if kind == "expense":
        return (f"➖ <b>Xarajat</b>\n\nQancha sarfladingiz? Summani yozing.\n"
                f"<i>Masalan: {ex} yoki {ex} non</i>"), [[{"text": "✖️ Bekor qilish", "callback_data": "x"}]]
    return (f"➕ <b>Daromad</b>\n\nQancha pul tushdi? Summani yozing.\n"
            f"<i>Masalan: {'1500' if user.currency == 'USD' else '8 mln'} yoki "
            f"{'1500' if user.currency == 'USD' else '8000000'} oylik</i>"), \
        [[{"text": "✖️ Bekor qilish", "callback_data": "x"}]]


def handle_text(user, text):
    """Oddiy matn keldi. Javob (matn, tugmalar) yoki None (bu matn bizga tegishli emas)."""
    state = get_state(user)
    amount, note = parse_amount(text)
    if state and state.get("step") == "amount":
        if amount is None:
            return (f"🤔 Summani tushunmadim. Faqat raqam yozing, masalan: <b>{_example(user)}</b>",
                    [[{"text": "✖️ Bekor qilish", "callback_data": "x"}]])
        return ask_details(user, state["kind"], amount, note)
    if amount is None:
        return None
    # Menyusiz yozilgan summa: nima ekanini so'raymiz
    set_state(user, step="kind", amount=amount, note=note)
    return (f"💬 <b>{money(amount, user.currency)}</b>{' — ' + escape(note) if note else ''}\n\nBu nima edi?",
            [[{"text": "➖ Xarajat", "callback_data": "k:expense"}, {"text": "➕ Daromad", "callback_data": "k:income"}],
             [{"text": "✖️ Bekor qilish", "callback_data": "x"}]])


def ask_details(user, kind, amount, note):
    set_state(user, step="details", kind=kind, amount=amount, note=note)
    head = f"<b>{money(amount, user.currency)}</b>{' — ' + escape(note) if note else ''}"
    if kind == "expense":
        return f"➖ {head}\n\nQaysi toifaga?", _grid(CATEGORY_BUTTONS, "c:")
    return f"➕ {head}\n\nQayerdan tushdi?", _grid(SOURCE_BUTTONS, "i:", per_row=2)


def choose_kind(user, kind):
    state = get_state(user)
    if not state or state.get("step") != "kind" or kind not in ("expense", "income"):
        return _expired()
    return ask_details(user, kind, state["amount"], state.get("note", ""))


def save_expense(user, category):
    state = get_state(user)
    if not state or state.get("step") != "details" or state.get("kind") != "expense" or category not in CATEGORY_LABELS:
        return _expired()
    clear_state(user)
    expense = Expense.objects.create(user=user, amount=state["amount"], category=category, note=state.get("note", ""))
    activity.log(user, "expense_add", amount=expense.amount, category=category, source="bot")
    today = timezone.localdate()
    m = services.month_totals(user, today.year, today.month)
    text = (f"✅ <b>Xarajat yozildi</b>\n\n{money(expense.amount, user.currency)} · {CATEGORY_LABELS[category]}"
            f"{' · ' + escape(expense.note) if expense.note else ''}")
    if m["base_income"]:
        text += f"\n\n💰 Bu oy qoldi: <b>{money(m['left'], user.currency)}</b>"
    return text, [[{"text": "↩️ Bekor qilish", "callback_data": f"u:e:{expense.pk}"},
                   {"text": "➖ Yana xarajat", "callback_data": "a:expense"}]]


def save_income(user, source):
    state = get_state(user)
    if not state or state.get("step") != "details" or state.get("kind") != "income" or source not in SOURCE_LABELS:
        return _expired()
    clear_state(user)
    income = Income.objects.create(user=user, amount=state["amount"], source=source, note=state.get("note", ""))
    activity.log(user, "income_add", amount=income.amount, source="bot")
    pay_self = services.save_amount(income.amount, user.save_percent)
    text = (f"✅ <b>Daromad yozildi</b>\n\n{money(income.amount, user.currency)} · {SOURCE_LABELS[source]}"
            f"{' · ' + escape(income.note) if income.note else ''}")
    buttons = []
    if pay_self:
        text += (f"\n\n💎 <b>Avval o'zingizga to'lang!</b>\n{user.save_percent}% i — "
                 f"<b>{money(pay_self, user.currency)}</b> ni jamg'armaga o'tkazasizmi?")
        buttons.append([{"text": f"✅ {money(pay_self, user.currency)} ni jamg'armaga", "callback_data": f"s:{income.pk}"}])
    buttons.append([{"text": "↩️ Bekor qilish", "callback_data": f"u:i:{income.pk}"}])
    return text, buttons


def save_from_income(user, income_pk):
    income = Income.objects.filter(pk=income_pk, user=user).first()
    if not income:
        return "Bu kirim topilmadi.", None
    if income.savings.exists():
        return "✅ Bu kirimdan allaqachon o'zingizga to'lagansiz.", None
    amount = services.save_amount(income.amount, user.save_percent)
    bucket = services.savings_summary(user)["suggested_bucket"]
    Saving.objects.create(user=user, amount=amount, income=income, kind="deposit", bucket=bucket)
    activity.log(user, "saving_add", amount=amount, bucket=bucket, source="bot")
    where = "🛡 qo'riqchi pulga" if bucket == "guard" else "🌱 o'sadigan pulga"
    total = services.savings_summary(user)["total"]
    return (f"💎 <b>Barakalla!</b> {money(amount, user.currency)} {where} o'tkazildi.\n"
            f"Jami jamg'arma: <b>{money(total, user.currency)}</b>"), None


def undo(user, kind, pk):
    model = Expense if kind == "e" else Income
    entry = model.objects.filter(pk=pk, user=user).first()
    if not entry:
        return "Bu yozuv allaqachon o'chirilgan.", None
    if kind == "i":
        entry.savings.all().delete()  # shu kirimdan qilingan jamg'arma ham qaytariladi
    entry.delete()
    activity.log(user, "entry_delete", kind="expense" if kind == "e" else "income", source="bot")
    return f"↩️ Bekor qilindi: {money(entry.amount, user.currency)} o'chirildi.", None


def cancel(user):
    clear_state(user)
    return "✖️ Bekor qilindi.", None


def _expired():
    return "⏳ Bu so'rov eskirgan. Pastdagi «➖ Xarajat» yoki «➕ Daromad» tugmasini qayta bosing.", None
