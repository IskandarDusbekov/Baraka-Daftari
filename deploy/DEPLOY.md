# Serverga joylash — ketma-ket buyruqlar

Ubuntu 22.04 / 24.04 VPS uchun. Kamida 2 GB RAM, 2 yadro (100 000+ foydalanuvchi uchun 4 yadro, 8 GB).

Quyida **`baraka.uz`** — o'z domeningiz, **`1.2.3.4`** — serveringiz IP manzili. Ularni o'zingiznikiga almashtiring.

---

## 0. Tayyorgarlik

1. Domen panelida **A-yozuv**: `baraka.uz` → `1.2.3.4` va `www.baraka.uz` → `1.2.3.4`.
2. @BotFather dan bot tokeni va username tayyor bo'lsin.

## 1. Loyihani arxivlash (o'z kompyuteringizda, PowerShell)

Maxfiy va keraksiz fayllar (`.env`, `venv`, lokal baza) serverga ketmaydi:

```powershell
cd C:\Users\ASUS\Desktop
tar -czf baraka.tar.gz --exclude=venv --exclude=.venv --exclude=.env --exclude=db.sqlite3 --exclude=__pycache__ --exclude=staticfiles --exclude=.claude Baraka-Daftari
scp baraka.tar.gz root@1.2.3.4:/root/
```

## 2. Serverni tayyorlash (serverda, root sifatida)

```bash
ssh root@1.2.3.4
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-dev build-essential libpq-dev \
    postgresql redis-server nginx certbot python3-certbot-nginx \
    ufw fail2ban unattended-upgrades
timedatectl set-timezone Asia/Tashkent

# Xavfsizlik devori: faqat SSH va veb
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Xavfsizlik yangilanishlari avtomatik o'rnatiladi; SSH parol tanlashdan fail2ban himoya qiladi
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now fail2ban

# Ilova uchun alohida foydalanuvchi (root emas!)
adduser --system --group --home /srv/baraka baraka
usermod -aG www-data baraka
```

## 3. PostgreSQL va Redis

Parolni o'zingiz yarating va eslab qoling (keyin `.env` ga yoziladi):

```bash
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))"); echo "$DB_PASS"
sudo -u postgres psql -c "CREATE USER baraka WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -c "CREATE DATABASE baraka OWNER baraka ENCODING 'UTF8';"
systemctl enable --now redis-server
```

Redis faqat serverning o'zidan ochiq bo'lishi kerak (standart holatda shunday):

```bash
grep -E '^bind' /etc/redis/redis.conf    # "bind 127.0.0.1 -::1" bo'lishi kerak
```

## 4. Kodni joylash

```bash
tar -xzf /root/baraka.tar.gz -C /srv/
cp -a /srv/Baraka-Daftari/. /srv/baraka/ && rm -rf /srv/Baraka-Daftari
cd /srv/baraka
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 5. `.env` (production sozlamalari)

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # SECRET_KEY uchun
python3 -c "import secrets; print('baza-' + secrets.token_hex(4))"  # ADMIN_URL uchun
nano /srv/baraka/.env
```

Ichiga (qiymatlarni o'zingiznikiga almashtiring):

```ini
SECRET_KEY=<yuqorida yaratilgan 50+ belgili kalit>
DEBUG=False
ALLOWED_HOSTS=baraka.uz,www.baraka.uz
CSRF_TRUSTED_ORIGINS=https://baraka.uz,https://www.baraka.uz
SSL_REDIRECT=False
HSTS_SECONDS=0
ADMIN_URL=<yuqorida yaratilgan, masalan baza-3f9a1c2e>/
REDIS_URL=redis://127.0.0.1:6379/1

DB_ENGINE=postgres
POSTGRES_DB=baraka
POSTGRES_USER=baraka
POSTGRES_PASSWORD=<3-qadamdagi DB_PASS>
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

BOT_TOKEN=<BotFather tokeni>
BOT_USERNAME=barakadaftaribot
WEBAPP_URL=https://baraka.uz/

DEV_LOGIN=False
MORNING_HOUR=8
EVENING_HOUR=20
```

Faylni faqat ilova o'qiy olsin:

```bash
chown -R baraka:www-data /srv/baraka
chmod 600 /srv/baraka/.env
sed -i 's/\r$//' /srv/baraka/deploy/*.sh    # Windows qator oxirlarini tozalash
```

## 6. Baza, statik fayllar, admin

```bash
cd /srv/baraka
sudo -u baraka .venv/bin/python manage.py migrate
sudo -u baraka .venv/bin/python manage.py load_saboqlar
sudo -u baraka .venv/bin/python manage.py collectstatic --noinput
sudo -u baraka .venv/bin/python manage.py createsuperuser     # parol kamida 10 belgi
sudo -u baraka .venv/bin/python manage.py check --deploy
```

`check --deploy` HTTPS haqida ogohlantirishi mumkin — 8-qadamda yoqamiz.

## 7. Gunicorn, bot va Nginx

```bash
cp /srv/baraka/deploy/baraka-web.service /srv/baraka/deploy/baraka-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now baraka-web baraka-bot
systemctl status baraka-web baraka-bot --no-pager

cp /srv/baraka/deploy/nginx.conf /etc/nginx/sites-available/baraka
sed -i 's/DOMAIN/baraka.uz/g' /etc/nginx/sites-available/baraka
sed -i "s#ADMIN_PATH#$(grep ^ADMIN_URL /srv/baraka/.env | cut -d= -f2 | tr -d /)#" /etc/nginx/sites-available/baraka
ln -sf /etc/nginx/sites-available/baraka /etc/nginx/sites-enabled/baraka
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Tekshirish: brauzerda `http://baraka.uz` ochilishi kerak.

## 8. HTTPS (SSL)

```bash
certbot --nginx -d baraka.uz -d www.baraka.uz --redirect -m sizning@email.uz --agree-tos -n
```

HTTPS ishlagach, `.env` da yoqing va qayta ishga tushiring:

```bash
sed -i 's/^SSL_REDIRECT=.*/SSL_REDIRECT=True/; s/^HSTS_SECONDS=.*/HSTS_SECONDS=31536000/' /srv/baraka/.env
systemctl restart baraka-web baraka-bot
sudo -u baraka /srv/baraka/.venv/bin/python /srv/baraka/manage.py check --deploy
```

Sertifikat avtomatik yangilanadi (`systemctl list-timers | grep certbot`).

## 9. Telegram

1. @BotFather → `/setuserpic` → botni tanlang → `static/img/bot-avatar.png` ni yuboring.
2. @BotFather → `/newapp` (yoki `/setmenubutton`) → Mini App manzili: `https://baraka.uz/asosiy/`.
3. `systemctl restart baraka-bot` — bot menyu tugmasi va buyruqlarni o'zi o'rnatadi.

## 10. Zaxira nusxa (har kecha)

```bash
install -m 755 /srv/baraka/deploy/backup.sh /usr/local/bin/baraka-backup
mkdir -p /var/backups/baraka && chown postgres /var/backups/baraka && chmod 700 /var/backups/baraka
(sudo -u postgres crontab -l 2>/dev/null; echo "30 3 * * * /usr/local/bin/baraka-backup") | sudo -u postgres crontab -
sudo -u postgres /usr/local/bin/baraka-backup && ls -lh /var/backups/baraka
```

Zaxiradan tiklash: `sudo -u postgres pg_restore -d baraka --clean /var/backups/baraka/baraka-YYYY-MM-DD.dump`

## 11. Google Search Console

1. `https://baraka.uz/boshqaruv/seo/` → sayt manzili, sarlavha, tavsifni to'ldiring.
2. [Search Console](https://search.google.com/search-console) → URL prefiksi → **HTML fayl** → faylni SEO sahifasida yuklang → «Tasdiqlash».
3. Search Console → Sitemaps → `sitemap.xml` ni qo'shing.

---

## Yangilash (keyingi versiyalar)

Kompyuteringizda 1-qadamdagi arxivni qayta yarating va yuboring, keyin serverda:

```bash
cd /srv/baraka
tar -xzf /root/baraka.tar.gz -C /tmp/ && cp -a /tmp/Baraka-Daftari/. /srv/baraka/ && rm -rf /tmp/Baraka-Daftari
chown -R baraka:www-data /srv/baraka && chmod 600 .env
sudo -u baraka .venv/bin/pip install -r requirements.txt
sudo -u baraka .venv/bin/python manage.py migrate
sudo -u baraka .venv/bin/python manage.py collectstatic --noinput
systemctl restart baraka-web baraka-bot
```

## Muammo bo'lsa — loglar

```bash
journalctl -u baraka-web -n 100 --no-pager      # Django / Gunicorn xatolari
journalctl -u baraka-bot -n 100 --no-pager      # bot
journalctl -u baraka-web | grep -E "security|panel.audit"   # admin kirishlari va amallari
tail -n 50 /var/log/nginx/error.log
```
