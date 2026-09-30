"""Xavfsizlik sarlavhalari (Content-Security-Policy va boshqalar).

CSP brauzerga faqat ruxsat etilgan manbalardan skript/uslub/rasm yuklashni aytadi — hatto qaysidir
yo'l bilan sahifaga begona kod tushsa ham (XSS), u tashqi serverga ma'lumot yubora olmaydi.
"""

TELEGRAM_FRAMES = "'self' https://web.telegram.org https://*.telegram.org"

CSP = "; ".join([
    "default-src 'self'",
    # Inline: sahifa sozlamalari (window.BARAKA) va landing'dagi qisqa yo'naltirish skripti
    "script-src 'self' 'unsafe-inline' https://telegram.org https://www.googletagmanager.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https:",
    "connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com https://www.googletagmanager.com",
    "frame-src https://www.youtube-nocookie.com https://www.youtube.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])

PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Mini App sahifalarini faqat Telegram (web.telegram.org) iframe ichida ochish mumkin,
        # qolganlarini — hech kim (clickjacking'dan himoya)
        ancestors = TELEGRAM_FRAMES if getattr(response, "xframe_options_exempt", False) else "'self'"
        response.setdefault("Content-Security-Policy", f"{CSP}; frame-ancestors {ancestors}")
        response.setdefault("Permissions-Policy", PERMISSIONS)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        response.setdefault("X-Content-Type-Options", "nosniff")
        if request.path.startswith(("/api/", "/boshqaruv/", "/admin/")):
            # Shaxsiy ma'lumotlar proksi/brauzer keshida qolmasin
            response.setdefault("Cache-Control", "no-store")
        return response
