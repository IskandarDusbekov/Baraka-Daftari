from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from panel.views import admin_login

# Django admin o'z kirish sahifasini ishlatmaydi — panel kirishiga yo'naltiriladi
# (u yerda urinishlar soni cheklangan, bruteforce'dan himoya)
admin.site.login = admin_login

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("boshqaruv/", include("panel.urls")),
    path("", include("core.urls")),
]
