"""SEO: robots.txt, sitemap.xml, qidiruv tizimlari tasdiqlash fayllari va meta-teglar.

Sozlamalar admin panel → SEO bo'limida o'zgartiriladi va 10 daqiqa keshlanadi (saqlanganda tozalanadi).
"""
import re

from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .models import SeoSettings, VerificationFile

CACHE_KEY = "seo:settings:v1"

DEFAULTS = {
    "title": "Baraka Daftari — pulingiz qayerga ketayotganini yozib boring",
    "description": ("Xarajatlarni yozing, avval o'zingizga to'lang, qarzdan reja bilan chiqing. "
                    "«Baraka Daftari» saboqlari asosidagi bepul daftar — Telegram ichida."),
    "og_title": "Baraka Daftari",
    "og_description": "Oylik tushadi, ikki haftada tugaydi — qayoqqa? Yozib boring, avval o'zingizga to'lang.",
}

# Faqat shu shakldagi fayl nomlari qabul qilinadi (yo'l/../ yoki boshqa fayllar emas)
VERIFICATION_NAME = re.compile(r"^(google[0-9a-f]{8,32}\.html|yandex_[0-9a-f]{8,32}\.html|BingSiteAuth\.xml)$")

# Qidiruvga chiqadigan ochiq sahifalar (ilova sahifalari kirish talab qiladi — ular indekslanmaydi)
PUBLIC_PAGES = [("/", "weekly", "1.0"), ("/kalkulyator/", "monthly", "0.8"), ("/haqida/", "monthly", "0.6")]


def seo_data():
    data = cache.get(CACHE_KEY)
    if data is None:
        s = SeoSettings.load()
        data = {
            "site_url": s.site_url.rstrip("/"),
            "title": s.title or DEFAULTS["title"],
            "description": s.description or DEFAULTS["description"],
            "keywords": s.keywords,
            "og_title": s.og_title or s.title or DEFAULTS["og_title"],
            "og_description": s.og_description or s.description or DEFAULTS["og_description"],
            "google_verification": s.google_verification,
            "yandex_verification": s.yandex_verification,
            "analytics_id": s.analytics_id if re.fullmatch(r"G-[A-Z0-9]{4,20}", s.analytics_id or "") else "",
            "robots_extra": s.robots_extra,
            "allow_indexing": s.allow_indexing,
        }
        cache.set(CACHE_KEY, data, 600)
    return data


def clear_cache():
    cache.delete(CACHE_KEY)


def context(request):
    """Shablonlar uchun: {{ seo.title }}, {{ seo.description }}…"""
    data = seo_data()
    base = data["site_url"] or f"{request.scheme}://{request.get_host()}"
    return {"seo": {**data, "base_url": base, "canonical": base + request.path}}


def _base(request):
    return seo_data()["site_url"] or f"{request.scheme}://{request.get_host()}"


@require_GET
@cache_control(max_age=3600, public=True)
def robots_txt(request):
    data = seo_data()
    if not data["allow_indexing"]:
        lines = ["User-agent: *", "Disallow: /"]
    else:
        lines = [
            "User-agent: *",
            "Allow: /$",
            "Allow: /haqida/",
            "Allow: /kalkulyator/",
            "Disallow: /api/",
            "Disallow: /boshqaruv/",
            "Disallow: /admin/",
            "Disallow: /kirish/",
        ]
        if data["robots_extra"]:
            lines += [line.strip() for line in data["robots_extra"].splitlines() if line.strip()]
        lines += ["", f"Sitemap: {_base(request)}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@require_GET
@cache_control(max_age=3600, public=True)
def sitemap_xml(request):
    base = _base(request)
    today = timezone.localdate().isoformat()
    urls = "".join(
        f"<url><loc>{base}{path}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for path, freq, prio in PUBLIC_PAGES
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def verification_file(request, filename):
    if not VERIFICATION_NAME.match(filename):
        raise Http404
    item = VerificationFile.objects.filter(filename=filename).first()
    if not item:
        raise Http404
    ctype = "application/xml" if filename.endswith(".xml") else "text/html"
    response = HttpResponse(item.content, content_type=f"{ctype}; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    return response
