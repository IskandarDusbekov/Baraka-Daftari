/* Jamg'arma: qo'riqchi pul va o'sadigan pul (3-saboq), qo'shish / o'tkazish / olish, tarix */
(() => {
  'use strict';
  const { api, esc, num, som, ic, toast, haptic, withBusy, bindMoney, render, MONTHS, BUCKETS } = B;

  const dayLabel = (iso) => { const [y, m, d] = iso.split('-').map(Number); return `${d}-${MONTHS[m - 1].toLowerCase()} ${y}`; };
  let history = [];
  let hasMore = false;

  async function main() {
    const r = await api('jamgarma');
    const s = r.savings;
    history = r.history.entries;
    hasMore = r.history.has_more;

    const page = render(`
      <section class="card savings-hero">
        <span class="chip on-dark">${ic('safe')} Jamg'armam</span>
        <h2>${som(s.total)}</h2>
      </section>

      <section class="grid2">
        <div class="bucket-card guard">
          <span class="stat-ico">${ic('shield')}</span>
          <span class="stat-label">Qo'riqchi pul</span>
          <b>${som(s.guard)}</b>
          ${s.guard_target ? `
            <div class="progress thin white"><i data-w="${s.guard_percent}"></i></div>
            <small>${s.months_covered} oyga yetadi · maqsad ${s.guard_months} oy</small>`
          : '<small>Og\'ir kun uchun</small>'}
        </div>
        <div class="bucket-card grow">
          <span class="stat-ico">${ic('sprout')}</span>
          <span class="stat-label">O'sadigan pul</span>
          <b>${som(s.grow)}</b>
          <small>Ishlaydigan pul</small>
        </div>
      </section>

      <section class="action-row">
        <button class="btn" id="add-btn">${ic('plus')} Qo'shish</button>
        <button class="btn ghost" id="move-btn">${ic('swap')} O'tkazish</button>
        <button class="btn ghost" id="take-btn">${ic('minus')} Olish</button>
      </section>

      ${s.guard_target ? `
      <section class="card">
        <div class="card-title"><h3><span class="h-ico blue">${ic('shield')}</span> Qo'riqchi pul maqsadi</h3><span class="chip">${s.guard_percent}%</span></div>
        <div class="progress"><i data-w="${s.guard_percent}"></i></div>
        <p class="muted small mt">${som(s.guard)} / ${som(s.guard_target)} · ${s.guard_months} oylik xarajat</p>
        ${s.guard >= s.guard_target ? `<p class="chip mt">${ic('check')} To'ldi — endi o'sadigan pulga</p>` : ''}
      </section>` : ''}

      <section class="card">
        <div class="card-title"><h3><span class="h-ico gray">${ic('history')}</span> Jamg'arma tarixi</h3><span class="muted small">${r.history.count} ta</span></div>
        <ul class="entries" id="hist">${history.length ? history.map(row).join('') : ''}</ul>
        ${history.length ? '' : `<div class="empty"><span class="e-ico">${ic('safe')}</span>Hali jamg'arma yo'q. «Qo'shish» ni bosing.</div>`}
        <button class="btn ghost block mt" id="more" ${hasMore ? '' : 'hidden'}>Ko'proq ko'rsatish</button>
      </section>`);

    page.querySelector('#add-btn').onclick = () => B.saveSheet(0, null, 0, main);
    page.querySelector('#move-btn').onclick = () => moveSheet(s);
    page.querySelector('#take-btn').onclick = () => takeSheet(s);
    bindHistory(page);
  }

  function row(e) {
    const b = BUCKETS[e.bucket];
    const title = e.kind === 'deposit' ? `${b.label}ga qo'shildi`
      : e.kind === 'withdraw' ? `${b.label}dan olindi`
        : e.amount > 0 ? `${b.label}ga o'tkazildi` : `${b.label}dan o'tkazildi`;
    return `<li class="entry">
      <span class="e-icon" style="--c:${b.color}">${ic(e.kind === 'transfer' ? 'swap' : b.icon)}</span>
      <span class="e-main"><b>${title}</b><small>${dayLabel(e.date)}${e.note ? ` · ${esc(e.note)}` : ''}</small></span>
      <span class="e-amt ${e.amount > 0 ? 'save' : 'minus'}">${e.amount > 0 ? '+' : '−'}${num(Math.abs(e.amount))}</span>
      <button class="e-del" data-del="${e.id}" aria-label="O'chirish">${ic('trash')}</button>
    </li>`;
  }

  function bindHistory(page) {
    const list = page.querySelector('#hist');
    const bindDel = () => list.querySelectorAll('[data-del]').forEach((b) => {
      b.onclick = async () => {
        if (!(await B.confirmAsk("O'tkazma bo'lsa, ikkala qismi ham o'chadi.", { title: "Yozuvni o'chirasizmi?", ok: "O'chirish", danger: true }))) return;
        try { await api(`entries/saving/${b.dataset.del}`, { method: 'DELETE' }); toast("O'chirildi"); await main(); } catch (e) { toast(e.message, true); }
      };
    });
    bindDel();
    const more = page.querySelector('#more');
    more.onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const r = await api(`jamgarma?offset=${history.length}`);
      history = history.concat(r.history.entries);
      list.insertAdjacentHTML('beforeend', r.history.entries.map(row).join(''));
      more.hidden = !r.history.has_more;
      bindDel();
    });
  }

  function bucketPicker(active, label) {
    return `<span class="field-label">${label}</span>
      <div class="seg">${Object.entries(BUCKETS).map(([k, b]) => `<button type="button" data-b="${k}" class="${k === active ? 'active' : ''}">${ic(b.icon)} ${b.label}</button>`).join('')}</div>`;
  }

  function moveSheet(s) {
    let from = s.guard >= s.grow ? 'guard' : 'grow';
    const body = B.openSheet(`
      <h2>${ic('swap')} O'tkazish</h2>
      ${bucketPicker(from, 'Qayerdan?')}
      <p class="muted small" id="mv-hint"></p>
      <label class="field money"><input class="input" id="mv-amt" inputmode="numeric" placeholder="0"></label>
      <label class="field"><span>Izoh (ixtiyoriy)</span><input class="input" id="mv-note" maxlength="200" placeholder="Masalan: savdoga sarmoya"></label>
      <button class="btn big" id="mv-go">O'tkazish</button>`);
    const hint = () => {
      const to = from === 'guard' ? 'grow' : 'guard';
      body.querySelector('#mv-hint').innerHTML = `${BUCKETS[from].label} (${som(s[from])}) → <b>${BUCKETS[to].label}</b>`;
    };
    body.querySelectorAll('[data-b]').forEach((b) => {
      b.onclick = () => { from = b.dataset.b; body.querySelectorAll('[data-b]').forEach((x) => x.classList.toggle('active', x === b)); hint(); };
    });
    hint();
    const val = bindMoney(body.querySelector('#mv-amt'));
    body.querySelector('#mv-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      if (!val()) { toast('Summani kiriting', true); return; }
      try {
        await api('savings/transfer', { method: 'POST', body: { from, amount: val(), note: body.querySelector('#mv-note').value } });
        B.closeSheet(true); haptic('success'); toast("O'tkazildi"); await main();
      } catch (e) { toast(e.message, true); }
    });
  }

  function takeSheet(s) {
    let bucket = s.grow > 0 ? 'grow' : 'guard';
    const body = B.openSheet(`
      <h2>${ic('minus')} Jamg'armadan olish</h2>
      ${bucketPicker(bucket, 'Qaysi qismdan?')}
      <p class="muted small" id="tk-hint"></p>
      <label class="field money"><input class="input" id="tk-amt" inputmode="numeric" placeholder="0"></label>
      <label class="field"><span>Nima uchun?</span><input class="input" id="tk-note" maxlength="200" placeholder="Masalan: davolanish"></label>
      <p class="tip">${ic('bulb')} Qo'riqchi pul — faqat og'ir kun uchun. Olingan pul bu oyning «qolgan pul»iga qo'shiladi.</p>
      <button class="btn orange big" id="tk-go">Olish</button>`);
    const hint = () => { body.querySelector('#tk-hint').textContent = `Hozir: ${som(s[bucket])}`; };
    body.querySelectorAll('[data-b]').forEach((b) => {
      b.onclick = () => { bucket = b.dataset.b; body.querySelectorAll('[data-b]').forEach((x) => x.classList.toggle('active', x === b)); hint(); };
    });
    hint();
    const val = bindMoney(body.querySelector('#tk-amt'));
    body.querySelector('#tk-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      if (!val()) { toast('Summani kiriting', true); return; }
      try {
        await api('savings/withdraw', { method: 'POST', body: { bucket, amount: val(), note: body.querySelector('#tk-note').value } });
        B.closeSheet(true); haptic('success'); toast('Olindi'); await main();
      } catch (e) { toast(e.message, true); }
    });
  }

  B.ready(main);
})();
