"""Kiruvchi Telegram yangilanishlarini qayta ishlash."""
import logging

from django.conf import settings
from django.utils import timezone

from core import activity
from core.models import LoginCode, TgUser

from . import entries, messages, reports
from .telegram import TelegramError

log = logging.getLogger("bot")

BLOCKED_TEXT = "⛔️ Hisobingiz vaqtincha bloklangan. Savol bo'lsa, sayt orqali biz bilan bog'laning."

COMMANDS = {
    "/qoldi": "left", "/hafta": "week", "/daromad": "income", "/jamgarma": "savings",
    "/qarz": "debts", "/kurs": "rate", "/bugun": "lesson", "/eslatma": "notify",
}


def handle_update(api, update):
    if "message" in update:
        handle_message(api, update["message"])
    elif "callback_query" in update:
        handle_callback(api, update["callback_query"])
    elif "my_chat_member" in update:
        handle_member(update["my_chat_member"])


def _user_for(tg_from):
    user, created = TgUser.upsert_from_telegram(tg_from)
    if created:
        activity.log(user, "register", source="bot")
    if not user.bot_started:
        # Birinchi kuni salomlashuv xabari yetarli, ertalabki eslatma ertadan boshlanadi
        user.last_morning_date = timezone.localdate()
        activity.log(user, "bot_start")
    if not user.bot_started or user.bot_blocked:
        user.bot_started, user.bot_blocked = True, False
        user.save(update_fields=["bot_started", "bot_blocked", "last_morning_date"])
    return user


def handle_message(api, msg):
    chat = msg.get("chat", {})
    if chat.get("type") != "private" or "from" not in msg:
        return
    user = _user_for(msg["from"])
    if not user.is_active:
        # Bloklangan foydalanuvchi: botda ham hech narsa qila olmaydi (spamga javob bermaslik uchun soatiga bir marta)
        if activity.allow(f"bot-blocked:{user.pk}", 1, 3600):
            api.send(user.tg_id, BLOCKED_TEXT)
        return
    text = (msg.get("text") or "").strip()
    command, _, arg = text.partition(" ")
    command = command.split("@")[0].lower()

    action = messages.MENU_ACTIONS.get(text) or COMMANDS.get(command)
    if action or command.startswith("/"):
        entries.clear_state(user)  # boshqa tugma bosildi — chala qolgan yozuv unutiladi

    if action in ("add_expense", "add_income"):
        api.send(user.tg_id, *entries.start(user, action[4:]))
    elif command == "/start" and arg.startswith("login_"):
        ask_login_confirm(api, user, arg[len("login_"):])
    elif command == "/start":
        api.send(user.tg_id, *messages.welcome(user))
        api.send(user.tg_id, messages.menu_hint(), keyboard=messages.main_keyboard())
    elif action in reports.REPORTS:
        activity.log(user, "bot_report", report=action)
        api.send(user.tg_id, *reports.REPORTS[action](user))
    elif action == "lesson":
        reply = messages.lesson_message(user)
        if reply:
            api.send(user.tg_id, *reply)
        else:
            api.send(user.tg_id, "🏆 Hozircha barcha saboqlarni o'tgansiz. Yangi video chiqishi bilan xabar beraman!")
    elif action == "notify":
        user.notify = not user.notify
        user.save(update_fields=["notify"])
        state = "yoqildi 🔔" if user.notify else "o'chirildi 🔕"
        api.send(user.tg_id, f"Kundalik eslatmalar {state}.\n"
                             "Ertalab — saboq, kechqurun — xarajatlarni yozish eslatmasi.\n"
                             "Qayta o'zgartirish: /eslatma")
    elif command == "/haqida":
        api.send(user.tg_id, messages.about_text())
    elif not command.startswith("/") and (reply := entries.handle_text(user, text)):
        api.send(user.tg_id, *reply)
    else:
        # Menyu eskirgan yoki yashirilgan bo'lsa ham qaytadan chiqadi
        api.send(user.tg_id, messages.help_text(), keyboard=messages.main_keyboard())


def ask_login_confirm(api, user, code):
    login = LoginCode.objects.filter(code=code, consumed=False, confirmed=False).first()
    if not login or (timezone.now() - login.created_at).total_seconds() > settings.LOGIN_CODE_TTL:
        api.send(user.tg_id, "⏳ Kirish havolasining muddati o'tgan. Saytda qaytadan «Kirish» tugmasini bosing.")
        return
    api.send(user.tg_id, messages.login_confirm_text(), [
        [{"text": "✅ Ha, saytga kiraman", "callback_data": f"login:{login.pk}"}],
    ])


def handle_callback(api, cq):
    data = cq.get("data") or ""
    user = _user_for(cq["from"])
    answer = ""
    if not user.is_active:
        answer = "Hisobingiz bloklangan"
    elif data.startswith("login:"):
        answer = confirm_login(api, user, data.split(":", 1)[1], cq.get("message"))
    elif data.startswith("r:") and data[2:] in reports.REPORTS and cq.get("message"):
        answer = refresh_report(api, user, data[2:], cq["message"])
    elif data == "x" or data[:2] in ENTRY_CALLBACKS:
        reply = entry_callback(user, data)
        if reply and data[:2] in ("a:", "s:"):
            api.send(user.tg_id, *reply)  # tasdiq xabari o'z joyida qolsin
        elif reply:
            _replace(api, user, cq.get("message"), *reply)
    try:
        api.call("answerCallbackQuery", callback_query_id=cq["id"], text=answer)
    except TelegramError as e:
        log.warning("answerCallbackQuery: %s", e)


ENTRY_CALLBACKS = ("k:", "c:", "i:", "s:", "u:", "a:")


def entry_callback(user, data):
    """Xarajat/daromad yozish tugmalari. (matn, tugmalar) qaytaradi."""
    value = data[2:]
    if data == "x":
        return entries.cancel(user)
    if data.startswith("k:"):
        return entries.choose_kind(user, value)
    if data.startswith("c:"):
        return entries.save_expense(user, value)
    if data.startswith("i:"):
        return entries.save_income(user, value)
    if data.startswith("a:") and value in ("expense", "income"):
        return entries.start(user, value)
    if data.startswith("s:") and value.isdigit():
        return entries.save_from_income(user, int(value))
    kind, _, pk = value.partition(":")
    if data.startswith("u:") and kind in ("e", "i") and pk.isdigit():
        return entries.undo(user, kind, int(pk))
    return None


def _replace(api, user, message, text, buttons=None):
    """Tugma bosilgan xabarni yangilaydi (eski tugmalar qayta bosilmasin); bo'lmasa yangi xabar."""
    if message:
        try:
            api.edit(message["chat"]["id"], message["message_id"], text, buttons)
            return
        except TelegramError as e:
            log.warning("editMessageText: %s", e)
    api.send(user.tg_id, text, buttons)


def refresh_report(api, user, key, message):
    """«🔄 Yangilash»: xabarni yangi raqamlar bilan o'rnida almashtiradi."""
    if not activity.allow(f"bot-refresh:{user.pk}", 20, 60):
        return "Biroz kuting…"
    text, buttons = reports.REPORTS[key](user)
    try:
        api.edit(message["chat"]["id"], message["message_id"], text, buttons)
    except TelegramError as e:
        if "not modified" in str(e):
            return "Yangi o'zgarish yo'q"
        log.warning("refresh_report: %s", e)
    return "Yangilandi"


def confirm_login(api, user, login_pk, message):
    login = LoginCode.objects.filter(pk=login_pk, consumed=False).first()
    if not login or (timezone.now() - login.created_at).total_seconds() > settings.LOGIN_CODE_TTL:
        return "Muddati o'tgan. Saytda qaytadan urinib ko'ring."
    if login.confirmed and login.user_id != user.pk:
        return "Bu havola allaqachon ishlatilgan."
    login.user, login.confirmed = user, True
    login.save(update_fields=["user", "confirmed"])
    if message:
        try:
            api.call("editMessageText", chat_id=message["chat"]["id"], message_id=message["message_id"],
                     text="✅ Kirish tasdiqlandi! Brauzerga qayting — sahifa o'zi ochiladi.")
        except TelegramError as e:
            log.warning("editMessageText: %s", e)
    return "Tasdiqlandi ✅"


def handle_member(update):
    """Foydalanuvchi botni bloklasa yoki qayta yoqsa."""
    status = update.get("new_chat_member", {}).get("status")
    tg_id = update.get("from", {}).get("id")
    if tg_id and status in ("kicked", "member"):
        TgUser.objects.filter(tg_id=tg_id).update(bot_blocked=(status == "kicked"))
        user = TgUser.objects.filter(tg_id=tg_id).first()
        if user and status == "kicked":
            activity.log(user, "bot_block")
