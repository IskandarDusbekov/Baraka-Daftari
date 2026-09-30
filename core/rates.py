"""O'zbekiston Markaziy banki (cbu.uz) dollar kursi.

Kurs soatiga bir marta olinadi va keshlanadi. cbu.uz javob bermasa, oxirgi ma'lum kurs
qaytariladi va 10 daqiqa qayta urinilmaydi — foydalanuvchi so'rovlari sekinlashmaydi.
"""
import logging

import requests
from django.core.cache import cache

log = logging.getLogger("core")

CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
CACHE_KEY = "cbu:usd"
LAST_KEY = "cbu:usd:last"
FAIL_KEY = "cbu:usd:fail"


def fetch_usd():
    resp = requests.get(CBU_URL, timeout=5)
    resp.raise_for_status()
    item = resp.json()[0]
    return {
        "rate": float(item["Rate"]),
        "diff": float(item.get("Diff") or 0),
        "date": item.get("Date", ""),  # "30.09.2026"
        "source": "O'zbekiston Respublikasi Markaziy banki",
    }


def usd_rate():
    """{'rate': 11821.18, 'diff': 14.21, 'date': '30.09.2026', 'stale': False} yoki None."""
    data = cache.get(CACHE_KEY)
    if data:
        return data
    if not cache.get(FAIL_KEY):
        try:
            data = {**fetch_usd(), "stale": False}
            cache.set(CACHE_KEY, data, 3600)
            cache.set(LAST_KEY, data, None)
            return data
        except (requests.RequestException, ValueError, KeyError, IndexError) as e:
            log.warning("CBU kursini olib bo'lmadi: %s", e)
            cache.set(FAIL_KEY, 1, 600)
    last = cache.get(LAST_KEY)
    return {**last, "stale": True} if last else None


def convert(amount, from_cur, to_cur, rate):
    """Butun songa yaxlitlab o'tkazadi (so'm va dollar ikkalasi ham butun sonda yuritiladi)."""
    if from_cur == to_cur:
        return amount
    if from_cur == "UZS" and to_cur == "USD":
        return round(amount / rate)
    return round(amount * rate)
