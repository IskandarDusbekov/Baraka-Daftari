"""Zaxira nusxa olib, uni Telegram'ga yuborish (har kecha cron orqali).

    python manage.py send_backup

Server buzilsa yoki o'chib ketsa ham, nusxa adminning Telegram'ida qoladi.
"""
from django.core.management.base import BaseCommand, CommandError

from core import backup


class Command(BaseCommand):
    help = "Bazadan zaxira nusxa olib, BACKUP_CHAT_IDS dagi Telegram chatlarga yuborish"

    def handle(self, *args, **opts):
        if not backup.telegram_enabled():
            raise CommandError(".env da BACKUP_CHAT_IDS va BOT_TOKEN ko'rsatilishi kerak")
        try:
            name = backup.create_backup(timeout=600)
            sent = backup.send_to_telegram(name)
        except backup.BackupError as e:
            self._alert(f"Zaxira nusxa olinmadi yoki yuborilmadi:\n{e}")
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"{name} → {sent} ta chatga yuborildi"))

    @staticmethod
    def _alert(text):
        """Cron jim ishlaydi — xato bo'lsa admin bilsin. Bu ham o'xshamasa, indamay o'tamiz."""
        from html import escape

        from django.conf import settings

        from bot.telegram import BotAPI

        try:
            api = BotAPI()
            for chat_id in settings.BACKUP_CHAT_IDS:
                api.send(chat_id, escape(text))
        except Exception:  # noqa: BLE001
            pass
