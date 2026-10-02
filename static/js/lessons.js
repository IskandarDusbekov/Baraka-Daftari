/* Saboqlar ro'yxati: bajarilgan, hozirgi va qulfdagi saboqlar */
(() => {
  'use strict';
  const { api, esc, ic, toast, haptic, render, MONTHS } = B;

  const dateLabel = (iso) => { const [, m, d] = iso.split('-').map(Number); return `${d}-${MONTHS[m - 1].toLowerCase()}`; };

  async function main() {
    const { lessons } = await api('lessons');
    const done = lessons.filter((l) => l.state === 'done').length;
    const pct = lessons.length ? Math.round((done * 100) / lessons.length) : 0;

    if (!lessons.length) {
      render(`<section class="card empty">
        <span class="e-ico">${ic('book')}</span>
        <h3>Saboqlar tez orada qo'shiladi</h3>
        <p class="mt">Abdukarim Mirzayevning «Baraka Daftari» ko'rsatuvi har hafta yangi video bilan davom etadi.
          Har bir video bo'yicha saboqlar va amaliy vazifalar shu yerda paydo bo'ladi.</p>
        <a class="btn mt" href="/hamyon/">${ic('wallet')} Hozircha Hamyonni to'ldiring</a>
      </section>`);
      return;
    }

    const STATUS = { done: 'Bajarildi', open: 'Hozirgi saboq', locked: "Oldingi saboq vazifasidan keyin ochiladi" };
    const rows = lessons.map((l) => {
      const mark = l.state === 'done' ? ic('check') : l.state === 'open' ? l.number : ic('lock');
      const clickable = l.state === 'done' || l.state === 'open';
      const tag = clickable ? `a href="/saboqlar/${l.number}/"` : 'button type="button" data-locked';
      return `<li><${tag} class="lrow ${l.state}">
          <span class="lr-mark">${mark}</span>
          <span class="lr-main"><small>${l.number}-saboq${l.published_on ? ` · ${dateLabel(l.published_on)}` : ''}</small>
            <b>${esc(l.title)}</b><em>${STATUS[l.state] || ''}</em></span>
          ${clickable ? ic('right', 'lr-go') : ''}
        </${clickable ? 'a' : 'button'}></li>`;
    }).join('');

    const page = render(`
      <section class="card road-head">
        <div class="card-title"><h3><span class="h-ico blue">${ic('book')}</span> Saboqlar</h3><span class="chip">${done} / ${lessons.length}</span></div>
        <div class="progress"><i data-w="${pct}"></i></div>
        <p class="muted small">Har bir saboq — bitta video va bitta amaliy vazifa. Vazifani bajarsangiz, keyingi saboq ochiladi.</p>
      </section>
      <ol class="lesson-list">${rows}
        <li><div class="lrow soon"><span class="lr-mark">${ic('clock')}</span>
          <span class="lr-main"><small>Keyingi saboq</small><b>Yangi video chiqqanda qo'shiladi</b></span></div></li>
      </ol>`);

    page.querySelectorAll('[data-locked]').forEach((b) => {
      b.onclick = () => {
        haptic('warning');
        toast("Avval oldingi saboqning vazifasini bajaring — shunda bu saboq ochiladi");
      };
    });
    const open = page.querySelector('.lrow.open');
    if (open) setTimeout(() => open.scrollIntoView({ behavior: 'smooth', block: 'center' }), 250);
  }

  B.ready(main);
})();
