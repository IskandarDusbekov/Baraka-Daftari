/* Kirish: veb saytda Telegram bot orqali tasdiqlash */
(() => {
  'use strict';
  const { api, esc, ic, toast, withBusy } = B;

  const next = new URLSearchParams(location.search).get('next') || '/asosiy/';
  const safeNext = /^\/[a-z0-9/-]*$/i.test(next) && next !== '/' ? next : '/asosiy/';

  // Mini App ichida yoki allaqachon kirgan bo'lsa — to'g'ridan-to'g'ri ilovaga
  if (B.IN_TG || B.token) { location.replace(safeNext); return; }

  let poll = 0;
  document.getElementById('login-btn').onclick = (ev) => start(ev.currentTarget);

  // Dasturchi kirishi (login/parol) — faqat DEV_LOGIN yoqilganda ko'rinadi
  const devForm = document.getElementById('dev-form');
  if (devForm) {
    devForm.onsubmit = (ev) => {
      ev.preventDefault();
      const btn = devForm.querySelector('button');
      withBusy(btn, async () => {
        try {
          const r = await api('auth/dev-login', { method: 'POST', body: {
            username: devForm.username.value.trim(), password: devForm.password.value,
          } });
          B.setToken(r.token, r.user.tg_id);
          location.replace(safeNext);
        } catch (e) { toast(e.message, true); }
      });
    };
  }

  async function start(btn) {
    let data;
    await withBusy(btn, async () => {
      try { data = await api('auth/login-code', { method: 'POST' }); } catch (e) { toast(e.message, true); }
    });
    if (!data) return;
    const id = ++poll;
    B.openSheet(`
      <h2>Telegram orqali kirish</h2>
      <ol class="steps">
        <li>Pastdagi tugma orqali botni oching.</li>
        <li>Botda <b>START</b>, so'ng <b>«Ha, saytga kiraman»</b> tugmasini bosing.</li>
        <li>Shu sahifaga qayting — kirish avtomatik bo'ladi.</li>
      </ol>
      <a class="btn blue block" href="${esc(data.bot_link)}" target="_blank" rel="noopener">${ic('send')} Botni ochish</a>
      <div class="login-wait"><span class="spinner sm"></span> Tasdiqlash kutilmoqda…</div>`,
    () => { poll++; });

    const deadline = Date.now() + data.expires_in * 1000;
    while (id === poll && Date.now() < deadline) {
      await B.sleep(2000);
      if (id !== poll) return;
      let st;
      try { st = await api(`auth/login-status?code=${encodeURIComponent(data.code)}`); } catch (e) { continue; }
      if (st.status === 'ok') {
        poll++;
        B.setToken(st.token, st.user.tg_id);
        B.confetti(90);
        setTimeout(() => location.replace(safeNext), 600);
        return;
      }
      if (st.status !== 'pending') break;
    }
    if (id === poll) {
      B.setSheet(B.celebrate('clock', 'Vaqt tugadi', "Qaytadan urinib ko'ring.",
        '<button class="btn block" id="again">Yopish</button>'))
        .querySelector('#again').onclick = () => B.closeSheet();
    }
  }
})();
