"""Bot xabarlari matnlari va tugmalari."""
from html import escape

from core import services
from .telegram import app_button, webapp_url

DISCLAIMER = (
    "ℹ️ <b>USHBU LOYIHA ABDUKARIM MIRZAYEVNING «BARAKA DAFTARI» KO'RSATUVIDAN "
    "ILHOMLANGAN HOLDA, INSONLARGA QULAYLIK YARATISH MAQSADIDA ISHLAB CHIQILDI. "
    "BARCHA HUQUQLAR VA ASL G'OYA MUALLIFI ABDUKARIM MIRZAYEVGA TEGISHLI.</b>"
)


def _rows(*rows):
    """None tugmalarni tashlab yuboradi."""
    result = []
    for row in rows:
        row = [b for b in row if b]
        if row:
            result.append(row)
    return result or None


# Pastdagi doimiy menyu: tugma matni -> hisobot kaliti (bot/reports.py)
MENU = [
    [("➖ Xarajat", "add_expense"), ("➕ Daromad", "add_income")],
    [("💰 Qancha qoldi", "left"), ("📅 Shu hafta", "week")],
    [("📈 Daromadim", "income"), ("🏦 Jamg'armam", "savings")],
    [("💳 Qarzlarim", "debts"), ("💱 Dollar kursi", "rate")],
]
MENU_ACTIONS = {text: key for row in MENU for text, key in row}


def main_keyboard():
    rows = [[{"text": text} for text, _ in row] for row in MENU]
    url = webapp_url("asosiy/")
    if url and url.startswith("https://"):
        rows.insert(0, [{"text": "📝 Daftarni ochish", "web_app": {"url": url}}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True,
            "input_field_placeholder": "Bo'limni tanlang"}


def menu_hint():
    return (
        "👇 <b>Pastdagi tugmalar:</b>\n"
        "➖ xarajat va ➕ daromadni shu yerning o'zida yozasiz;\n"
        "💰 bu oy qancha pul qoldi · 📅 shu hafta qancha sarfladingiz;\n"
        "📈 daromad · 🏦 jamg'arma · 💳 qarzlar · 💱 dollar kursi.\n\n"
        "💡 Tez yo'l: shunchaki summani yozing, masalan <b>45000 non</b>."
    )


def welcome(user):
    text = (
        f"Assalomu alaykum, <b>{escape(user.first_name or 'do‘stim')}</b>! 🌿\n\n"
        "<b>Elektron Baraka Daftari</b>ga xush kelibsiz.\n\n"
        "Bu yerda siz:\n"
        "📚 har hafta yangi video bo'yicha saboqlar va amaliy vazifalar olasiz;\n"
        "💰 daromadingizning bir qismini (5–20%) o'zingizga to'laysiz;\n"
        "📒 xarajatlaringizni yozib borasiz;\n"
        "❄️ qarzlardan «qor bo'lagi» usulida qutulasiz.\n\n"
        "Yangi saboq qo'shilganda xabar beraman, kechqurun esa xarajatlarni "
        "yozishni eslatib turaman.\n\n"
        f"{DISCLAIMER}"
    )
    return text, _rows([app_button("📝 Daftarni ochish")])


def help_text():
    return (
        "🤖 <b>Buyruqlar</b>\n\n"
        "/qoldi — bu oy qancha pul qoldi\n"
        "/hafta — shu hafta qancha sarfladim\n"
        "/daromad — daromad va o'zimga to'lash\n"
        "/jamgarma — qo'riqchi va o'sadigan pul\n"
        "/qarz — qarzlarim\n"
        "/kurs — Markaziy bank dollar kursi\n"
        "/bugun — navbatdagi saboq va vazifa\n"
        "/eslatma — eslatmalarni yoqish/o'chirish\n"
        "/haqida — loyiha haqida\n\n"
        "Xarajat yoki daromad yozish uchun pastdagi «➖ Xarajat» / «➕ Daromad» ni bosing "
        "yoki shunchaki summani yozing: <b>45000 non</b>."
    )


def about_text():
    return (
        "📖 <b>Elektron Baraka Daftari</b>\n\n"
        "Moliyaviy saboqlarni kichik amaliy qadamlar orqali odatga "
        "aylantiruvchi bepul raqamli daftar.\n\n"
        f"{DISCLAIMER}"
    )


def lesson_message(user, morning=False):
    """Navbatdagi saboq haqida xabar. Ochiq saboq bo'lmasa (hammasi bajarilgan / ertaga) None."""
    lesson, state = services.current_lesson(user)
    if lesson is None:
        return None
    if state == "wait":
        if morning:
            return None
        text = (
            "✅ Bugungi saboq bajarildi. Barakalla!\n\n"
            f"Keyingisi — <b>{lesson.number}-saboq: {escape(lesson.title)}</b> ertaga ochiladi."
        )
        return text, _rows([app_button("📝 Daftarni ochish")])
    greet = "Assalomu alaykum! ☀️\n\n" if morning else ""
    total = len(services.published_lessons())
    text = (
        f"{greet}📚 Sizni Baraka Daftarining <b>{lesson.number}-saboqi</b> kutmoqda ({lesson.number}/{total}).\n\n"
        f"<b>{escape(lesson.title)}</b>\n"
        f"📌 Vazifa: {escape(lesson.task_title)}\n\n"
        "Videoni ko'rish va vazifani bajarish uchun pastdagi tugmani bosing."
    )
    return text, lesson_buttons(lesson)


def lesson_buttons(lesson):
    return _rows(
        [{"text": "🎬 Videoni ko'rish", "url": lesson.video_url}],
        [app_button("📝 Daftarni ochish", f"saboqlar/{lesson.number}/")],
    )


def new_lesson_announcement(lesson):
    """Admin yangi saboq qo'shganda barchaga yuboriladigan xabar."""
    text = (
        "🆕 <b>Yangi saboq qo'shildi!</b>\n\n"
        f"📚 <b>{lesson.number}-saboq: {escape(lesson.title)}</b>\n\n"
        f"{escape(lesson.summary[:300])}{'…' if len(lesson.summary) > 300 else ''}\n\n"
        "Videoni ko'ring va vazifalarni bajaring 👇"
    )
    return text, lesson_buttons(lesson)


def evening_message(user):
    text = (
        "🌙 Xayrli kech!\n\n"
        "<b>Bugungi xarajatlaringizni kiritdingizmi?</b>\n"
        "Atigi 1 daqiqa — va oy oxirida pulingiz qayerga ketganini aniq bilasiz."
    )
    return text, _rows([{"text": "➖ Xarajat yozish", "callback_data": "a:expense"},
                        app_button("📝 Daftar", "hamyon/")])


def login_confirm_text():
    return (
        "🔐 <b>Saytga kirish so'rovi</b>\n\n"
        "Brauzerda «Elektron Baraka Daftari» saytiga kirish so'raldi.\n"
        "Agar bu siz bo'lsangiz — pastdagi tugmani bosing.\n\n"
        "⚠️ Agar siz so'ramagan bo'lsangiz, hech narsa bosmang."
    )
