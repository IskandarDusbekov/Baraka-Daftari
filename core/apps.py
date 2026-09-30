from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Baraka Daftari"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import seo, services
        from .models import Lesson, SeoSettings

        def clear(**kwargs):
            services.clear_lessons_cache()

        def clear_seo(**kwargs):
            seo.clear_cache()

        post_save.connect(clear, sender=Lesson, dispatch_uid="lesson_cache_save")
        post_delete.connect(clear, sender=Lesson, dispatch_uid="lesson_cache_delete")
        post_save.connect(clear_seo, sender=SeoSettings, dispatch_uid="seo_cache_save")
