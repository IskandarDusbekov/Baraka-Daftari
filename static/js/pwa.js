/* PWA: service worker va "Ilovani o'rnatish".
   Landing'da ham, ilova sahifalarida ham ishlaydi (common.js'ga bog'liq emas).
   window.BarakaPWA.available() — tugmani ko'rsatish kerakmi; .install() — o'rnatish yoki qo'llanma. */
(() => {
  'use strict';
  const ua = navigator.userAgent;
  const isIOS = /iphone|ipad|ipod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const tg = window.Telegram && window.Telegram.WebApp;
  const inMiniApp = !!(tg && tg.initData) || location.hash.includes('tgWebAppData');
  // Telegram/Instagram ichidagi brauzerda o'rnatib bo'lmaydi — Chrome yoki Safari kerak
  const inAppBrowser = /Telegram|Instagram|FBAN|FBAV/i.test(ua);
  let deferred = null;

  // Service worker faqat HTTPS'da (yoki lokal kompyuterda) ishlaydi
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault(); // o'z tugmamiz orqali so'raymiz
    deferred = e;
    paint();
  });
  window.addEventListener('appinstalled', () => { deferred = null; paint(); });

  const available = () => !standalone && !inMiniApp;

  const STEPS = {
    ios: ["Safari'da pastdagi <b>«Ulashish»</b> tugmasini bosing (kvadrat va yuqoriga strelka).",
      "Ro'yxatdan <b>«Bosh ekranga qo'shish»</b> (Add to Home Screen) ni tanlang.",
      "<b>«Qo'shish»</b> ni bosing — ilova telefon ekraningizda paydo bo'ladi."],
    android: ["Brauzer menyusini oching (yuqori o'ngdagi <b>⋮</b> belgisi).",
      "<b>«Ilovani o'rnatish»</b> yoki <b>«Bosh ekranga qo'shish»</b> ni tanlang.",
      "<b>«O'rnatish»</b> ni bosing — ilova telefon ekraningizda paydo bo'ladi."],
    inapp: ["Bu oyna Telegram (yoki Instagram) ichidagi brauzer — u yerdan o'rnatib bo'lmaydi.",
      "Yuqoridagi <b>⋮</b> menyusidan <b>«Brauzerda ochish»</b> ni tanlang.",
      "Chrome yoki Safari'da shu tugmani qayta bosing."],
  };

  function help() {
    const key = inAppBrowser ? 'inapp' : isIOS ? 'ios' : 'android';
    const wrap = document.createElement('div');
    wrap.setAttribute('role', 'dialog');
    wrap.setAttribute('aria-modal', 'true');
    wrap.style.cssText = 'position:fixed;inset:0;z-index:200;display:grid;place-items:end center;background:rgba(15,23,42,.45);padding:12px;font-family:inherit';
    wrap.innerHTML = `
      <div style="background:#fff;color:#1e293b;border-radius:22px;padding:22px 20px 18px;width:min(460px,100%);box-shadow:0 20px 60px rgba(0,0,0,.25)">
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
          <img src="/static/img/icon-192.png" alt="" width="48" height="48" style="border-radius:12px">
          <div><b style="font-size:18px;display:block">Telefonga o'rnatish</b>
            <span style="color:#64748b;font-size:14px">Ilova kabi ekrandan bir bosishda ochiladi</span></div>
        </div>
        <ol style="margin:0;padding-left:20px;line-height:1.5;font-size:15px">${STEPS[key].map((s) => `<li style="margin:6px 0">${s}</li>`).join('')}</ol>
        <button type="button" style="margin-top:16px;width:100%;border:0;border-radius:14px;padding:13px;font:inherit;font-weight:800;background:#16a34a;color:#fff;cursor:pointer">Tushunarli</button>
      </div>`;
    const close = () => wrap.remove();
    wrap.addEventListener('click', (e) => { if (e.target === wrap || e.target.tagName === 'BUTTON') close(); });
    document.body.appendChild(wrap);
  }

  async function install() {
    if (deferred) {
      deferred.prompt();
      try { await deferred.userChoice; } catch (e) { /* bekor qilindi */ }
      deferred = null;
      paint();
      return;
    }
    help();
  }

  /** Sahifadagi [data-install] tugmalari: o'rnatib bo'lmaydigan joyda yashiriladi */
  function paint() {
    document.querySelectorAll('[data-install]').forEach((b) => {
      b.hidden = !available();
      if (!b.dataset.wired) { b.dataset.wired = '1'; b.addEventListener('click', (e) => { e.preventDefault(); install(); }); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paint); else paint();

  window.BarakaPWA = { available, install, standalone };
})();
