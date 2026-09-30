"""Amallar jurnali va yengil so'rov cheklovchi (rate limit)."""
import datetime as dt
import logging

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

from .models import ActivityLog, TgUser

log_ = logging.getLogger("core")

LAST_SEEN_EVERY = 300  # soniya: last_seen ni har so'rovda emas, 5 daqiqada bir yangilaymiz
VISIT_GAP_MINUTES = 30


def log(user, action, **meta):
    """Amalni jurnalga yozadi. Jurnal xatosi asosiy amalni buzmasligi kerak."""
    try:
        ActivityLog.objects.create(user=user, action=action, meta=meta)
    except Exception:  # noqa: BLE001
        log_.exception("ActivityLog yozilmadi: %s", action)


def touch_last_seen(user):
    """100k foydalanuvchida har so'rovda UPDATE qilmaslik uchun keshga tayanib kamdan-kam yangilaydi."""
    key = f"seen:{user.pk}"
    if cache.add(key, 1, LAST_SEEN_EVERY):
        now = timezone.now()
        updates = {"last_seen": now}
        # 30 daqiqadan uzoq tanaffusdan keyin kirish — yangi "tashrif" (baho so'rash shunga qarab)
        if user.last_seen and now - user.last_seen > dt.timedelta(minutes=VISIT_GAP_MINUTES):
            updates["visits"] = F("visits") + 1
            user.visits += 1
        TgUser.objects.filter(pk=user.pk).update(**updates)
        user.last_seen = now


def allow(key, limit, window):
    """Oynada `limit` tadan ko'p so'rovga ruxsat bermaydi. True — ruxsat."""
    cache_key = f"rl:{key}"
    if cache.add(cache_key, 1, window):
        return True
    try:
        return cache.incr(cache_key) <= limit
    except ValueError:  # kalit shu orada muddati tugagan bo'lsa
        cache.set(cache_key, 1, window)
        return True


def client_ip(request):
    """Mijoz IP manzili.

    X-Forwarded-For ning birinchi qiymatiga ishonib bo'lmaydi — uni mijozning o'zi yozib yuborishi
    mumkin (rate limitni aylanib o'tish uchun). Nginx `X-Real-IP` ni o'zi ($remote_addr) qo'yadi,
    shuning uchun faqat unga ishonamiz; nginx bo'lmasa — to'g'ridan-to'g'ri ulanish manzili.
    """
    return (request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or "").strip()[:64]
