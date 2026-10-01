/* Saboqlar yo'lkasi (roadmap) */
(() => {
  'use strict';
  const { api, esc, ic, toast, haptic, render, MONTHS } = B;

  const OFFSETS = [0, 55, 85, 55, 0, -55, -85, -55];
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

    const nodes = lessons.map((l, i) => {
      const inner = l.state === 'done' ? ic('check') : l.state === 'open' ? l.number : ic(l.state === 'wait' ? 'clock' : 'lock');
      const clickable = l.state === 'done' || l.state === 'open';
      const tag = clickable ? `a href="/saboqlar/${l.number}/"` : `button type="button" data-state="${l.state}"`;
      return `<div class="node-wrap ${l.state === 'open' ? 'is-open' : ''}" style="transform:translateX(${OFFSETS[i % OFFSETS.length]}px)">
          ${l.state === 'open' ? '<span class="start-bubble">BOSHLASH</span>' : ''}
          <${tag} class="node ${l.state}" aria-label="${l.number}-saboq: ${esc(l.title)}">${inner}</${clickable ? 'a' : 'button'}>
          <span class="node-label">${l.number}-saboq<b>${esc(l.title)}</b>${l.published_on ? `<small>${dateLabel(l.published_on)}</small>` : ''}</span>
        </div>`;
    }).join('');

    const page = render(`
      <section class="card road-head">
        <div class="row between"><h3><span class="h-ico blue">${ic('book')}</span> Saboqlar yo'lkasi</h3><span class="chip gold">${ic('star')} ${done * 10}</span></div>
        <div class="progress"><i data-w="${pct}"></i></div>
        <p class="muted small">${lessons.length} ta saboqdan <b>${done}</b> tasi bajarildi. Har hafta yangi video — yangi saboq.</p>
      </section>
      <section class="road">${nodes}
        <div class="node-wrap"><span class="node soon">${ic('clock')}</span>
          <span class="node-label">Keyingi saboq<b>yangi video bilan qo'shiladi</b></span></div>
      </section>`);

    page.querySelectorAll('button.node').forEach((b) => {
      b.onclick = () => {
        haptic('warning');
        toast("Avval oldingi saboqning vazifasini bajaring — shunda bu saboq ochiladi");
      };
    });
    const open = page.querySelector('.node.open');
    if (open) setTimeout(() => open.scrollIntoView({ behavior: 'smooth', block: 'center' }), 250);
  }

  B.ready(main);
})();
