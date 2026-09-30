"""Botni long polling rejimida ishga tushiradi.

    python manage.py runbot

Eslatmalar ham shu jarayon ichida vaqti-vaqti bilan tekshiriladi, shuning uchun
alohida crontab shart emas (xohlasangiz `send_reminders` buyrug'idan foydalaning).
"""
import logging
import threading
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from bot import reminders
from bot.handlers import handle_update
from bot.telegram import BotAPI, TelegramError, webapp_url

log = logging.getLogger("bot")

SCHEDULE_EVERY = 60  # soniya


class Command(BaseCommand):
    help = "Telegram botni ishga tushirish (long polling + eslatmalar)"

    def add_arguments(self, parser):
        parser.add_argument("--no-reminders", action="store_true", help="Eslatmalarni yubormaslik")

    def handle(self, *args, **opts):
        api = BotAPI()
        me = api.call("getMe")
        self.stdout.write(self.style.SUCCESS(f"Bot ishga tushdi: @{me['username']}"))
        self.setup(api)

        # Eslatmalar va ommaviy xabarlar alohida oqimda: yuborish uzoq davom etsa ham bot javob beradi
        worker = threading.Thread(target=self.worker, args=(not opts["no_reminders"],), daemon=True, name="bot-worker")
        worker.start()

        offset = None
        while True:
            close_old_connections()
            try:
                params = {"timeout": 25, "allowed_updates": ["message", "callback_query", "my_chat_member"]}
                if offset is not None:
                    params["offset"] = offset
                for update in api.call("getUpdates", http_timeout=35, **params):
                    offset = update["update_id"] + 1
                    try:
                        handle_update(api, update)
                    except Exception:
                        log.exception("Yangilanishni qayta ishlashda xato")
            except (requests.RequestException, TelegramError) as e:
                log.warning("getUpdates xatosi: %s", e)
                time.sleep(3)

    def worker(self, with_reminders):
        """Fon oqimi: ommaviy xabarlar navbati va kundalik eslatmalar."""
        api = BotAPI()  # requests.Session oqimlar o'rtasida bo'lishilmaydi
        last_schedule = 0.0
        while True:
            close_old_connections()
            try:
                busy = reminders.process_broadcasts(api)
            except Exception:
                log.exception("Ommaviy xabar yuborishda xato")
                busy = 0
            if with_reminders and time.time() - last_schedule > SCHEDULE_EVERY:
                last_schedule = time.time()
                try:
                    reminders.run_due(api)
                except Exception:
                    log.exception("Eslatmalarni yuborishda xato")
            if not busy:
                time.sleep(10)

    def setup(self, api):
        api.call("deleteWebhook")
        api.call("setMyCommands", commands=[
            {"command": "start", "description": "Boshlash va menyu"},
            {"command": "qoldi", "description": "Bu oy qancha pul qoldi"},
            {"command": "hafta", "description": "Shu hafta qancha sarfladim"},
            {"command": "daromad", "description": "Daromad va o'zimga to'lash"},
            {"command": "jamgarma", "description": "Jamg'armam"},
            {"command": "qarz", "description": "Qarzlarim"},
            {"command": "kurs", "description": "Markaziy bank dollar kursi"},
            {"command": "bugun", "description": "Navbatdagi saboq va vazifa"},
            {"command": "eslatma", "description": "Eslatmalarni yoqish/o'chirish"},
            {"command": "haqida", "description": "Loyiha haqida"},
        ])
        try:
            # Bot profilida /start bosilishidan oldin ko'rinadigan matnlar
            api.call("setMyShortDescription", short_description=(
                "Pulingiz qayerga ketayotganini biling: xarajat, jamg'arma, qarz va haftalik saboqlar."))
            api.call("setMyDescription", description=(
                "Elektron Baraka Daftari — Abdukarim Mirzayevning «Baraka Daftari» ko'rsatuvidan "
                "ilhomlangan bepul raqamli daftar.\n\n"
                "💰 Bu oy qancha pul qolganini ko'rsatadi\n"
                "📅 Haftalik xarajatlar hisoboti\n"
                "🏦 O'zingizga to'lash va jamg'arma\n"
                "❄️ Qarzdan «qor bo'lagi» usulida qutulish\n"
                "💱 Markaziy bank dollar kursi\n\n"
                "Boshlash uchun «Start» ni bosing."))
        except TelegramError as e:
            log.warning("Bot tavsifini o'rnatib bo'lmadi: %s", e)
        if settings.WEBAPP_URL.startswith("https://"):
            api.call("setChatMenuButton", menu_button={
                "type": "web_app", "text": "📝 Daftar", "web_app": {"url": webapp_url("asosiy/")},
            })
        else:
            self.stdout.write(self.style.WARNING(
                "WEBAPP_URL HTTPS emas — Mini App menyu tugmasi o'rnatilmadi (lokal rejim)."
            ))
