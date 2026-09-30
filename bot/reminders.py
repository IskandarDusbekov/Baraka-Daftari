"""Eslatmalar va ommaviy xabarlar.

Bot jarayonidagi alohida fon oqimi (runbot) chaqiradi, shuning uchun 100 000+ foydalanuvchiga
yuborish bot javoblarini to'xtatib qo'ymaydi. Telegram limiti ~30 xabar/soniya — biz ~25 da yuboramiz.
"""
import datetime as dt
import logging
import time
from html import escape

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Broadcast, Expense, TgUser

from . import messages
from .telegram import TelegramError

log = logging.getLogger("bot")

SEND_DELAY = 0.04  # ~25 xabar/soniya
CHUNK = 2000


def _reachable():
    return TgUser.objects.filter(notify=True, bot_started=True, bot_blocked=False, is_active=True)


def _recipients(field, today):
    return _reachable().exclude(**{field: today})


def _deliver(api, user, reply):
    try:
        api.send(user.tg_id, *reply)
        return True
    except TelegramError as e:
        if e.code == 403:  # bot bloklangan
            TgUser.objects.filter(pk=user.pk).update(bot_blocked=True)
        elif e.code == 429:  # juda tez — biroz kutamiz
            time.sleep(3)
        else:
            log.warning("Xabar yuborilmadi %s: %s", user.tg_id, e)
    return False


def send_morning(api):
    today = timezone.localdate()
    sent = 0
    for user in _recipients("last_morning_date", today).iterator(chunk_size=CHUNK):
        reply = messages.lesson_message(user, morning=True)
        if reply and _deliver(api, user, reply):
            sent += 1
            time.sleep(SEND_DELAY)
        TgUser.objects.filter(pk=user.pk).update(last_morning_date=today)
    log.info("Ertalabki eslatma: %s ta yuborildi", sent)
    return sent


def send_evening(api):
    today = timezone.localdate()
    # Bugun xarajat kiritganlarni bitta so'rov bilan chiqarib tashlaymiz
    wrote_today = Expense.objects.filter(date=today).values("user_id")
    sent = 0
    for user in _recipients("last_evening_date", today).exclude(pk__in=wrote_today).iterator(chunk_size=CHUNK):
        if _deliver(api, user, messages.evening_message(user)):
            sent += 1
            time.sleep(SEND_DELAY)
        TgUser.objects.filter(pk=user.pk).update(last_evening_date=today)
    _recipients("last_evening_date", today).filter(pk__in=wrote_today).update(last_evening_date=today)
    log.info("Kechki eslatma: %s ta yuborildi", sent)
    return sent


def announce_lesson(api, lesson):
    """Yangi saboq e'lonini darhol yuboradi (kichik auditoriya / testlar uchun).
    Katta auditoriyada Broadcast navbatidan foydalaning."""
    reply = messages.new_lesson_announcement(lesson)
    sent = 0
    for user in _reachable().iterator(chunk_size=CHUNK):
        if _deliver(api, user, reply):
            sent += 1
            time.sleep(SEND_DELAY)
    log.info("Yangi saboq e'loni (%s): %s ta yuborildi", lesson.number, sent)
    return sent


# ---------------------------------------------------------------- ommaviy xabarlar navbati

def broadcast_audience(b):
    qs = _reachable()
    week_ago = timezone.now() - dt.timedelta(days=7)
    if b.audience == "active7":
        qs = qs.filter(last_seen__gte=week_ago)
    elif b.audience == "inactive7":
        qs = qs.filter(last_seen__lt=week_ago)
    return qs


def broadcast_reply(b):
    if b.lesson_id:
        return messages.new_lesson_announcement(b.lesson)
    return escape(b.text), None


def process_broadcasts(api, time_budget=50):
    """Navbatdagi ommaviy xabarni `time_budget` soniya davomida yuboradi va to'xtagan joyini saqlaydi."""
    with transaction.atomic():
        b = (Broadcast.objects.select_for_update(skip_locked=True)
             .filter(status__in=["pending", "sending"]).order_by("created_at").first())
        if not b:
            return 0
        if b.status == "pending":
            b.status = "sending"
            b.total = broadcast_audience(b).count()
            b.save(update_fields=["status", "total"])

    reply = broadcast_reply(b)
    started = time.monotonic()
    done = 0
    users = broadcast_audience(b).filter(pk__gt=b.last_user_id).order_by("pk")
    for user in users.iterator(chunk_size=500):
        if _deliver(api, user, reply):
            b.sent += 1
        else:
            b.failed += 1
        b.last_user_id = user.pk
        done += 1
        time.sleep(SEND_DELAY)
        if done % 100 == 0:
            b.save(update_fields=["sent", "failed", "last_user_id"])
        if time.monotonic() - started > time_budget:
            break
    else:
        b.status = "done"
        b.finished_at = timezone.now()
    b.save(update_fields=["sent", "failed", "last_user_id", "status", "finished_at"])
    return done


def run_due(api):
    """Vaqti kelgan eslatmalarni yuboradi. Har bir foydalanuvchiga kuniga bir marta."""
    now = timezone.localtime()
    if now.hour >= settings.EVENING_HOUR:
        send_evening(api)
    # Ertalabki xabar faqat ertalab (4 soatlik oyna ichida) yuboriladi
    if settings.MORNING_HOUR <= now.hour < min(settings.MORNING_HOUR + 4, settings.EVENING_HOUR):
        send_morning(api)
