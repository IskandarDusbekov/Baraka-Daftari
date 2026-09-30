"""Telegram Bot API uchun yengil klient."""
import logging
import requests
from django.conf import settings

log = logging.getLogger("bot")


class TelegramError(Exception):
    def __init__(self, description, code=None):
        super().__init__(description)
        self.code = code


class BotAPI:
    def __init__(self, token=None):
        self.token = token or settings.BOT_TOKEN
        if not self.token:
            raise RuntimeError("BOT_TOKEN o'rnatilmagan (.env faylini tekshiring)")
        self.base = f"https://api.telegram.org/bot{self.token}/"
        self.session = requests.Session()

    def call(self, method, http_timeout=35, **params):
        # `http_timeout` — so'rovning o'zi uchun; `timeout` esa Telegram parametri (getUpdates long polling)
        resp = self.session.post(self.base + method, json=params, timeout=http_timeout)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(data.get("description", "unknown error"), data.get("error_code"))
        return data["result"]

    def send(self, chat_id, text, buttons=None, keyboard=None):
        """`buttons` — xabar ostidagi inline tugmalar, `keyboard` — pastdagi doimiy menyu."""
        params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        elif keyboard:
            params["reply_markup"] = keyboard
        return self.call("sendMessage", **params)

    def edit(self, chat_id, message_id, text, buttons=None):
        params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        return self.call("editMessageText", **params)


def webapp_url(path=None):
    """Mini App manzili. `path` — sahifa yo'li, masalan "hamyon/" yoki "saboqlar/4/"."""
    url = settings.WEBAPP_URL
    if not url or not path:
        return url
    return url.rstrip("/") + "/" + path.lstrip("/")


def app_button(text, path="asosiy/"):
    """HTTPS bo'lsa haqiqiy Mini App tugmasi, aks holda oddiy havola."""
    url = webapp_url(path)
    if not url:
        return None
    if url.startswith("https://"):
        return {"text": text, "web_app": {"url": url}}
    return {"text": text, "url": url}
