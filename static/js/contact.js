/* Biz bilan bog'lanish: admin panel → Sozlamalar'da kiritilgan aloqa ma'lumotlari */
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
    let site = { contact: {} };
    try { site = await api('site'); } catch (e) { /* ma'lumot bo'lmasa ham bot havolasi chiqadi */ }
    const c = site.contact || {};
    const botLink = BOT ? `https://t.me/${BOT}` : '';

    const links = [
      linkRow(safeUrl(c.telegram), 'send', 'blue', 'Telegram orqali yozish', c.telegram_name || ''),
      linkRow(safeUrl(c.channel), 'send', 'blue', 'Bizning kanal', 'Yangiliklar va yangi saboqlar'),
      linkRow(safeUrl(c.instagram), 'instagram', 'purple', 'Instagram', ''),
      c.phone && /^\+?\d{7,15}$/.test(c.phone) ? linkRow(`tel:${c.phone}`, 'call', 'green', c.phone_label || c.phone, "Qo'ng'iroq qilish") : '',
      c.email && /^[^\s@<>"]+@[^\s@<>"]+$/.test(c.email) ? linkRow(`mailto:${c.email}`, 'mail', 'orange', c.email, 'Email yozish') : '',
    ].join('');

    render(`
      <h1 class="page-title">${ic('chat')} Biz bilan bog'lanish</h1>
      <section class="card">
        <p>Savol, taklif yoki xato topdingizmi? Yozing — albatta javob beramiz.</p>
        ${c.hours ? `<p class="muted small mt">${ic('clock')} ${esc(c.hours)}</p>` : ''}
        <div class="menu-grid mt">
          ${links || linkRow(botLink, 'send', 'blue', 'Bot orqali yozish', BOT ? `@${BOT}` : '')}
        </div>
      </section>
      ${B.token ? `<section class="card">
        <div class="card-title"><h3>Ilova yoqdimi?</h3></div>
        <p class="muted small">Bahoyingiz va fikringiz ilovani yaxshilashga yordam beradi.</p>
        <button class="btn ghost block mt" id="rate">${ic('star')} Baho berish</button>
      </section>` : ''}`);
    const rate = document.getElementById('rate');
    if (rate) rate.onclick = () => B.ratingModal();
  }

  B.ready(main, { isPublic: true });
})();
