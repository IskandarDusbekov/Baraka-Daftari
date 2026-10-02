"""PWA: telefonga ilova sifatida o'rnatish (manifest, service worker, oflayn sahifa).

Service worker faqat statik fayllarni (CSS, JS, rasmlar) keshlaydi. Shaxsiy ma'lumotlar (/api/)
hech qachon keshlanmaydi — ular faqat tarmoqdan olinadi.
"""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Service worker o'zgarsa oshiring — eski kesh tozalanadi
SW_VERSION = "1"


@require_GET
@cache_control(max_age=86400, public=True)
def manifest(request):
    data = {
        "id": "/asosiy/",
        "name": "Baraka Daftari",
        "short_name": "Baraka Daftari",
        "description": "Xarajatlar, jamg'arma va qarzlarni yozib boradigan shaxsiy moliya daftari.",
        "lang": "uz",
        "start_url": "/asosiy/?manba=ilova",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f4f7fb",
        "theme_color": "#16a34a",
        "categories": ["finance", "productivity"],
        "icons": [
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        # Ikonkani bosib turganda chiqadigan tezkor havolalar
        "shortcuts": [
            {"name": "Xarajat yozish", "url": "/hamyon/#xarajat", "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Kirim yozish", "url": "/hamyon/#kirim", "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Kalkulyator", "url": "/kalkulyator/", "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192"}]},
        ],
    }
    response = JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    response["Content-Type"] = "application/manifest+json; charset=utf-8"
    return response


@require_GET
def service_worker(request):
    # Saytning ildizidan (/sw.js) beriladi — shunda butun saytni boshqara oladi.
    # Har safar tekshirilsin (no-cache), aks holda yangilanish kechikadi.
    # Lokal (DEBUG) rejimda statik fayl nomlarida xesh yo'q — keshlasak, o'zgarishlar ko'rinmay qoladi
    response = render(request, "sw.js", {"version": SW_VERSION, "cache_static": not settings.DEBUG},
                      content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    return render(request, "offline.html")
