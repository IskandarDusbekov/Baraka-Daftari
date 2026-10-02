"""Qarzni ikki foydalanuvchi o'rtasida bog'lash.

Qoidalar:
- Bog'lash faqat rozilik bilan: taklif havolasini ikkinchi tomon botda ochib, «Tasdiqlayman» ni bosadi.
  Hech kim boshqa foydalanuvchini qidirib topa olmaydi.
- Qarz egasi — doim qarz olgan odam (Debt.user); qarz bergan esa Debt.lender sifatida bog'lanadi.
- Bog'langan qarzda summani o'zgartirib yoki o'chirib bo'lmaydi — avval bog'lanish uziladi (ikkinchi tomon xabar oladi).
- Qarzdor to'lov yozsa, qarz bergan tasdiqlaydi yoki rad etadi (rad etilsa summa qarzga qaytadi).
"""
import datetime as dt
import logging
import secrets
from html import escape

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import activity
from .models import Debt, DebtLink, DebtPayment

log = logging.getLogger("bot")

LINKABLE_KINDS = ("personal", "nasiya", "other")  # bank krediti — bank bilan, bog'lanmaydi


class LinkError(Exception):
    pass


def som(n):
    return f"{n:,}".replace(",", " ") + " so'm"


def invite_url(link):
    return f"https://t.me/{settings.BOT_USERNAME}?start=q_{link.token}" if settings.BOT_USERNAME else ""


def first_name(user):
    return user.first_name or user.display_name()


# ---------------------------------------------------------------- bot orqali xabar (sayt jarayonidan ham)

def notify(user, text, buttons=None):
    """Ikkinchi tomonga bot xabari. Yetib bormasa — jim o'tamiz (asosiy amal bunga bog'liq emas)."""
    if not user or not user.bot_started or user.bot_blocked or not user.is_active or not settings.BOT_TOKEN:
        return False
    from bot.telegram import BotAPI, TelegramError
    try:
        BotAPI().call("sendMessage", http_timeout=6, chat_id=user.tg_id, text=text, parse_mode="HTML",
                      disable_web_page_preview=True, **({"reply_markup": {"inline_keyboard": buttons}} if buttons else {}))
        return True
    except (TelegramError, OSError, ValueError) as e:
        log.warning("debt notify %s: %s", user.pk, e)
        return False


def _app_buttons(text="📒 Qarzlarni ochish"):
    from bot.telegram import app_button
    btn = app_button(text, "qarzlar/")
    return [[btn]] if btn else None


# ---------------------------------------------------------------- taklif yaratish

def invite_for_debt(user, debt):
    """Qarzdor o'z qarzini qarz bergan odamga bog'lash uchun havola so'raydi."""
    if debt.user_id != user.pk:
        raise LinkError("Qarz topilmadi")
    if debt.kind not in LINKABLE_KINDS:
        raise LinkError("Bank kreditini bog'lab bo'lmaydi — faqat tanish yoki nasiya qarzini")
    if debt.lender_id:
        raise LinkError("Bu qarz allaqachon bog'langan")
    if debt.remaining == 0:
        raise LinkError("Bu qarz yopilgan")
    link = debt.links.filter(status="open").first()
    if link and not link.expired:
        return link
    _check_rate(user)
    link = DebtLink.objects.create(token=secrets.token_urlsafe(16), creator=user, direction="borrowed", debt=debt,
                                   amount=debt.remaining, note=debt.name)
    activity.log(user, "debt_invite", direction="borrowed")
    return link


def invite_lent(user, amount, note):
    """«Qarz berdim»: qabul qilgan odamning ro'yxatida yangi qarz paydo bo'ladi."""
    _check_rate(user)
    link = DebtLink.objects.create(token=secrets.token_urlsafe(16), creator=user, direction="lent",
                                   amount=amount, note=note)
    activity.log(user, "debt_invite", direction="lent", amount=amount)
    return link


def _check_rate(user):
    if not activity.allow(f"debt-invite:{user.pk}", 20, 3600):
        raise LinkError("Juda ko'p havola yaratildi. Birozdan keyin urinib ko'ring")


def share_text(link):
    who = first_name(link.creator)
    if link.direction == "borrowed":
        return f"{who}: sizdan olgan {som(link.amount)} qarzimni «Baraka Daftari»da yozib boryapman. Tasdiqlasangiz, to'lovlarni siz ham ko'rib turasiz."
    return f"{who}: sizga bergan {som(link.amount)} qarzni «Baraka Daftari»da yozib qo'ydim. Tasdiqlasangiz, qarz va to'lovlar ikkalamizda ham ko'rinadi."


def cancel_invite(user, pk):
    updated = DebtLink.objects.filter(pk=pk, creator=user, status="open").update(status="cancelled")
    if not updated:
        raise LinkError("Taklif topilmadi")


# ---------------------------------------------------------------- taklifni qabul qilish (botda)

def open_link(token):
    link = DebtLink.objects.select_related("creator", "debt").filter(token=token).first()
    if not link or link.status != "open" or link.expired:
        raise LinkError("Bu havola eskirgan yoki allaqachon ishlatilgan. Yuborgan odamdan yangisini so'rang.")
    if link.direction == "borrowed" and (not link.debt or link.debt.lender_id):
        raise LinkError("Bu qarz allaqachon bog'langan.")
    return link


def invite_message(link):
    """Havolani ochgan odamga ko'rsatiladigan savol (matn, tugmalar)."""
    who = escape(first_name(link.creator))
    if link.direction == "borrowed":
        text = (f"🤝 <b>{who}</b> sizdan <b>{som(link.amount)}</b> qarz olganini yozdi"
                f"{f' («{escape(link.note)}»)' if link.note else ''}.\n\n"
                "Tasdiqlasangiz, bu qarz va uning to'lovlari sizning «Menga qarzdorlar» ro'yxatingizda ko'rinadi. "
                "U to'lov kiritganda sizdan tasdiq so'raladi.")
    else:
        text = (f"🤝 <b>{who}</b> sizga <b>{som(link.amount)}</b> qarz berganini yozdi"
                f"{f' («{escape(link.note)}»)' if link.note else ''}.\n\n"
                "Tasdiqlasangiz, qarz sizning «Qarzlar» ro'yxatingizga qo'shiladi — qancha qolganini va "
                "to'lovlarni ikkalangiz ham ko'rib turasiz.")
    text += "\n\n<i>Bu yozuv shaxsiy hisob uchun, huquqiy hujjat emas.</i>"
    return text, [[{"text": "✅ Ha, to'g'ri", "callback_data": f"dl:{link.token}:y"},
                   {"text": "✖️ Yo'q", "callback_data": f"dl:{link.token}:n"}]]


def accept(user, token):
    """Qabul qiladi. Qaytaradi: javob matni (bot xabari)."""
    with transaction.atomic():
        link = DebtLink.objects.select_for_update().select_related("creator").filter(token=token).first()
        if not link or link.status != "open" or link.expired:
            raise LinkError("Bu havola eskirgan yoki allaqachon ishlatilgan.")
        if link.creator_id == user.pk:
            raise LinkError("Bu havolani o'zingiz yaratgansiz — uni qarz bergan/olgan odamga yuboring.")
        if link.direction == "borrowed":
            debt = Debt.objects.select_for_update().filter(pk=link.debt_id).first()
            if not debt or debt.lender_id:
                raise LinkError("Bu qarz allaqachon bog'langan.")
            debt.lender = user
            debt.save(update_fields=["lender"])
        else:
            debt = Debt.objects.create(user=user, lender=link.creator, kind="personal", total=link.amount,
                                       name=f"{first_name(link.creator)}dan qarz"[:100])
        link.status, link.used_by = "accepted", user
        link.save(update_fields=["status", "used_by"])
    activity.log(user, "debt_link", direction=link.direction, amount=link.amount)
    who = escape(first_name(user))
    if link.direction == "borrowed":
        notify(link.creator, f"✅ <b>{who}</b> qarzingizni tasdiqladi ({som(link.amount)}). "
                             "Endi to'lov kiritganingizda u ham ko'radi.", _app_buttons())
        return f"✅ Tasdiqlandi. Qarz «Menga qarzdorlar» ro'yxatingizda ({som(link.amount)})."
    notify(link.creator, f"✅ <b>{who}</b> {som(link.amount)} qarzni tasdiqladi. "
                         "U to'lov qilganda sizdan tasdiq so'raladi.", _app_buttons())
    return f"✅ Tasdiqlandi. Qarz «Qarzlar» ro'yxatingizga qo'shildi ({som(link.amount)})."


def decline(user, token):
    link = DebtLink.objects.select_related("creator").filter(token=token, status="open").first()
    if not link:
        raise LinkError("Bu havola eskirgan yoki allaqachon ishlatilgan.")
    if link.creator_id == user.pk:
        raise LinkError("Bu havolani o'zingiz yaratgansiz.")
    link.status, link.used_by = "declined", user
    link.save(update_fields=["status", "used_by"])
    notify(link.creator, f"✖️ <b>{escape(first_name(user))}</b> {som(link.amount)} qarz yozuvini tasdiqlamadi. "
                         "Summa noto'g'ri bo'lsa, u bilan gaplashib, yangi havola yuboring.")
    return "Rad etildi. Yuborgan odamga xabar berdik."


# ---------------------------------------------------------------- to'lovlar

def payment_created(payment):
    """Bog'langan qarzga to'lov yozildi — qarz bergandan tasdiq so'raymiz."""
    debt = payment.debt
    text = (f"💸 <b>{escape(first_name(debt.user))}</b> sizga <b>{som(payment.amount)}</b> qaytarganini yozdi.\n"
            f"Qoldi: {som(debt.remaining)}.\n\nShu pulni oldingizmi?")
    notify(debt.lender, text, [[{"text": "✅ Ha, oldim", "callback_data": f"dp:{payment.pk}:y"},
                                {"text": "✖️ Olmadim", "callback_data": f"dp:{payment.pk}:n"}]])


def review_payment(user, pk, ok):
    """Qarz bergan to'lovni tasdiqlaydi yoki rad etadi. Qaytaradi: javob matni."""
    with transaction.atomic():
        payment = DebtPayment.objects.select_for_update().select_related("debt").filter(pk=pk).first()
        if not payment or payment.debt.lender_id != user.pk:
            raise LinkError("To'lov topilmadi")
        if payment.status != "pending":
            return "Bu to'lov allaqachon ko'rib chiqilgan."
        debt = Debt.objects.select_for_update().get(pk=payment.debt_id)
        if ok:
            payment.status = "ok"
        else:
            payment.status = "rejected"
            debt.paid = max(debt.paid - payment.amount, 0)
            debt.closed_at = None if debt.remaining else debt.closed_at
            debt.save(update_fields=["paid", "closed_at"])
        payment.save(update_fields=["status"])
    who = escape(first_name(user))
    if ok:
        notify(debt.user, f"✅ <b>{who}</b> {som(payment.amount)} to'lovingizni tasdiqladi. Qoldi: {som(debt.remaining)}.")
        return "Tasdiqlandi ✅"
    notify(debt.user, f"✖️ <b>{who}</b> {som(payment.amount)} to'lovni olmaganini aytdi — summa qarzga qaytarildi. "
                      "U bilan gaplashib oling.", _app_buttons())
    return "Rad etildi — summa qarzga qaytarildi"


# ---------------------------------------------------------------- bog'lanishni uzish

def unlink(user, debt):
    if user.pk not in (debt.user_id, debt.lender_id) or not debt.lender_id:
        raise LinkError("Qarz topilmadi")
    other = debt.lender if user.pk == debt.user_id else debt.user
    with transaction.atomic():
        debt.payments.filter(status="pending").update(status="ok")
        debt.lender = None
        debt.save(update_fields=["lender"])
    activity.log(user, "debt_unlink")
    notify(other, f"🔓 <b>{escape(first_name(user))}</b> «{escape(debt.name)}» qarzi bo'yicha bog'lanishni uzdi. "
                  "Endi u sizning ro'yxatingizda yangilanmaydi.")


# ---------------------------------------------------------------- JSON (qarz bergan tomon uchun)

def lent_json(debt):
    pending = [{"id": p.id, "amount": p.amount, "date": p.date.isoformat()}
               for p in debt.payments.all() if p.status == "pending"]
    return {
        "id": debt.id, "name": debt.name, "borrower": first_name(debt.user),
        "total": debt.total, "paid": debt.paid, "remaining": debt.remaining, "percent": debt.percent,
        "closed": debt.remaining == 0, "pending": pending,
    }


def open_invites(user):
    """Hali tasdiqlanmagan «qarz berdim» havolalari."""
    cutoff = timezone.now() - dt.timedelta(days=DebtLink.TTL_DAYS)
    return [{"id": l.id, "amount": l.amount, "note": l.note, "url": invite_url(l), "text": share_text(l)}
            for l in user.debt_links.filter(direction="lent", status="open", created_at__gt=cutoff)]
