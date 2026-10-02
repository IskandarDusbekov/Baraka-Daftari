/* Elektron Baraka Daftari — barcha sahifalar uchun umumiy kod (window.B) */
(() => {
  'use strict';

  const tg = window.Telegram && window.Telegram.WebApp;
  const IN_TG = !!(tg && tg.initData);
  const CFG = window.BARAKA || {};
  const BOT_LINK = CFG.botUsername ? `https://t.me/${CFG.botUsername}` : '';
  const TOKEN_KEY = 'baraka_token';
  const UID_KEY = 'baraka_tg_uid';
  const $sheetRoot = document.getElementById('sheet-root');

  const MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'];
  const DISCLAIMER = "Ushbu loyiha Abdukarim Mirzayevning «Baraka Daftari» ko'rsatuvidan ilhomlangan holda, " +
    'insonlarga qulaylik yaratish maqsadida ishlab chiqildi. Bu rasmiy loyiha emas.';

  // ------------------------------------------------------------------ utils
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* private mode */ } },
  };
  let token = store.get(TOKEN_KEY);

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (n) => Math.round(Number(n) || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const digits = (s) => String(s || '').replace(/\D/g, '');
  // Qisqa ko'rinish, lekin chalg'itmaydigan aniqlikda: 1 500 -> "1.5 ming", 8 450 000 -> "8.45 mln"
  const compactNum = (n) => {
    const a = Math.abs(n);
    if (a >= 1e9) return `${+(n / 1e9).toFixed(2)} mlrd`;
    if (a >= 1e6) return `${+(n / 1e6).toFixed(a < 1e7 ? 2 : 1)} mln`;
    if (a >= 1e3) return `${+(n / 1e3).toFixed(a < 1e5 ? 1 : 0)} ming`;
    return String(Math.round(n));
  };

  // ------------------------------------------------------------------ valyuta
  // Hisob valyutasi foydalanuvchida bitta: UZS yoki USD. Barcha summalar shu valyutada.
  const CUR_KEY = 'baraka_currency';
  const CURRENCIES = {
    UZS: { label: "So'm", sign: "so'm", ph: { big: '8 000 000', mid: '500 000', small: '50 000' } },
    USD: { label: 'Dollar', sign: '$', ph: { big: '800', mid: '50', small: '5' } },
  };
  let currency = CURRENCIES[store.get(CUR_KEY)] ? store.get(CUR_KEY) : 'UZS';
  const applyCurrency = () => {
    document.documentElement.style.setProperty('--cur', `"${CURRENCIES[currency].sign}"`);
    document.documentElement.dataset.cur = currency;
  };
  applyCurrency();
  function setCurrency(c) {
    if (!CURRENCIES[c] || c === currency) return;
    currency = c;
    store.set(CUR_KEY, c);
    applyCurrency();
  }
  /** Summa + valyuta: "8 000 000 so'm" yoki "$800" */
  const som = (n) => (currency === 'USD' ? `${n < 0 ? '−' : ''}$${num(Math.abs(n))}` : `${num(n)} so'm`);
  // Dollar summalari kichik — million'gacha to'liq ko'rsatiladi ($1 500), so'm esa qisqartiriladi (1.5 mln)
  const compact = (n) => {
    if (currency !== 'USD') return compactNum(n);
    const sign = n < 0 ? '−' : '';
    return Math.abs(n) < 1e6 ? `${sign}$${num(Math.abs(n))}` : `${sign}$${compactNum(Math.abs(n))}`;
  };
  const curSign = () => CURRENCIES[currency].sign;
  const ph = (size = 'mid') => CURRENCIES[currency].ph[size];
  /** Ikkinchi valyutadagi taxminiy qiymat (faqat ko'rsatish uchun) */
  function otherCurrency(n, rate) {
    if (!rate || !rate.rate) return '';
    return currency === 'USD'
      ? `≈ ${num(n * rate.rate)} so'm`
      : `≈ $${num(n / rate.rate)}`;
  }
  const pad = (n) => String(n).padStart(2, '0');
  const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const monthKey = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
  const monthLabel = (key) => { const [y, m] = key.split('-').map(Number); return `${MONTHS[m - 1]} ${y}`; };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /** SVG sprite ikonkasi: ic('home') */
  const ic = (name, cls = '') => `<svg class="ic ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  function haptic(type) {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else tg.HapticFeedback.notificationOccurred(type);
    } catch (e) { /* eski klient */ }
  }

  // ------------------------------------------------------------------ API
  class ApiError extends Error {
    constructor(message, status, data) { super(message); this.status = status; this.data = data || {}; }
  }

  async function api(path, { method = 'GET', body } = {}) {
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;
    let res;
    try {
      res = await fetch(`/api/${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      throw new ApiError('Internet aloqasini tekshiring', 0);
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* bo'sh javob */ }
    if (res.status === 401 && token && !path.startsWith('auth/')) {
      logout();
      throw new ApiError(data.error || 'Qaytadan kiring', 401, data);
    }
    if (!res.ok) throw new ApiError(data.error || 'Xatolik yuz berdi', res.status, data);
    if (data.user && data.user.currency) setCurrency(data.user.currency); // valyuta har doim serverdagidek
    return data;
  }

  function setToken(t, uid) {
    token = t;
    store.set(TOKEN_KEY, t);
    if (uid) store.set(UID_KEY, String(uid));
  }

  function logout() {
    token = null;
    store.del(TOKEN_KEY);
    store.del(UID_KEY);
    location.replace(IN_TG ? '/asosiy/' : '/');
  }

  // ------------------------------------------------------------------ toast
  let toastTimer;
  function toast(msg, isError) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.toggle('error', !!isError);
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
    if (isError) haptic('error');
  }

  // ------------------------------------------------------------------ pastki oyna (sheet)
  let sheetOnClose = null;
  const isHome = CFG.page === 'asosiy' || CFG.page === 'kirish';

  function syncBackButton() {
    if (!tg || !tg.BackButton) return;
    if ($sheetRoot.classList.contains('open') || !isHome) tg.BackButton.show();
    else tg.BackButton.hide();
  }

  function openSheet(html, onClose) {
    $sheetRoot.innerHTML = `
      <div class="sheet-backdrop" data-close></div>
      <div class="sheet" role="dialog" aria-modal="true">
        <div class="sheet-handle"></div>
        <button class="sheet-close" data-close aria-label="Yopish">${ic('x')}</button>
        <div class="sheet-body">${html}</div>
      </div>`;
    sheetOnClose = onClose || null;
    $sheetRoot.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', () => closeSheet()));
    requestAnimationFrame(() => $sheetRoot.classList.add('open'));
    syncBackButton();
    return $sheetRoot.querySelector('.sheet-body');
  }

  function setSheet(html) {
    const body = $sheetRoot.querySelector('.sheet-body');
    if (body) body.innerHTML = html;
    return body;
  }

  function onSheetClose(cb) { sheetOnClose = cb; }

  function closeSheet(silent) {
    if (!$sheetRoot.classList.contains('open')) return;
    $sheetRoot.classList.remove('open');
    const cb = sheetOnClose;
    sheetOnClose = null;
    setTimeout(() => { if (!$sheetRoot.classList.contains('open')) $sheetRoot.innerHTML = ''; }, 300);
    syncBackButton();
    if (cb && !silent) cb();
  }

  // ------------------------------------------------------------------ menyu (pastki paneldagi 5-tugma)
  const MENU = [
    ['/hisobot/', 'chart', 'blue', 'Hisobot', '7 kunlik, 10 kunlik, oylik umumiy hisob'],
    ['/jamgarma/', 'safe', 'green', "Jamg'arma", "Qo'riqchi va o'sadigan pul"],
    ['/kalkulyator/', 'calc', 'blue', 'Kalkulyatorlar', "Kredit, qarz, narxlar"],
    ['/sozlamalar/', 'gear', 'purple', 'Sozlamalar', 'Valyuta, daromad, eslatmalar'],
    ['/haqida/', 'info', 'orange', 'Loyiha haqida', 'Abdukarim Mirzayev saboqlari'],
    ['/aloqa/', 'chat', 'gray', "Biz bilan bog'lanish", 'Savol, taklif yoki xato'],
  ];

  function menuSheet() {
    const here = location.pathname;
    const body = openSheet(`
      <h2>Menyu</h2>
      <nav class="menu-grid">${MENU.map(([href, icon, color, title, hint]) => `
        <a href="${href}" class="menu-item ${here === href ? 'on' : ''}">
          <span class="h-ico ${color}">${ic(icon)}</span><span><b>${title}</b><small>${hint}</small></span></a>`).join('')}
        <button type="button" class="menu-item" id="menu-rate"><span class="h-ico gold">${ic('star')}</span><span><b>Baho berish</b><small>Ilova sizga yoqdimi?</small></span></button>
      </nav>`);
    body.querySelector('#menu-rate').onclick = () => { closeSheet(true); setTimeout(() => ratingModal(), 250); };
    // Hozirgi sahifa tanlansa — shunchaki menyuni yopamiz
    body.querySelectorAll('a.menu-item').forEach((a) => {
      a.addEventListener('click', (e) => { if (a.pathname === here) { e.preventDefault(); closeSheet(true); } });
    });
  }
  const $menuBtn = document.getElementById('menu-btn');
  if ($menuBtn) $menuBtn.addEventListener('click', (e) => { e.preventDefault(); haptic('light'); menuSheet(); });

  if (tg && tg.BackButton) {
    tg.BackButton.onClick(() => {
      if ($sheetRoot.classList.contains('open')) closeSheet();
      else if (history.length > 1) history.back();
      else location.href = '/asosiy/';
    });
  }

  function celebrate(iconName, title, text, extra = '') {
    return `<div class="celebrate"><div class="big-ico">${ic(iconName)}</div>
      <h2>${title}</h2>${text ? `<p class="muted mt">${text}</p>` : ''}</div>${extra}`;
  }

  // ------------------------------------------------------------------ markaziy oyna (modal)
  let modalOpen = false;

  /** Ekran markazidagi oyna. Varaq (sheet) ustida ham ochiladi. Yopilganda onClose(qiymat). */
  function openModal(html, { onClose, dismissible = true } = {}) {
    const root = document.createElement('div');
    root.className = 'modal-root';
    root.innerHTML = `<div class="modal-backdrop" ${dismissible ? 'data-mclose' : ''}></div>
      <div class="modal" role="dialog" aria-modal="true">${html}</div>`;
    document.body.appendChild(root);
    modalOpen = true;
    let done = false;
    const close = (value) => {
      if (done) return;
      done = true;
      modalOpen = false;
      document.removeEventListener('keydown', onKey);
      root.classList.remove('open');
      setTimeout(() => root.remove(), 200);
      if (onClose) onClose(value);
    };
    const onKey = (e) => { if (e.key === 'Escape' && dismissible) close(false); };
    document.addEventListener('keydown', onKey);
    root.querySelectorAll('[data-mclose]').forEach((el) => el.addEventListener('click', () => close(false)));
    requestAnimationFrame(() => root.classList.add('open'));
    return { el: root.querySelector('.modal'), close };
  }

  /**
   * Tasdiqlash oynasi: o'chirish, chiqish va boshqa qaytarib bo'lmaydigan amallar oldidan.
   * confirmAsk("Yozuvni o'chirasizmi?", { danger: true, ok: "O'chirish" })
   */
  function confirmAsk(text, { title = 'Tasdiqlang', ok = 'Ha', cancel = 'Bekor qilish', danger = false } = {}) {
    return new Promise((resolve) => {
      const m = openModal(`
        <div class="modal-ico ${danger ? 'danger' : ''}">${ic(danger ? 'trash' : 'alert')}</div>
        <h3>${esc(title)}</h3>
        <p class="muted">${esc(text)}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" data-mclose>${esc(cancel)}</button>
          <button type="button" class="btn ${danger ? 'danger' : ''}" data-ok>${esc(ok)}</button>
        </div>`, { onClose: (v) => resolve(!!v) });
      haptic('light');
      m.el.querySelector('[data-ok]').onclick = () => { haptic(danger ? 'warning' : 'light'); m.close(true); };
      setTimeout(() => m.el.querySelector('[data-ok]').focus(), 50);
    });
  }

  // ------------------------------------------------------------------ baho so'rash
  const STAR_WORDS = ['', 'Yoqmadi', 'Qoniqarsiz', "O'rtacha", 'Yaxshi', "Zo'r!"];

  /** Baho oynasi. auto=true — tizim o'zi so'raganda (server "ko'rsatildi" deb belgilaydi). */
  function ratingModal({ auto = false } = {}) {
    let rating = 0;
    if (auto) api('feedback/shown', { method: 'POST', body: {} }).catch(() => {});
    const m = openModal(`
      <div class="modal-ico star">${ic('star')}</div>
      <h3>Baraka Daftari sizga yoqyaptimi?</h3>
      <p class="muted">Bahoyingiz ilovani yaxshilashga yordam beradi. Bu 5 soniya oladi.</p>
      <div class="stars-pick" role="radiogroup" aria-label="Baho">
        ${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-star="${n}" role="radio" aria-label="${n} yulduz">${ic('star')}</button>`).join('')}
      </div>
      <p class="star-word" id="rt-word">&nbsp;</p>
      <label class="field" id="rt-comment-wrap" hidden><span id="rt-q">Nimani yaxshilashimiz kerak?</span>
        <textarea class="input" id="rt-comment" rows="3" maxlength="1000" placeholder="Ixtiyoriy"></textarea></label>
      <div class="modal-actions">
        <button type="button" class="btn ghost" data-mclose>Keyinroq</button>
        <button type="button" class="btn" id="rt-send" disabled>Yuborish</button>
      </div>`);
    const el = m.el;
    const paint = (n) => el.querySelectorAll('[data-star]').forEach((b) => b.classList.toggle('on', Number(b.dataset.star) <= n));
    el.querySelectorAll('[data-star]').forEach((b) => {
      b.onmouseenter = () => paint(Number(b.dataset.star));
      b.onmouseleave = () => paint(rating);
      b.onclick = () => {
        rating = Number(b.dataset.star);
        paint(rating);
        haptic('light');
        el.querySelector('#rt-word').textContent = STAR_WORDS[rating];
        el.querySelector('#rt-comment-wrap').hidden = false;
        el.querySelector('#rt-q').textContent = rating >= 4 ? 'Nimasi ayniqsa yoqdi?' : 'Nimani yaxshilashimiz kerak?';
        el.querySelector('#rt-send').disabled = false;
      };
    });
    el.querySelector('#rt-send').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      try {
        await api('feedback', { method: 'POST', body: {
          rating, comment: el.querySelector('#rt-comment').value, page: CFG.page || '',
        } });
        haptic('success');
        const share = BOT_LINK ? `https://t.me/share/url?url=${encodeURIComponent(BOT_LINK)}&text=${encodeURIComponent("Pulimni shu daftarda yozib boryapman — sizga ham foydali bo'ladi")}` : '';
        el.innerHTML = `
          <div class="modal-ico green">${ic('check-circle')}</div>
          <h3>Rahmat!</h3>
          <p class="muted">${rating >= 4 ? "Xursandmiz! Ilova foydali bo'lsa, do'stlaringizga ham ulashing — ularga ham baraka bo'lsin." : "Fikringizni o'qib chiqamiz va ilovani yaxshilaymiz."}</p>
          <div class="modal-actions ${share && rating >= 4 ? '' : 'one'}">
            ${share && rating >= 4 ? `<a class="btn ghost" href="${share}" target="_blank" rel="noopener">${ic('send')} Ulashish</a>` : ''}
            <button type="button" class="btn" id="rt-close">Yopish</button>
          </div>`;
        el.querySelector('#rt-close').onclick = () => m.close(true);
      } catch (e) { toast(e.message, true); }
    });
  }

  /** Bosh sahifa ma'lumoti kelganda: server "so'rash vaqti keldi" desa, biroz kutib baho oynasini ochadi. */
  function maybeAskRating(data) {
    if (!data || !data.ask_rating || store.get('baraka_rate_asked') === todayISO()) return;
    setTimeout(() => {
      // Foydalanuvchi boshqa ish bilan band bo'lsa (varaq yoki oyna ochiq) — bezovta qilmaymiz
      if (modalOpen || $sheetRoot.classList.contains('open') || document.hidden) return;
      store.set('baraka_rate_asked', todayISO());
      ratingModal({ auto: true });
    }, 2500);
  }

  // ------------------------------------------------------------------ formalar
  /** Summa maydoni: yozilganda "1 000 000" ko'rinishida formatlanadi */
  function bindMoney(input, onChange) {
    const fmt = () => {
      const d = digits(input.value).replace(/^0+(?=\d)/, '').slice(0, 13);
      input.value = d ? num(d) : '';
      if (onChange) onChange(d ? Number(d) : 0);
    };
    input.addEventListener('input', fmt);
    fmt();
    return () => Number(digits(input.value)) || 0;
  }

  async function withBusy(btn, fn) {
    if (btn.disabled) return;
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner sm"></span>';
    try { await fn(); } finally { if (btn.isConnected) { btn.disabled = false; btn.innerHTML = html; } }
  }

  function animateBars(root = document) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      root.querySelectorAll('[data-w]').forEach((el) => { el.style.width = `${Math.min(100, el.dataset.w)}%`; });
    }));
  }

  // ------------------------------------------------------------------ konfetti
  function confetti(amount = 140) {
    const canvas = document.getElementById('confetti');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
    ctx.scale(dpr, dpr);
    const colors = ['#22c55e', '#f59e0b', '#3b82f6', '#ef4444', '#a855f7', '#14b8a6'];
    const parts = Array.from({ length: amount }, () => ({
      x: innerWidth / 2 + (Math.random() - 0.5) * 80,
      y: innerHeight * 0.35,
      vx: (Math.random() - 0.5) * 14,
      vy: -Math.random() * 13 - 4,
      s: Math.random() * 7 + 5,
      r: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3,
      c: colors[Math.floor(Math.random() * colors.length)],
    }));
    const start = performance.now();
    haptic('success');
    (function frame(t) {
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      parts.forEach((p) => {
        p.vy += 0.35; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r);
        ctx.fillStyle = p.c; ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2);
        ctx.restore();
      });
      if (t - start < 2600) requestAnimationFrame(frame);
      else ctx.clearRect(0, 0, innerWidth, innerHeight);
    })(start);
  }

  // ------------------------------------------------------------------ sahifa
  const $page = document.getElementById('page');

  function render(html) {
    $page.innerHTML = html;
    animateBars($page);
    return $page;
  }

  function errorView(e, retry) {
    render(`<div class="card empty"><span class="e-ico">${ic('alert')}</span><p>${esc(e.message)}</p>
      <button class="btn mt" id="retry">Qayta urinish</button></div>`);
    document.getElementById('retry').onclick = retry || (() => location.reload());
  }

  const disclaimerHtml = () => `<section class="disclaimer"><div class="d-title">${ic('alert')} Muhim ma'lumot</div>${esc(DISCLAIMER)}</section>`;

  /** Telegram'ni sozlaydi, foydalanuvchini tanitadi va sahifa funksiyasini ishga tushiradi. */
  /** isPublic: sahifa kirmagan mehmonlarga ham ochiq (masalan, kalkulyatorlar) */
  async function ready(main, { isPublic = false } = {}) {
    if (tg) {
      try {
        tg.ready();
        tg.expand();
        tg.setHeaderColor('#f4f7fb');
        tg.setBackgroundColor('#f4f7fb');
        if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
      } catch (e) { /* eski klient */ }
      syncBackButton();
    }

    if (IN_TG) {
      const tgUser = tg.initDataUnsafe && tg.initDataUnsafe.user;
      const sameUser = tgUser && store.get(UID_KEY) === String(tgUser.id);
      if (!token || !sameUser) {
        try {
          const r = await api('auth/telegram', { method: 'POST', body: { init_data: tg.initData } });
          setToken(r.token, r.user.tg_id);
        } catch (e) {
          if (!isPublic) { errorView(e); return; }
        }
      }
    }

    // Mehmon (kirmagan) — ochiq sahifada ilova bo'limlari (menyu, saboqlar, hamyon…) ko'rinmaydi
    if (!token && isPublic) {
      document.body.classList.add('guest');
      const brand = document.querySelector('.topbar .brand');
      if (brand) brand.href = '/';
    }

    if (!token && !isPublic) {
      location.replace(`/kirish/?next=${encodeURIComponent(location.pathname)}`);
      return;
    }

    const run = () => Promise.resolve().then(main).catch((e) => { if (e.status !== 401) errorView(e, run); });
    run();
  }

  /** "O'zingga to'la" — zaxiraga o'tkazish oynasi (Asosiy va Hamyon sahifalarida) */
  function saveSheet(amount, incomeId, incomeAmount, after) {
    const body = openSheet(`
      <div class="celebrate"><div class="big-ico green">${ic('safe')}</div></div>
      ${incomeAmount ? `<h2 class="center">Siz o'zingizga ${som(amount)} to'lashingiz kerak</h2>
        <p class="center muted">Daromadingiz ${som(incomeAmount)}. Xarajatdan oldin shu qismini jamg'armaga ajrating —
          avval o'zingizga to'lang. Summani o'zgartirishingiz mumkin.</p>`
        : `<h2 class="center">O'zingizga to'lang</h2>
        <p class="center muted">Zaxiraga o'tkaziladigan summa:</p>`}
      <label class="field money"><input class="input" id="save-amt" inputmode="numeric" autocomplete="off"></label>
      <div>
        <span class="field-label">Qayerga?</span>
        <div class="seg three">
          <button type="button" data-bucket="auto" class="active">${ic('sparkles')} Avtomatik</button>
          ${Object.entries(BUCKETS).map(([k, b]) => `<button type="button" data-bucket="${k}">${ic(b.icon)} ${b.label.split(' ')[0]}</button>`).join('')}
        </div>
        <p class="muted small mt">Avtomatik: qo'riqchi pul maqsadga yetguncha unga, keyin o'sadigan pulga.</p>
      </div>
      <button class="btn big" id="save-go">${ic('check')} Tasdiqlayman — jamg'armaga o'tkazdim</button>
      <button class="btn ghost block" id="save-later">Keyinroq</button>`, after);
    body.querySelector('#save-later').onclick = () => closeSheet();
    const input = body.querySelector('#save-amt');
    input.value = amount;
    const val = bindMoney(input);
    let bucket = 'auto';
    body.querySelectorAll('[data-bucket]').forEach((b) => {
      b.onclick = () => {
        bucket = b.dataset.bucket;
        body.querySelectorAll('[data-bucket]').forEach((x) => x.classList.toggle('active', x === b));
        haptic('light');
      };
    });
    body.querySelector('#save-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const sum = val();
      if (!sum) { toast('Summani kiriting', true); return; }
      try {
        const r = await api('savings', { method: 'POST', body: { amount: sum, income_id: incomeId, bucket } });
        const target = BUCKETS[r.saving.bucket];
        confetti();
        setSheet(celebrate('sparkles', 'Barakalla!', `O'zingiz uchun yana <b>${som(sum)}</b> jamg'ardingiz — <b>${target.label.toLowerCase()}</b>ga.`,
          `<div class="treasure">${ic('safe')}<span>Umumiy jamg'arma</span><b>${som(r.reserve_total)}</b>
             <small>Qo'riqchi: ${som(r.savings.guard)} · O'sadigan: ${som(r.savings.grow)}</small></div>
           <button class="btn big" id="save-done">Davom etish</button>`))
          .querySelector('#save-done').onclick = () => closeSheet();
      } catch (e) { toast(e.message, true); }
    });
  }

  const PERCENTS = [5, 10, 15, 20];
  const part = (amount, percent) => Math.floor((amount * percent) / 100);

  /**
   * Daromad sozlamalari: oylik olaman / olmayman + necha foizini o'ziga to'lashi.
   * user: { income_type, monthly_income, save_percent }
   */
  function incomeSetupSheet(user, after) {
    let type = user.income_type || 'salary';
    let percent = user.save_percent || 10;
    const custom = !PERCENTS.includes(percent);

    const body = openSheet(`
      <h2>Daromad sozlamalari</h2>
      <div class="seg" role="tablist">
        <button type="button" data-type="salary">${ic('calendar')} Oylik olaman</button>
        <button type="button" data-type="irregular">${ic('coins')} Oylik olmayman</button>
      </div>
      <div id="is-salary">
        <label class="field"><span>Oyiga taxminan qancha olasiz?</span>
          <div class="money"><input class="input" id="is-amt" inputmode="numeric" placeholder="${ph('big')}" autocomplete="off"></div></label>
      </div>
      <p class="tip" id="is-irregular">${ic('bulb')} Daromadingiz o'zgaruvchan bo'lsa ham bo'ladi: pul tushganda Hamyonga
        kirim yozasiz — tanlagan foizingiz har bir kirimdan avtomatik hisoblanadi.</p>

      <div>
        <h3 class="sub-title">${ic('safe')} Daromadingizdan necha foizini o'zingizga to'laysiz?</h3>
        <div class="pct-grid">
          ${PERCENTS.map((p) => `<button type="button" class="pct" data-p="${p}"><b>${p}%</b><small data-amt="${p}"></small></button>`).join('')}
          <button type="button" class="pct" data-p="custom"><b>Boshqa</b><small>foiz</small></button>
        </div>
        <label class="field mt" id="is-custom-wrap" ${custom ? '' : 'hidden'}><span>O'z foizingiz (1–50)</span>
          <div class="money pct-input"><input class="input" id="is-custom" inputmode="numeric" maxlength="2" value="${custom ? percent : ''}" placeholder="12"></div></label>
      </div>

      <div class="calc-result" id="is-calc" hidden>
        <div><span id="is-self-label">O'zingizga</span><b id="is-self">0</b></div>
        <div class="rest"><span>Qolgani</span><b id="is-rest">0</b></div>
      </div>
      <p class="muted small" id="is-note"></p>
      <button class="btn big" id="is-save">${ic('check')} Saqlash</button>`, after);

    const amtInput = body.querySelector('#is-amt');
    if (user.monthly_income) amtInput.value = user.monthly_income;
    const customInput = body.querySelector('#is-custom');

    const refresh = () => {
      const amount = Number(digits(amtInput.value)) || 0;
      body.querySelectorAll('[data-type]').forEach((b) => b.classList.toggle('active', b.dataset.type === type));
      body.querySelector('#is-salary').hidden = type !== 'salary';
      body.querySelector('#is-irregular').hidden = type !== 'irregular';
      const isCustom = !PERCENTS.includes(percent) || !body.querySelector('#is-custom-wrap').hidden;
      body.querySelectorAll('[data-p]').forEach((b) => {
        b.classList.toggle('active', b.dataset.p === 'custom' ? isCustom : !isCustom && Number(b.dataset.p) === percent);
      });
      // Summalar faqat oylik kiritilgandan keyin ko'rinadi — o'ylab topilgan namuna ko'rsatilmaydi
      const known = type === 'salary' && amount > 0;
      body.querySelectorAll('[data-amt]').forEach((s) => {
        s.textContent = known ? compactMoney(part(amount, Number(s.dataset.amt))) : '';
      });
      body.querySelector('#is-calc').hidden = !known;
      if (known) {
        body.querySelector('#is-self-label').textContent = `O'zingizga har oy (${percent}%)`;
        body.querySelector('#is-self').textContent = som(part(amount, percent));
        body.querySelector('#is-rest').textContent = som(amount - part(amount, percent));
      }
      body.querySelector('#is-note').textContent = type === 'irregular'
        ? `Har bir kirimdan ${percent}% o'zingizga ajratiladi — summa kirim yozilganda hisoblanadi.`
        : (known ? '' : 'Oylik summasini yozing — har bir foiz qancha bo\'lishi shu yerda ko\'rinadi.');
    };

    bindMoney(amtInput, refresh);
    body.querySelectorAll('[data-type]').forEach((b) => { b.onclick = () => { type = b.dataset.type; haptic('light'); refresh(); }; });
    body.querySelectorAll('[data-p]').forEach((b) => {
      b.onclick = () => {
        const wrap = body.querySelector('#is-custom-wrap');
        if (b.dataset.p === 'custom') {
          wrap.hidden = false;
          customInput.focus();
          percent = Number(customInput.value) || percent;
        } else {
          wrap.hidden = true;
          percent = Number(b.dataset.p);
        }
        haptic('light');
        refresh();
      };
    });
    customInput.addEventListener('input', () => {
      customInput.value = digits(customInput.value).slice(0, 2);
      const v = Number(customInput.value);
      if (v >= 1 && v <= 50) { percent = v; refresh(); }
    });
    refresh();

    body.querySelector('#is-save').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const amount = Number(digits(amtInput.value)) || 0;
      if (type === 'salary' && !amount) { toast('Oylik summangizni kiriting', true); return; }
      if (!(percent >= 1 && percent <= 50)) { toast('Foiz 1 dan 50 gacha bo\'lishi kerak', true); return; }
      try {
        const r = await api('me', { method: 'POST', body: {
          income_type: type, monthly_income: type === 'salary' ? amount : 0, save_percent: percent,
        } });
        haptic('success');
        // Oylik kiritildi — darhol so'raymiz: bu oy o'zingizga to'lash kerak bo'lgan summa (hali to'lanmagan qismi)
        const need = r.month ? Math.max(0, r.month.should_save - r.month.saved) : 0;
        if (type === 'salary' && need > 0) {
          closeSheet(true);
          setTimeout(() => saveSheet(need, null, amount, after), 320);
          return;
        }
        closeSheet();
        toast(type === 'salary'
          ? `Har oy o'zingizga: ${som(part(amount, percent))}`
          : `Har bir kirimdan ${percent}% o'zingizga`);
      } catch (e) { toast(e.message, true); }
    });
  }

  // ------------------------------------------------------------------ xarajat
  // Ro'zg'or xarajatlari turlari (serverdagi Expense.CATEGORIES bilan bir xil)
  const CATS = {
    food: { label: 'Oziq-ovqat', icon: 'cart', color: '#22c55e' },
    rent: { label: 'Ijara / uy', icon: 'home2', color: '#0ea5e9' },
    utility: { label: 'Kommunal', icon: 'bulb', color: '#f59e0b' },
    transport: { label: "Yo'lkira", icon: 'bus', color: '#3b82f6' },
    clothes: { label: 'Kiyim-kechak', icon: 'shirt', color: '#ec4899' },
    health: { label: "Sog'liq", icon: 'heart', color: '#ef4444' },
    education: { label: "Ta'lim", icon: 'cap', color: '#6366f1' },
    phone: { label: 'Aloqa', icon: 'phone', color: '#14b8a6' },
    events: { label: "To'y-marosim", icon: 'gift', color: '#d946ef' },
    charity: { label: 'Sadaqa', icon: 'hand', color: '#84cc16' },
    shopping: { label: 'Xaridlar', icon: 'bag', color: '#f97316' },
    other: { label: 'Boshqalar', icon: 'box', color: '#94a3b8' },
  };

  // 3-saboq: jamg'arma ikki qism
  const BUCKETS = {
    guard: { label: "Qo'riqchi pul", icon: 'shield', color: '#0ea5e9', hint: "og'ir kun uchun" },
    grow: { label: "O'sadigan pul", icon: 'sprout', color: '#16a34a', hint: 'ishlaydigan pul' },
  };

  // 2-saboq: "Zarur — Kerak — Havas"
  const NEEDS = {
    zarur: { label: 'Zarur', hint: "usiz bo'lmaydi", color: '#16a34a' },
    kerak: { label: 'Kerak', hint: 'foydali', color: '#2563eb' },
    havas: { label: 'Havas', hint: "ko'ngil xohishi", color: '#ea580c' },
  };

  /** Xarajat formasi HTML'i (Hamyon sahifasida ham, tezkor oynada ham bir xil) */
  function expenseFormHtml(defaultDate) {
    return `
      <div class="cats">
        ${Object.entries(CATS).map(([k, c], i) => `<button type="button" class="cat ${i === 0 ? 'active' : ''}" data-cat="${k}" style="--c:${c.color}">${ic(c.icon, 'ci')}${c.label}</button>`).join('')}
      </div>
      <label class="field money mt"><input class="input" data-exp="amount" inputmode="numeric" placeholder="${ph('small')}" autocomplete="off"></label>
      <div class="mt">
        <span class="field-label">Bu xarajat qanday?</span>
        <div class="needs">${Object.entries(NEEDS).map(([k, n]) => `
          <button type="button" class="need need-${k}" data-need="${k}"><b>${n.label}</b><small>${n.hint}</small></button>`).join('')}
        </div>
      </div>
      <div class="form-grid mt">
        <label class="field"><span>Izoh (ixtiyoriy)</span><input class="input" data-exp="note" maxlength="200" placeholder="Masalan: non, sut"></label>
        <label class="field"><span>Sana</span><input class="input" type="date" data-exp="date" value="${defaultDate || todayISO()}" max="${todayISO()}"></label>
      </div>
      <button type="button" class="btn orange big" data-exp="go">${ic('minus')} Xarajatni saqlash</button>`;
  }

  /** Xarajat formasini ishga tushiradi; saqlangach onSaved(amount) chaqiriladi */
  function bindExpenseForm(root, onSaved) {
    let cat = 'food';
    let need = '';
    root.querySelectorAll('[data-cat]').forEach((b) => {
      b.onclick = () => {
        cat = b.dataset.cat;
        root.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('active', x === b));
        haptic('light');
      };
    });
    root.querySelectorAll('[data-need]').forEach((b) => {
      b.onclick = () => {
        need = need === b.dataset.need ? '' : b.dataset.need; // qayta bosilsa belgi olinadi
        root.querySelectorAll('[data-need]').forEach((x) => x.classList.toggle('active', x.dataset.need === need));
        haptic('light');
      };
    });
    const val = bindMoney(root.querySelector('[data-exp="amount"]'));
    root.querySelector('[data-exp="go"]').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const amount = val();
      if (!amount) { toast('Xarajat summasini kiriting', true); return; }
      try {
        await api('expenses', { method: 'POST', body: {
          amount, category: cat, need,
          note: root.querySelector('[data-exp="note"]').value,
          date: root.querySelector('[data-exp="date"]').value,
        } });
        haptic('success');
        toast(`${CATS[cat].label}: ${som(amount)} yozildi`);
        await onSaved(amount);
      } catch (e) { toast(e.message, true); }
    });
  }

  function expenseSheet(after, defaultDate) {
    const body = openSheet(`<h2>${ic('receipt')} Xarajat qo'shish</h2>${expenseFormHtml(defaultDate)}`);
    bindExpenseForm(body, async () => { closeSheet(true); if (after) await after(); });
    setTimeout(() => body.querySelector('[data-exp="amount"]').focus(), 350);
  }

  const SOURCES = { salary: 'Oylik maosh', extra: "Qo'shimcha", business: 'Biznes / savdo', other: 'Boshqa' };

  /** Kirim yozish oynasi: jonli "o'zingizga X%" hisobi, saqlangach darhol "o'zingizga to'lang" oynasi */
  function incomeSheet(percent, after, defaultDate) {
    const p = percent || 0;
    const body = openSheet(`
      <h2>${ic('up')} Kirim yozish</h2>
      <label class="field money"><input class="input" id="inc-amt" inputmode="numeric" placeholder="${ph('big')}" autocomplete="off"></label>
      ${p ? `<div class="calc-result" id="inc-calc" hidden>
        <div><span>O'zingizga (${p}%)</span><b id="inc-self">0</b></div>
        <div class="rest"><span>Qolgani</span><b id="inc-rest">0</b></div>
      </div>` : ''}
      <div class="form-grid mt">
        <label class="field"><span>Manba</span>
          <select class="input" id="inc-src">${Object.entries(SOURCES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
        <label class="field"><span>Sana</span><input class="input" type="date" id="inc-date" value="${defaultDate || todayISO()}" max="${todayISO()}"></label>
      </div>
      <button class="btn big" id="inc-go">${ic('plus')} Kirimni saqlash</button>`);
    const $ = (s) => body.querySelector(s);
    const val = bindMoney($('#inc-amt'), (v) => {
      if (!p) return;
      const self = Math.floor((v * p) / 100);
      $('#inc-calc').hidden = !v;
      $('#inc-self').textContent = som(self);
      $('#inc-rest').textContent = som(v - self);
    });
    $('#inc-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const amount = val();
      if (!amount) { toast('Kirim summasini kiriting', true); return; }
      try {
        const r = await api('incomes', { method: 'POST', body: { amount, source: $('#inc-src').value, date: $('#inc-date').value } });
        haptic('success');
        saveSheet(r.suggested_saving, r.income.id, amount, after);
      } catch (e) { toast(e.message, true); }
    });
    setTimeout(() => $('#inc-amt').focus(), 350);
  }

  /** Telegram'da ulashish oynasi (Mini App ichida — Telegram'ning o'zida, brauzerda — yangi oynada) */
  function share(url, text) {
    const link = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text || '')}`;
    if (tg && tg.openTelegramLink && tg.initData) tg.openTelegramLink(link);
    else window.open(link, '_blank', 'noopener');
  }

  /** Havolani ulashish varag'i: Telegram orqali yuborish + nusxa olish */
  function shareSheet(title, hint, url, text, after) {
    const body = openSheet(`
      <div class="celebrate"><div class="big-ico blue">${ic('send')}</div></div>
      <h2 class="center">${esc(title)}</h2>
      <p class="center muted">${hint}</p>
      <div class="share-link"><span>${esc(url)}</span></div>
      <button class="btn big" id="sh-go">${ic('send')} Telegram orqali yuborish</button>
      <button class="btn ghost block" id="sh-copy">Havolani nusxalash</button>`, after);
    body.querySelector('#sh-go').onclick = () => share(url, text);
    body.querySelector('#sh-copy').onclick = async () => {
      try { await navigator.clipboard.writeText(`${text}\n${url}`); toast('Nusxalandi'); } catch (e) { toast('Nusxalab bo\'lmadi — havolani qo\'lda belgilang', true); }
    };
  }

  const dayLabel = (iso) => { const [, m, d] = iso.split('-').map(Number); return `${d}-${MONTHS[m - 1].toLowerCase()}`; };

  /** Tarixdagi bitta yozuv qatori (Hamyon — tahrir/o'chirish bilan, bosh sahifa — faqat ko'rish) */
  function entryRow(e, actions) {
    let icon; let cls; let sign; let title; let color;
    if (e.type === 'income') { icon = 'up'; cls = 'plus'; sign = '+'; title = SOURCES[e.source] || e.label; color = '#2563eb'; }
    else if (e.type === 'saving') {
      const b = BUCKETS[e.bucket] || BUCKETS.guard;
      const out = e.amount < 0;
      icon = b.icon; cls = out ? 'plus' : 'save'; sign = out ? '←' : '→'; color = b.color;
      title = out ? `${b.label}dan olindi` : `${b.label}ga`;
    }
    else { const c = CATS[e.category] || CATS.other; icon = c.icon; cls = 'minus'; sign = '−'; title = c.label; color = c.color; }
    const editable = actions && e.type !== 'saving';
    return `<li class="entry ${editable ? 'editable' : ''}" ${editable ? `data-edit="${e.type}/${e.id}"` : ''}>
      <span class="e-icon" style="--c:${color}">${ic(icon)}</span>
      <span class="e-main"><b>${esc(title)}${e.need ? `<span class="need-tag" style="background:${NEEDS[e.need].color}">${NEEDS[e.need].label}</span>` : ''}</b><small>${dayLabel(e.date)}${e.note ? ` · ${esc(e.note)}` : ''}</small></span>
      <span class="e-amt ${cls}">${sign}${num(Math.abs(e.amount))}</span>
      ${actions ? `<button class="e-del" data-del="${e.type}/${e.id}" aria-label="O'chirish">${ic('trash')}</button>` : ''}
    </li>`;
  }

  // ------------------------------------------------------------------ MB kursi
  const fmtRate = (r) => r.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/ /g, ' ');

  /** "MB kursi: 1 $ = 11 821,18 so'm · 30.09.2026 ▲14,21" */
  function rateLine(rate, extra = '') {
    if (!rate) return `<p class="rate-line muted">${ic('alert')} Markaziy bank kursi hozircha mavjud emas</p>`;
    const up = rate.diff >= 0;
    return `<p class="rate-line">${ic('bank')} MB kursi: <b>1 $ = ${fmtRate(rate.rate)} so'm</b>
      <span class="muted">· ${esc(rate.date)}${rate.stale ? ' (oxirgi ma\'lum)' : ''}</span>
      ${rate.diff ? `<span class="${up ? 'c-green' : 'c-red'}">${up ? '▲' : '▼'}${fmtRate(Math.abs(rate.diff))}</span>` : ''}${extra}</p>`;
  }

  function currencyOptions(selected) {
    return `<div class="cur-grid big">${Object.entries(CURRENCIES).map(([code, c]) => `
      <button type="button" class="cur-opt ${selected === code ? 'active' : ''}" data-pick="${code}">
        <b>${code === 'USD' ? '$' : "so'm"}</b><span>${c.label}</span>
        <small>${code === 'USD' ? 'Maosh yoki jamg\'arma dollarda bo\'lsa' : 'Maosh va xarajatlar so\'mda bo\'lsa (ko\'pchilik uchun)'}</small>
      </button>`).join('')}</div>`;
  }

  /** Valyutani tanlash / almashtirish. Ma'lumot bo'lsa, server MB kursi bo'yicha qayta hisoblaydi. */
  async function currencySheet(user, after, preselect) {
    let pick = preselect || user.currency;
    let rate = null;
    try { rate = (await api('rates')).rate; } catch (e) { /* kurs bo'lmasa ham tanlash mumkin */ }
    const body = openSheet(`
      <h2>${ic('coins')} Hisob valyutasi</h2>
      <p class="muted">Hisob-kitobni qaysi valyutada olib borasiz? Barcha summalar faqat shu valyutada bo'ladi.</p>
      ${currencyOptions(pick)}
      ${rateLine(rate)}
      <p class="tip" id="cur-warn" hidden>${ic('alert')} Mavjud yozuvlaringiz (kirim, xarajat, jamg'arma, qarzlar)
        Markaziy bank kursi bo'yicha yangi valyutaga qayta hisoblanadi.</p>
      <button class="btn big" id="cur-save">${ic('check')} Tanlash</button>`, after);
    const sync = () => {
      body.querySelectorAll('[data-pick]').forEach((b) => b.classList.toggle('active', b.dataset.pick === pick));
      body.querySelector('#cur-warn').hidden = !user.currency_chosen || pick === user.currency;
    };
    body.querySelectorAll('[data-pick]').forEach((b) => { b.onclick = () => { pick = b.dataset.pick; haptic('light'); sync(); }; });
    sync();
    body.querySelector('#cur-save').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      try {
        const r = await api('me/currency', { method: 'POST', body: { currency: pick } });
        Object.assign(user, r.user);
        haptic('success');
        closeSheet();
        toast(r.converted ? `Yozuvlar ${CURRENCIES[pick].label.toLowerCase()}ga o'tkazildi` : `Hisob valyutasi: ${CURRENCIES[pick].label}`);
      } catch (e) { toast(e.message, true); }
    });
  }

  // ------------------------------------------------------------------ tanishtiruv
  const ROAD = [
    ['coins', 'Valyutani tanlang', "So'm yoki dollar — hisob bitta valyutada"],
    ['wallet', 'Daromadni sozlang', "Oylik bormi va necha foizini o'zingizga to'laysiz"],
    ['receipt', 'Har kuni xarajat yozing', "Bir daqiqa — pul qayerga ketayotgani ko'rinadi"],
    ['safe', "Avval o'zingizga to'lang", "Daromad tushishi bilan bir qismini jamg'armaga"],
    ['card', 'Qarzlarni reja bilan yoping', "Kredit kalkulyatori va qarzdan qutulish rejasi"],
    ['book', "Har hafta bitta saboq", "Video, xulosa va amaliy vazifa"],
  ];

  /** Birinchi kirishda: xush kelibsiz → yo'l xaritasi → valyuta → daromad */
  function onboardingSheet(user, after, rate) {
    let pick = user.currency || 'UZS';
    const body = openSheet(`
      <div class="tour-dots"><i class="on"></i><i></i><i></i></div>
      ${celebrate('book', 'Xush kelibsiz!', "Baraka Daftari — pulni yozib borish, avval o'zingizga to'lash va qarzdan reja bilan chiqish uchun daftar.")}
      ${disclaimerHtml()}
      <button class="btn big" id="t-next">Boshladik ${ic('arrow')}</button>`);
    body.querySelector('#t-next').onclick = step2;

    function step2() {
      setSheet(`
        <div class="tour-dots"><i></i><i class="on"></i><i></i></div>
        <h2>Sizning yo'lingiz</h2>
        <p class="muted">Har kuni 5 daqiqa. Shu tartibda yurasiz — bosh sahifada «Boshlash yo'li» kuzatib boradi.</p>
        <ol class="road-list">${ROAD.map(([i, t, h]) => `<li><span class="h-ico green">${ic(i)}</span><div><b>${t}</b><small>${h}</small></div></li>`).join('')}</ol>
        <button class="btn big" id="t-next">Davom etish ${ic('arrow')}</button>`)
        .querySelector('#t-next').onclick = step3;
    }

    function step3() {
      const b = setSheet(`
        <div class="tour-dots"><i></i><i></i><i class="on"></i></div>
        <h2>Hisob-kitobni qaysi valyutada olib borasiz?</h2>
        <p class="muted">Barcha summalar shu valyutada yuritiladi — so'm va dollar aralashmaydi. Keyin sozlamalarda o'zgartirish mumkin.</p>
        ${currencyOptions(pick)}
        ${rateLine(rate)}
        <button class="btn big" id="t-done">${ic('check')} Tanlash va davom etish</button>`);
      b.querySelectorAll('[data-pick]').forEach((btn) => {
        btn.onclick = () => {
          pick = btn.dataset.pick;
          b.querySelectorAll('[data-pick]').forEach((x) => x.classList.toggle('active', x === btn));
          haptic('light');
        };
      });
      b.querySelector('#t-done').onclick = (ev) => withBusy(ev.currentTarget, async () => {
        try {
          const r = await api('me/currency', { method: 'POST', body: { currency: pick } });
          await api('me', { method: 'POST', body: { accepted_disclaimer: true } });
          Object.assign(user, r.user);
          closeSheet(true);
          haptic('success');
          // Oxirgi qadam: daromad sozlamalari (o'tkazib yuborsa ham bo'ladi)
          setTimeout(() => (user.income_type ? after && after() : incomeSetupSheet(user, after)), 350);
        } catch (e) { toast(e.message, true); }
      });
    }
  }

  const compactMoney = (n) => (currency === 'USD' ? compact(n) : `${compactNum(n)} so'm`);

  window.B = {
    compactMoney,
    saveSheet, incomeSetupSheet, expenseSheet, incomeSheet, entryRow, share, shareSheet, SOURCES, expenseFormHtml, bindExpenseForm, CATS, NEEDS, BUCKETS,
    tg, IN_TG, CFG, MONTHS, DISCLAIMER,
    esc, num, som, digits, compact, pad, todayISO, monthKey, monthLabel, sleep, ic, haptic,
    CURRENCIES, setCurrency, curSign, ph, otherCurrency, get currency() { return currency; },
    rateLine, currencySheet, onboardingSheet,
    api, ApiError, setToken, logout, get token() { return token; },
    toast, openSheet, setSheet, closeSheet, onSheetClose, celebrate, confirmAsk, openModal, ratingModal, maybeAskRating,
    bindMoney, withBusy, animateBars, confetti, render, errorView, disclaimerHtml, ready,
  };
})();
