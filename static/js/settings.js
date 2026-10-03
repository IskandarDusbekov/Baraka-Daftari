/* Sozlamalar: telefondagi kabi guruhlangan ro'yxat — Moliya, Ilova, Yordam, Hisob */
(() => {
  'use strict';
  const { api, esc, som, compact, ic, toast, haptic, render } = B;
  const BOT = B.CFG.botUsername;
  const GUARD_CHOICES = [3, 4, 5, 6];

  function incomeValue(u) {
    if (u.income_type === 'salary' && u.monthly_income) return compact(u.monthly_income);
    if (u.income_type === 'irregular') return "O'zgaruvchan";
    return '<span class="c-orange">Sozlanmagan</span>';
  }

  /** Bitta qator: ikonka, nom, joriy qiymat, o'ng tomonda strelka (yoki boshqa element) */
  const row = ({ id, href, icon, color, title, value = '', sub = '', right, danger }) => {
    const tag = href ? `a href="${href}"${href.startsWith('http') ? ' target="_blank" rel="noopener"' : ''}` : 'button type="button"';
    return `<${tag} class="set-row ${danger ? 'danger' : ''}" ${id ? `id="${id}"` : ''}>
      <span class="h-ico ${color}">${ic(icon)}</span>
      <span class="sr-main"><b>${title}</b>${sub ? `<small>${sub}</small>` : ''}</span>
      ${value ? `<span class="sr-value">${value}</span>` : ''}
      ${right === undefined ? ic('right', 'sr-go') : right}
    </${href ? 'a' : 'button'}>`;
  };
  const group = (title, rows) => `<section class="set-group"><h3>${title}</h3><div class="set-card">${rows.join('')}</div></section>`;

  async function main() {
    const [me, rec] = await Promise.all([api('me'), api('recurring')]);
    const u = me.user;
    const botLink = BOT ? `https://t.me/${BOT}` : '';
    const canInstall = window.BarakaPWA && BarakaPWA.available();
    const initial = esc((u.first_name || u.name || '?').trim().charAt(0).toUpperCase());

    const page = render(`
      <h1 class="page-title">${ic('gear')} Sozlamalar</h1>

      <section class="card profile-card">
        <span class="pc-avatar">${initial}${u.photo_url ? `<img src="${esc(u.photo_url)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}</span>
        <div><b>${esc(u.name)}</b><small>${u.username ? `@${esc(u.username)} · ` : ''}Telegram orqali kirgan</small></div>
      </section>

      ${group('Moliya', [
        row({ id: 'cur-row', icon: 'coins', color: 'blue', title: 'Hisob valyutasi', value: B.CURRENCIES[u.currency].label,
          sub: me.rate ? `MB kursi: 1 $ = ${Math.round(me.rate.rate).toLocaleString('ru-RU').replace(/,/g, ' ')} so'm` : '' }),
        row({ id: 'income-row', icon: 'wallet', color: 'green', title: 'Daromad', value: incomeValue(u),
          sub: u.income_type ? `O'zingizga ${u.save_percent}% to'laysiz` : '' }),
        row({ href: '/hamyon/#doimiy', icon: 'repeat', color: 'orange', title: 'Doimiy xarajatlar',
          value: rec.items.length ? `${compact(rec.total)}/oy` : '',
          sub: rec.items.length ? `${rec.items.length} ta — har oy o'zi yoziladi` : "Ijara, kommunal, internet — bir marta kiriting" }),
        row({ id: 'guard-row', icon: 'shield', color: 'blue', title: "Qo'riqchi pul", value: `${u.guard_months} oylik`,
          sub: me.savings.monthly_need ? `Maqsad: ${som(me.savings.monthly_need * u.guard_months)}` : '' }),
      ])}

      ${group('Ilova', [
        row({ icon: 'bell', color: 'purple', title: 'Bot eslatmalari', sub: 'Yangi saboq va kechki xarajat eslatmasi',
          right: `<label class="switch"><input type="checkbox" id="notify" ${u.notify ? 'checked' : ''}><span></span></label>` }),
        botLink ? row({ href: botLink, icon: 'send', color: 'blue', title: 'Telegram bot',
          sub: `@${esc(BOT)}${u.bot_started ? '' : ' · eslatmalar uchun START ni bosing'}` }) : '',
        canInstall ? row({ id: 'install-row', icon: 'phone', color: 'green', title: "Telefonga o'rnatish", sub: 'Ilova kabi ekrandan ochiladi' }) : '',
        row({ id: 'tour', icon: 'book', color: 'gray', title: "Tanishtiruvni qayta ko'rish" }),
      ])}

      ${group('Yordam', [
        row({ id: 'share-row', icon: 'users', color: 'green', title: "Do'stga tavsiya qilish" }),
        row({ id: 'rate', icon: 'star', color: 'gold', title: 'Ilovaga baho berish' }),
        row({ href: '/aloqa/', icon: 'chat', color: 'gray', title: "Biz bilan bog'lanish" }),
        row({ href: '/haqida/', icon: 'info', color: 'orange', title: 'Loyiha haqida' }),
      ])}

      ${group('Hisob', [
        B.IN_TG ? '' : row({ id: 'logout', icon: 'logout', color: 'gray', title: 'Chiqish', right: '' }),
        row({ id: 'logout-all', icon: 'lock', color: 'red', title: 'Barcha qurilmalardan chiqish', danger: true, right: '' }),
      ])}

      <p class="set-foot muted small">Baraka Daftari · mustaqil loyiha · ma'lumotlaringiz faqat sizga ko'rinadi</p>`);

    const $ = (s) => page.querySelector(s);
    $('#cur-row').onclick = () => B.currencySheet(u, main);
    $('#income-row').onclick = () => B.incomeSetupSheet(u, main);
    $('#guard-row').onclick = () => guardSheet(u, me.savings.monthly_need);
    $('#notify').onchange = async (ev) => {
      try {
        await api('me', { method: 'POST', body: { notify: ev.target.checked } });
        toast(ev.target.checked ? 'Eslatmalar yoqildi' : "Eslatmalar o'chirildi");
      } catch (e) { ev.target.checked = !ev.target.checked; toast(e.message, true); }
    };
    if ($('#install-row')) $('#install-row').onclick = () => BarakaPWA.install();
    $('#tour').onclick = () => B.onboardingSheet(u, main, me.rate);
    $('#share-row').onclick = () => B.share(`${location.origin}/`, "Xarajat, jamg'arma va qarzlarni yozib boradigan bepul daftar. Kredit kalkulyatori ham bor — foydali bo'ladi:");
    $('#rate').onclick = () => B.ratingModal();
    if ($('#logout')) {
      $('#logout').onclick = async () => {
        if (await B.confirmAsk('Qayta kirish uchun Telegram orqali tasdiqlaysiz.', { title: 'Hisobdan chiqasizmi?', ok: 'Chiqish' })) B.logout();
      };
    }
    $('#logout-all').onclick = async () => {
      const ok = await B.confirmAsk("Telegram, telefon va kompyuterdagi barcha ochiq kirishlar yopiladi. Ma'lumotlaringiz o'chmaydi.",
        { title: 'Barcha qurilmalardan chiqish', ok: 'Ha, chiqish', danger: true });
      if (!ok) return;
      try { await api('me/logout-all', { method: 'POST', body: {} }); toast('Barcha qurilmalardan chiqildi'); setTimeout(B.logout, 900); } catch (e) { toast(e.message, true); }
    };

    // Boshqa sahifadan "valyutani tanlang" havolasi bilan kelinganda
    if (location.hash === '#valyuta') { history.replaceState(null, '', location.pathname); B.currencySheet(u, main); }
  }

  function guardSheet(u, need) {
    const body = B.openSheet(`
      <h2>${ic('shield')} Qo'riqchi pul</h2>
      <p class="muted">Og'ir kun uchun (kasallik, ishsiz qolish) necha oylik xarajatni zaxirada saqlaysiz? Odatda 3–6 oy tavsiya qilinadi.</p>
      <div class="pct-grid four">${GUARD_CHOICES.map((m) => `
        <button type="button" class="pct ${u.guard_months === m ? 'active' : ''}" data-guard="${m}"><b>${m} oy</b><small>${need ? compact(need * m) : ''}</small></button>`).join('')}
      </div>
      <a class="btn ghost block" href="/jamgarma/">${ic('safe')} Jamg'armani ko'rish</a>`);
    body.querySelectorAll('[data-guard]').forEach((b) => {
      b.onclick = async () => {
        try {
          await api('me', { method: 'POST', body: { guard_months: Number(b.dataset.guard) } });
          haptic('light');
          B.closeSheet(true);
          toast(`Qo'riqchi pul: ${b.dataset.guard} oylik`);
          await main();
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  B.ready(main);
})();
