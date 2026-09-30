from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ".env dagi DEV_USERNAME / DEV_PASSWORD bilan dasturchi (superuser) yaratadi yoki parolini yangilaydi"

    def handle(self, *args, **opts):
        if not settings.DEV_PASSWORD:
            raise CommandError(".env faylida DEV_PASSWORD ni to'ldiring")
        User = get_user_model()
        user, created = User.objects.get_or_create(username=settings.DEV_USERNAME)
        user.is_staff = user.is_superuser = user.is_active = True
        user.set_password(settings.DEV_PASSWORD)
        user.save()
        action = "yaratildi" if created else "yangilandi"
        self.stdout.write(self.style.SUCCESS(f"Dasturchi '{user.username}' {action}. Kirish: /kirish/ yoki /admin/"))
