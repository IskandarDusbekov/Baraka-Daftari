from django.core.management.base import BaseCommand

from core.models import Lesson
from core.saboq_data import load_saboqlar


class Command(BaseCommand):
    help = "core/saboq_data.py dagi saboqlarni bazaga yuklash (yaratish/yangilash)"

    def handle(self, *args, **opts):
        count = load_saboqlar(Lesson)
        self.stdout.write(self.style.SUCCESS(f"{count} ta saboq yuklandi. Bazada jami: {Lesson.objects.count()}"))
