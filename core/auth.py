"""Telegram orqali autentifikatsiya va API tokenlari."""
import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import parse_qsl

from django.conf import settings
from django.core import signing

from .models import TgUser

TOKEN_SALT = "baraka-api-token"


def verify_webapp_init_data(init_data, bot_token, max_age=24 * 3600):
    """Mini App `initData` imzosini tekshiradi va `user` lug'atini qaytaradi.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(pairs.get("auth_date", "0"))
        user = json.loads(pairs.get("user", "{}"))
    except (ValueError, TypeError):
        return None
    if max_age and time.time() - auth_date > max_age:
        return None
    if not isinstance(user, dict) or "id" not in user:
        return None
    return user


def make_api_token(user):
    """Imzolangan token: ichida taxmin qilib bo'lmaydigan UUID va token versiyasi.

    Versiya oshirilsa (admin "sessiyalarni tugatish" yoki foydalanuvchi "barcha qurilmalardan chiqish"),
    avval berilgan barcha tokenlar darhol bekor bo'ladi.
    """
    return signing.dumps({"u": str(user.uid), "v": user.token_version}, salt=TOKEN_SALT, compress=True)


def user_from_token(token):
    if not token or len(token) > 512:
        return None
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=settings.API_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or "u" not in data:
        return None
    try:
        uid = uuid.UUID(str(data["u"]))
    except ValueError:
        return None
    user = TgUser.objects.filter(uid=uid, is_active=True).first()
    if user is None or user.token_version != data.get("v"):
        return None
    return user


def user_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return user_from_token(header[7:].strip())
