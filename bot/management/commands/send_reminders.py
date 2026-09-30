"""Eslatmalarni qo'lda yoki crontab orqali yuborish.

    python manage.py send_reminders morning
    python manage.py send_reminders evening
"""
from django.core.management.base import BaseCommand

from bot import reminders
from bot.telegram import BotAPI


class Command(BaseCommand):
    help = "Ertalabki (navbatdagi saboq) yoki kechki (xarajatlar) eslatmani yuborish"

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=["morning", "evening"])

    def handle(self, *args, **opts):
        api = BotAPI()
        sender = reminders.send_morning if opts["kind"] == "morning" else reminders.send_evening
        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sender(api)} ta"))
