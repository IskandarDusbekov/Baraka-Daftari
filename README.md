# Elektron Baraka Daftari

Telegram Mini App + Telegram bot + veb sayt. Odamlarga daromadning 10% ini saqlash, xarajatlarni
nazorat qilish va qarzdan qutulishni Abdukarim Mirzayevning haftalik saboqlari asosida kichik amaliy
qadamlar bilan o'rgatadigan raqamli daftar.

> **Ushbu loyiha Abdukarim Mirzayevning «Baraka Daftari» ko'rsatuvidan ilhomlangan holda, insonlarga
> qulaylik yaratish maqsadida ishlab chiqildi.**

## Imkoniyatlar

| Bo'lim | Manzil | Nima qiladi |
|---|---|---|
| Landing | `/` | Ochiq sahifa: «daftar» uslubi, saboqlar mundarijasi (bazadan), 70/20/10 kalkulyatori, savollar |
| Asosiy | `/asosiy/` | Qolgan pul, daromad, jamg'arma va qarzlar, navbatdagi saboq, yutuqlar |
| Hamyon | `/hamyon/` | Xarajat (11 tur), kirim + foiz kalkulyatori, diagramma, Zarur/Kerak/Havas, tarix (tahrirlash bilan) |
| Qarzlar | `/qarzlar/` | Qarzlar ro'yxati, to'lovlar, progress bar, **qarzdan qutulish** rejasi va qutulish sanasi |
| Saboqlar | `/saboqlar/` | Duolingo uslubidagi yo'lka: bajarilgan — yashil, joriy — sariq, qolganlari qulflangan |
| Saboq | `/saboqlar/<raqam>/` | YouTube video, qisqacha mazmun, **saboqlar** ro'yxati va **nima qilish kerak** (belgilanadigan) |
| Jamg'arma | `/jamgarma/` | Qo'riqchi pul (3–6 oylik xarajat maqsadi bilan) va o'sadigan pul; qo'shish, o'tkazish, olish, tarix |
| Sozlamalar | `/sozlamalar/` | Daromad va foiz, oylik majburiy xarajatlar, qo'riqchi pul necha oylik, eslatmalar, chiqish |
| Haqida | `/haqida/` | Muallif haqida ogohlantirish, loyiha tamoyillari |
| Kirish | `/kirish/` | Veb saytga Telegram bot orqali kirish |

* **Valyuta**: har foydalanuvchida bitta hisob valyutasi — **so'm** yoki **dollar** (butun sonlarda).
  Summalar hech qachon aralashmaydi. Valyuta almashtirilsa, barcha yozuvlar (kirim, xarajat, jamg'arma,
  qarzlar, majburiy xarajatlar, oylik) Markaziy bank kursi bo'yicha bitta tranzaksiyada qayta hisoblanadi.
  **MB kursi** (cbu.uz) bosh sahifada va sozlamalarda ko'rinadi, soatiga bir marta yangilanadi;
  qolgan pulning ikkinchi valyutadagi taxminiy qiymati ham ko'rsatiladi. Admin panelda ham summalar valyuta bo'yicha alohida.
* **Tanishtiruv**: birinchi kirishda — xush kelibsiz → yo'l xaritasi → valyuta tanlash → daromad sozlash.
  Bosh sahifada **«Boshlash yo'li»**: 6 qadam (valyuta, daromad, birinchi xarajat, o'zingizga to'lash,
  qarzlar, 1-saboq), keyingisi ajratib ko'rsatiladi. Sozlamalarda «Tanishtiruvni qayta ko'rish».
* **Daromad sozlamalari**: «Oylik olaman» (summa bir marta kiritiladi, masalan 8 000 000) yoki
  «Oylik olmayman» (faqat haqiqiy kirimlar hisoblanadi). Keyin **necha foizini o'ziga to'lashi** tanlanadi:
  5 / 10 / 15 / 20% (har birining summasi ko'rinadi) yoki 1–50% oralig'idagi istalgan foiz.
  Shu oyda kirim yozilgan bo'lsa, haqiqiy kirim oylik summadan ustun turadi.
* **Jamg'arma ikki qism** (3-saboq): yangi pul «Avtomatik» tanlansa, qo'riqchi pul maqsadga
  (oylik ro'zg'or × 3–6 oy) yetguncha unga, keyin o'sadigan pulga tushadi. Jamg'armadan olingan pul
  shu oyning «qolgan pul»iga qo'shiladi.
* **Oylik majburiy xarajatlar** (ixtiyoriy): ijara, kommunal va h.k. belgilangan kuni avtomatik yoziladi;
  hali tushmaganlari bosh sahifada «erkin pul»dan oldindan ayiriladi.
* **Xarajat turlari**: Oziq-ovqat, Ijara/uy, Kommunal, Yo'lkira, Kiyim-kechak, Sog'liq, Ta'lim,
  Aloqa, To'y-marosim, Sadaqa, Boshqalar. Tarix 20 tadan sahifalanadi va turi bo'yicha filtrlanadi.
* **Bank krediti kalkulyatori**: qarz qo'shishda tur tanlanadi. Kreditda olingan summa, yillik foiz va
  muddat (oy/yil), qancha to'langani (necha oy yoki summa) kiritiladi. Ilova annuitet bo'yicha oylik
  to'lovni, foiz bilan jami summani, ustamani va qoldiqni hisoblaydi. «Har oy qancha qo'shib to'laysiz?»
  (+10/20/30/50% yoki o'z foizi) tanlansa — necha oyda tugashi va qancha pul yutilishi ko'rsatiladi.
  Qo'shimcha to'lov asosiy qarzga ketadi: har to'lovdan keyin qolgan foiz qayta hisoblanadi.
* **Bosh sahifa**: eng tepada «Bu oy qolgan pulingiz» (daromad − xarajat − zaxira) va tezkor
  «− Xarajat» tugmasi. Hamyonda xarajat formasi eng tepada.
* Saboqlar ketma-ket o'tiladi: keyingisi **oldingi saboqning vazifasi bajarilgandagina** ochiladi. Barcha vazifalar belgilanmaguncha
  «Saboqni yakunladim» tugmasi o'chiq; ilovadagi amal (masalan, daromad kiritish) serverda tekshiriladi.
* **Bot**: yangi saboq e'loni (admin'dan), ertalab ochiq saboq eslatmasi (08:00), kechqurun (20:00) —
  agar bugun xarajat kiritilmagan bo'lsa — eslatma. `/eslatma` bilan o'chirish mumkin.
* Har bir sahifa alohida, o'zining kichik JS fayli bilan yuklanadi; ikonlar — bitta SVG sprite.
* **Tahrirlash**: Hamyon tarixida kirim yoki xarajatni bosing — summa, tur, sana, izohni o'zgartirish
  yoki o'chirish mumkin. Qarzlar va majburiy xarajatlar ham tahrirlanadi.

## Admin panel (`/boshqaruv/`)

Faqat staff foydalanuvchilar uchun (`python manage.py createsuperuser` yoki `create_dev_user`).

| Bo'lim | Nima bor |
|---|---|
| Umumiy | Jami / yangi / faol foydalanuvchilar, bot holati, 30 kunlik grafik, eng ko'p amallar, pul oqimi |
| Voronka | Ro'yxatdan o'tish → shartlar → daromad → birinchi xarajat → jamg'arma → 1-saboq → qaytib kelish (7/30/90 kun) |
| Foydalanuvchilar | Qidiruv (ism, @username, Telegram ID), filtrlar, sahifalash |
| Profil | Moliyaviy holat, saboqlar va javoblari, qarzlar, amallar tarixi; hisobni o'chirish/yoqish, eslatmalar, bot orqali xabar, admin izohi |
| Kirishlar | Ro'yxatdan o'tishlar va kirishlar (Mini App / sayt / bot) |
| Amallar | Barcha amallar jurnali (kirim, xarajat, jamg'arma, qarz, saboq, sozlamalar…) |
| Saboqlar | Qo'shish/tahrirlash (YouTube havolasini to'g'ridan-to'g'ri qo'ying), nashr, **E'lon qilish** |
| Xabarlar | Ommaviy xabar (hammaga / 7 kunda faollarga / 7 kundan beri kirmaganlarga), jarayon ko'rsatkichi |

`/admin/` — xom ma'lumotlar bazasi (Django admin) ham qoladi.

## 100 000+ foydalanuvchi uchun

* Barcha asosiy jadvallarda `(user, date)` indekslari; amallar jurnali `(user, vaqt)` va `(amal, vaqt)` bo'yicha.
* Oylik hisoblar shartli agregatsiya bilan bitta so'rovda; saboqlar keshda (saqlanganda avtomatik tozalanadi);
  `last_seen` har so'rovda emas, 5 daqiqada bir yoziladi; admin statistikasi 60 soniya keshlanadi.
* Bot: eslatmalar va ommaviy xabarlar **alohida fon oqimida**, ~25 xabar/soniya, 429 da kutadi.
  Ommaviy xabar navbatda saqlanadi va bot qayta ishga tushsa ham to'xtagan joyidan davom etadi.
* Rate limit: Telegram kirish, login-kod, dev va panel kirishlari (Redis bo'lsa — barcha worker'lar uchun umumiy);
  nginx'da API uchun `limit_req`.
* Production: PostgreSQL + `CONN_MAX_AGE`, Redis kesh (`REDIS_URL`), gunicorn `gthread` (5×4),
  xeshli statik fayllar (`ManifestStaticFilesStorage`) + nginx 30 kunlik kesh va gzip.

## Kirish (autentifikatsiya)

* **Mini App ichida** — avtomatik: Telegram `initData` imzosi serverda `BOT_TOKEN` bilan tekshiriladi.
* **Veb saytda** — «Telegram orqali kirish» → bot ochiladi → «✅ Ha, saytga kiraman» → sayt o'zi kiradi.
  Parol yo'q. Bir martalik kod 10 daqiqa amal qiladi.
* **Dasturchi kirishi (login/parol)** — `/kirish/` sahifasida, faqat `DEV_LOGIN=True` bo'lganda ko'rinadi.
  `.env` dagi `DEV_USERNAME` / `DEV_PASSWORD` ni yozing va `python manage.py create_dev_user` ni ishga
  tushiring — shu login `/admin/` uchun ham ishlaydi. Productionda `DEV_LOGIN=False` qiling.
* API `Authorization: Bearer <token>` bilan ishlaydi (cookie emas), shuning uchun Telegram Web
  (iframe) ichida ham muammosiz ishlaydi.

## Tuzilma

```
config/            Django sozlamalari
core/              modellar, API (api.py), biznes mantiq (services.py), jurnal (activity.py), saboqlar (saboq_data.py)
bot/               Telegram bot: handlers.py, reminders.py (eslatmalar + ommaviy xabarlar navbati), runbot
panel/             admin panel (/boshqaruv/): views.py, forms.py
templates/         landing.html, base.html, pages/*.html, panel/*.html, partials/icons.html (SVG ikonlar)
static/            css (app, landing, panel), js (common.js + har sahifa uchun alohida fayl)
deploy/            nginx va systemd fayllari
```

## Lokal ishga tushirish (Windows)

```bash
python -m venv .venv
```
```bash
.venv\Scripts\pip install -r requirements.txt
```
```bash
copy .env.example .env
```
`.env` ichida `SECRET_KEY`, `BOT_TOKEN`, `BOT_USERNAME` ni to'ldiring (`DB_ENGINE` bo'sh bo'lsa SQLite ishlatiladi).

```bash
.venv\Scripts\python manage.py migrate
```
```bash
.venv\Scripts\python manage.py createsuperuser
```
```bash
.venv\Scripts\python manage.py runserver
```
Boshqa terminalda bot:
```bash
.venv\Scripts\python manage.py runbot
```

Mini App tugmasi faqat **HTTPS** manzil bilan ishlaydi. Lokal sinov uchun `ngrok http 8000` kabi
tunnel manzilini `WEBAPP_URL` ga yozing (va `ALLOWED_HOSTS` ga qo'shing).

Testlar:
```bash
.venv\Scripts\python manage.py test
```

## Saboqlarni qo'shish (har hafta yangi video)

Ikki yo'l bor:

1. **Admin panel**: `/boshqaruv/saboqlar/` → «+ Yangi saboq». Raqam, mavzu, YouTube havolasi,
   qisqacha mazmun, **Saboqlar** va **Nima qilish kerak** (har biri alohida qatorda), ilovadagi amal turi.
   Saqlagach **E'lon qilish** — bot hammaga fon rejimida xabar yuboradi.
2. **Fayl orqali**: `core/saboq_data.py` dagi `SABOQLAR` ro'yxatiga qo'shing va ishga tushiring:
   ```bash
   .venv\Scripts\python manage.py load_saboqlar
   ```

Video kiritilmagan saboqda kanalning videolar sahifasi havolasi ko'rsatiladi.

## VPS ga joylash (Ubuntu)

1. Paketlar: `sudo apt install python3-venv postgresql redis-server nginx certbot python3-certbot-nginx`
2. PostgreSQL:
   ```bash
   sudo -u postgres psql -c "CREATE USER baraka WITH PASSWORD 'kuchli-parol';"
   ```
   ```bash
   sudo -u postgres psql -c "CREATE DATABASE baraka OWNER baraka;"
   ```
3. Loyihani `/srv/baraka` ga joylang, `.venv` yarating, `pip install -r requirements.txt`.
4. `.env`: `DEBUG=False`, uzun tasodifiy `SECRET_KEY` (50+ belgi), `DB_ENGINE=postgres`, `POSTGRES_*`,
   `REDIS_URL=redis://127.0.0.1:6379/1`, `ALLOWED_HOSTS=baraka.example.uz`,
   `CSRF_TRUSTED_ORIGINS=https://baraka.example.uz`, `WEBAPP_URL=https://baraka.example.uz/`, `DEV_LOGIN=False`;
   SSL ulangach `SSL_REDIRECT=True` va `HSTS_SECONDS=31536000`.
5. `python manage.py migrate`, `python manage.py load_saboqlar` va `python manage.py collectstatic --noinput`
6. `deploy/baraka-web.service`, `deploy/baraka-bot.service` → `/etc/systemd/system/`, so'ng
   `sudo systemctl enable --now baraka-web baraka-bot`
7. `deploy/nginx.conf` → `/etc/nginx/sites-available/baraka`, yoqing va `sudo nginx -t && sudo systemctl reload nginx`
8. SSL: `sudo certbot --nginx -d baraka.example.uz`
9. @BotFather → Bot Settings → Configure Mini App: `https://baraka.example.uz/asosiy/`
   (bot ishga tushganda menyu tugmasini o'zi ham `/asosiy/` ga o'rnatadi; `/` — ochiq landing sahifa).

Eslatmalar `runbot` jarayoni ichida yuboriladi. Xohlasangiz crontab orqali ham mumkin:
```
0 8 * * *  cd /srv/baraka && .venv/bin/python manage.py send_reminders morning
0 20 * * * cd /srv/baraka && .venv/bin/python manage.py send_reminders evening
```
(bunda `runbot --no-reminders` bilan ishga tushiring; server vaqt zonasi Toshkent bo'lishi kerak).
