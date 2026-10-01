/* Loyiha haqida: tamoyillar va Abdukarim Mirzayev sahifalari (havolalar admin panelda sozlanadi).
   Aloqa ma'lumotlari — alohida /aloqa/ sahifasida (contact.js). */
(() => {
  'use strict';
  const { ic, esc, render, api } = B;
  const BOT = B.CFG.botUsername;

  // Faqat https havolalar va oddiy telefon/email — admin xato kiritsa ham sahifaga begona narsa tushmaydi
  const safeUrl = (u) => (/^https:\/\/[^\s"'<>]+$/.test(u || '') ? u : '');

  function linkRow(href, icon, color, title, sub) {
    if (!href) return '';
    const external = href.startsWith('https://');
    return `<a class="menu-item" href="${esc(href)}" ${external ? 'target="_blank" rel="noopener noreferrer"' : ''}>
      <span class="h-ico ${color}">${ic(icon)}</span><span><b>${esc(title)}</b>${sub ? `<small>${esc(sub)}</small>` : ''}</span></a>`;
  }

  async function main() {
    let site = { author: {} };
    try { site = await api('site'); } catch (e) { /* havolalar bo'lmasa ham sahifa ochiladi */ }
    const a = site.author || {};
    const botLink = BOT ? `https://t.me/${BOT}` : '';

    const authorLinks = [
      linkRow(safeUrl(a.youtube), 'youtube', 'red', 'YouTube', '«Baraka Daftari» ko\'rsatuvi'),
      linkRow(safeUrl(a.instagram), 'instagram', 'purple', 'Instagram', ''),
      linkRow(safeUrl(a.telegram), 'send', 'blue', 'Telegram kanal', ''),
    ].join('');

    render(`
      <section class="hero compact">
        <img src="/static/img/logo.svg" alt="" class="hero-logo">
        <h1>Elektron <span>Baraka</span> Daftari</h1>
      </section>
      ${B.disclaimerHtml()}
      <section class="card principles">
        <div><span class="h-ico orange">${ic('x')}</span>Bu loyiha tez boyish usuli emas</div>
        <div><span class="h-ico green">${ic('check')}</span>Bu loyiha — boylikning ilmi</div>
        <div><span class="h-ico orange">${ic('x')}</span>Bu loyiha diniy fatvo emas</div>
        <div><span class="h-ico green">${ic('check')}</span>Bu loyiha — ta'limiy asar</div>
      </section>
      <section class="card">
        <h3>Loyiha haqida</h3>
        <p class="mt">Bu — moliyaviy saboqlarni amaliyotga aylantiruvchi bepul raqamli daftar. Maqsad: avval o'zingizga
          to'lash, xarajatlarni nazorat qilish va qarzdan qutulish bosqichlarini haftalik saboqlar va kichik amaliy
          qadamlar bilan o'rgatish.</p>
        <ul class="about-list mt">
          <li><span class="h-ico blue">${ic('book')}</span><div><b>Saboqlar</b> — har bir video bo'yicha saboq; vazifani bajarsangiz, keyingisi ochiladi.</div></li>
          <li><span class="h-ico green">${ic('wallet')}</span><div><b>Hamyon</b> — xarajatlar, qolgan pul, Zarur · Kerak · Havas.</div></li>
          <li><span class="h-ico green">${ic('safe')}</span><div><b>Jamg'arma</b> — qo'riqchi pul va o'sadigan pul.</div></li>
          <li><span class="h-ico orange">${ic('snow')}</span><div><b>Qarzlar</b> — 70/20/10 va «qor bo'lagi» rejasi.</div></li>
          <li><span class="h-ico blue">${ic('calc')}</span><div><b>Kalkulyatorlar</b> — kredit, qarzdan chiqish, narxlar va pul qadri.</div></li>
          <li><span class="h-ico purple">${ic('bell')}</span><div><b>Bot</b> — yangi saboq xabari, kechqurun xarajat eslatmasi.</div></li>
        </ul>
      </section>

      ${authorLinks ? `<section class="card">
        <div class="card-title"><h3>Abdukarim Mirzayev</h3></div>
        <p class="muted small">Saboqlarning asl manbai — ko'rsatuvni kuzatib boring.</p>
        <div class="menu-grid mt">${authorLinks}</div>
      </section>` : ''}

      <section class="card">
        <div class="menu-grid">
          ${linkRow('/aloqa/', 'chat', 'gray', "Biz bilan bog'lanish", 'Savol, taklif yoki xato')}
          ${linkRow(botLink, 'send', 'blue', 'Botni ochish', BOT ? `@${BOT}` : '')}
        </div>
      </section>`);
  }

  B.ready(main, { isPublic: true });
})();
