from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("chiqish/", views.logout_view, name="logout"),
    path("voronka/", views.funnel, name="funnel"),
    path("foydalanuvchilar/", views.users, name="users"),
    # UUID: foydalanuvchi havolasini taxmin qilib yoki raqamni o'zgartirib boshqasiga o'tib bo'lmaydi
    path("foydalanuvchilar/<uuid:uid>/", views.user_detail, name="user"),
    path("foydalanuvchilar/<uuid:uid>/amal/", views.user_action, name="user_action"),
    path("amallar/", views.activity_log, name="activity"),
    path("kirishlar/", views.auth_log, name="auth"),
    path("saboqlar/", views.lessons, name="lessons"),
    path("saboqlar/yangi/", views.lesson_edit, name="lesson_new"),
    path("saboqlar/<int:pk>/", views.lesson_edit, name="lesson_edit"),
    path("saboqlar/<int:pk>/korinish/", views.lesson_preview, name="lesson_preview"),
    path("saboqlar/<int:pk>/amal/", views.lesson_action, name="lesson_action"),
    path("saboqlar/<int:pk>/elon/", views.lesson_announce, name="lesson_announce"),
    path("baholar/", views.feedback_list, name="feedback"),
    path("baholar/oqildi/", views.feedback_read, name="feedback_read"),
    path("seo/", views.seo_settings, name="seo"),
    path("sozlamalar/", views.site_settings, name="settings"),
    path("adminlar/", views.admins, name="admins"),
    path("adminlar/<int:pk>/amal/", views.admin_action, name="admin_action"),
    path("zaxira/", views.backups, name="backups"),
    path("zaxira/yuklab-olish/<str:name>", views.backup_download, name="backup_download"),
    path("seo/fayl/<int:pk>/ochirish/", views.seo_file_delete, name="seo_file_delete"),
    path("xabarlar/", views.broadcasts, name="broadcasts"),
]
