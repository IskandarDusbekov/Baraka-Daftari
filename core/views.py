from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt


def page(template, active):
    """Sahifa ko'rinishi. Ma'lumotlar API orqali sahifaning o'z JS faylida yuklanadi."""

    @xframe_options_exempt  # Telegram Web Mini App'ni iframe ichida ochadi
    def view(request, **kwargs):
        context = {"bot_username": settings.BOT_USERNAME, "dev_login": settings.DEV_LOGIN, "active": active, **kwargs}
        return render(request, template, context)

    return view


@xframe_options_exempt
def landing(request):
    """Ochiq bosh sahifa (landing). Kirgan foydalanuvchi JS orqali /asosiy/ ga o'tkaziladi."""
    from . import services

    lessons = services.published_lessons()
    return render(request, "landing.html", {
        "bot_username": settings.BOT_USERNAME,
        "lessons": lessons,
        "dev_login": settings.DEV_LOGIN,
    })


home = page("pages/home.html", "asosiy")
wallet = page("pages/wallet.html", "hamyon")
debts = page("pages/debts.html", "qarzlar")
lessons = page("pages/lessons.html", "saboqlar")
savings = page("pages/savings.html", "jamgarma")
settings_page = page("pages/settings.html", "sozlamalar")
about = page("pages/about.html", "haqida")
login = page("pages/login.html", "kirish")
calculators = page("pages/calc.html", "kalkulyator")
_lesson = page("pages/lesson.html", "saboqlar")


def lesson(request, number):
    if not 1 <= number <= 1000:
        raise Http404
    return _lesson(request, number=number)
