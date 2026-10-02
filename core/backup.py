"""Bazaning zaxira nusxasi (admin panel → Zaxira nusxa).

PostgreSQL'da `pg_dump -Fc` (siqilgan, `pg_restore` bilan tiklanadi), lokal SQLite'da esa bazaning
izchil nusxasi olinadi. Nusxalar BACKUP_DIR papkasida saqlanadi, eng yangi KEEP tasi qoldiriladi.
Asosiy kunlik zaxira — serverdagi cron (deploy/backup.sh); bu yerdagisi qo'lda, "hozir" olish uchun.
"""
import datetime as dt
import os
import re
import sqlite3
import subprocess
from pathlib import Path

from django.conf import settings
from django.db import connection

KEEP = 10
NAME_RE = re.compile(r"^baraka-\d{8}-\d{6}\.(dump|sqlite3)$")


class BackupError(Exception):
    pass


def backup_dir():
    path = Path(settings.BACKUP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)  # nusxalarni faqat ilova foydalanuvchisi o'qiy olsin
    except OSError:
        pass
    return path


def list_backups():
    items = []
    for f in backup_dir().iterdir():
        if f.is_file() and NAME_RE.match(f.name):
            st = f.stat()
            items.append({"name": f.name, "size": st.st_size,
                          "created": dt.datetime.fromtimestamp(st.st_mtime)})
    return sorted(items, key=lambda x: x["name"], reverse=True)


def path_of(name):
    """Faqat bizning nomlash qoidasiga mos fayl — '../../.env' kabi yo'llar o'tmaydi."""
    if not NAME_RE.match(name or ""):
        return None
    path = backup_dir() / name
    return path if path.is_file() else None


def create_backup(timeout=25):
    """`timeout` — panel so'rovi uchun qisqa; kechki cron buyrug'i (send_backup) uzunroq beradi."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    db = settings.DATABASES["default"]
    if connection.vendor == "postgresql":
        path = backup_dir() / f"baraka-{stamp}.dump"
        env = {**os.environ, "PGPASSWORD": db.get("PASSWORD", "")}
        cmd = ["pg_dump", "-Fc", "--no-owner", "-h", db.get("HOST") or "127.0.0.1", "-p", str(db.get("PORT") or 5432),
               "-U", db["USER"], "-d", db["NAME"], "-f", str(path)]
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise BackupError("Serverda pg_dump topilmadi (postgresql-client o'rnatilmagan)")
        except subprocess.TimeoutExpired:
            path.unlink(missing_ok=True)
            raise BackupError(f"Baza katta — nusxa {timeout} soniyada tugamadi. Serverdagi kunlik zaxiradan foydalaning")
        if result.returncode != 0:
            path.unlink(missing_ok=True)
            raise BackupError(f"pg_dump xatosi: {result.stderr.strip()[:300]}")
    elif connection.vendor == "sqlite":
        path = backup_dir() / f"baraka-{stamp}.sqlite3"
        src = sqlite3.connect(str(db["NAME"]))
        dst = sqlite3.connect(str(path))
        try:
            src.backup(dst)  # yozilayotgan paytda ham izchil nusxa
        finally:
            dst.close()
            src.close()
    else:
        raise BackupError(f"{connection.vendor} bazasi uchun zaxira qo'llab-quvvatlanmaydi")
    os.chmod(path, 0o600)
    _cleanup()
    return path.name


def delete_backup(name):
    path = path_of(name)
    if path:
        path.unlink()
        return True
    return False


TELEGRAM_LIMIT = 49 * 1024 * 1024  # Bot API hujjat cheklovi 50 MB


def telegram_enabled():
    return bool(settings.BACKUP_CHAT_IDS and settings.BOT_TOKEN)


def send_to_telegram(name):
    """Nusxani BACKUP_CHAT_IDS ga yuboradi. Qaytaradi: nechta chatga yetib bordi."""
    from bot.telegram import BotAPI, TelegramError
    from core.models import TgUser

    path = path_of(name)
    if not path:
        raise BackupError("Nusxa topilmadi")
    if not telegram_enabled():
        raise BackupError(".env da BACKUP_CHAT_IDS (yoki BOT_TOKEN) ko'rsatilmagan")
    size = path.stat().st_size
    if size > TELEGRAM_LIMIT:
        raise BackupError(f"Nusxa {size // (1024 * 1024)} MB — Telegram 50 MB dan kattasini qabul qilmaydi. Panel orqali yuklab oling")
    caption = (f"<b>Baraka Daftari · zaxira nusxa</b>\n{name}\n"
               f"Hajmi: {max(size // 1024, 1)} KB · Foydalanuvchilar: {TgUser.objects.count()}\n"
               "Faylni hech kimga yubormang.")
    api = BotAPI()
    sent, errors = 0, []
    for chat_id in settings.BACKUP_CHAT_IDS:
        try:
            api.send_document(chat_id, path, caption)
            sent += 1
        except (TelegramError, OSError, ValueError) as e:  # requests xatolari OSError'dan, JSON xatosi ValueError'dan
            errors.append(f"{chat_id}: {e}")
    if not sent:
        raise BackupError("Telegram'ga yuborilmadi — " + "; ".join(errors)[:300])
    return sent


def _cleanup():
    for item in list_backups()[KEEP:]:
        (backup_dir() / item["name"]).unlink(missing_ok=True)
