/* Hamyon: oy xulosasi, tezkor tugmalar (xarajat / kirim oynalari), o'zingga to'la, diagramma, tarix */
(() => {
  'use strict';
  const { api, esc, num, som, compact, ic, toast, haptic, withBusy, bindMoney, render, CATS, SOURCES } = B;

  const params = new URLSearchParams(location.search);
  let month = /^\d{4}-\d{2}$/.test(params.get('oy') || '') ? params.get('oy') : B.monthKey();
  if (month > B.monthKey()) month = B.monthKey();
  let firstRender = true;

  const shiftMonth = (key, delta) => { const [y, m] = key.split('-').map(Number); return B.monthKey(new Date(y, m - 1 + delta, 1)); };
  const lastDayOf = (key) => { const [y, m] = key.split('-').map(Number); return `${key}-${B.pad(new Date(y, m, 0).getDate())}`; };

  async function main() {
    // 'me' — hisob valyutasi har doim serverdagidek bo'lishi uchun (api() uni o'zi sinxronlaydi)
    const [w, , rec] = await Promise.all([api(`wallet?month=${month}`), api('me'), api('recurring')]);
    const t = w.totals;
    const p = t.save_percent;
    const isCurrent = month === B.monthKey();
    const defaultDate = isCurrent ? B.todayISO() : lastDayOf(month);
    const catTotal = w.categories.reduce((s, c) => s + c.amount, 0);
    const savePct = t.should_save ? Math.round((t.saved * 100) / t.should_save) : 0;

    const page = render(`
      <section class="month-switch">
        <button class="icon-btn" data-month="-1" aria-label="Oldingi oy">${ic('left')}</button>
        <h2>${B.monthLabel(month)}</h2>
        <button class="icon-btn" data-month="1" aria-label="Keyingi oy" ${isCurrent ? 'disabled' : ''}>${ic('right')}</button>
      </section>

      <section class="totals four">
        <div class="total in"><span>${ic('up')} Daromad</span><b>${compact(t.base_income)}</b></div>
        <div class="total out"><span>${ic('down')} Xarajat</span><b>${compact(t.expense)}</b></div>
        <div class="total save"><span>${ic('safe')} Jamg'arma</span><b>${compact(t.saved)}</b></div>
        <div class="total left ${t.base_income && t.left < 0 ? 'neg' : ''}"><span>${ic('wallet')} Qoldi</span><b>${t.base_income ? compact(t.left) : '—'}</b></div>
      </section>

      <section class="add-row">
        <button class="add-btn out" id="add-exp"><span>${ic('minus')}</span>Xarajat</button>
        <button class="add-btn in" id="add-inc"><span>${ic('plus')}</span>Kirim</button>
      </section>

      ${t.should_save ? `
      <section class="card save-mini">
        <div class="card-title"><h3><span class="h-ico green">${ic('safe')}</span> O'zingizga to'lash</h3><span class="chip">${Math.min(savePct, 999)}%</span></div>
        <div class="progress"><i data-w="${savePct}"></i></div>
        <div class="save-row">
          <span class="muted small">${som(t.saved)} / ${som(t.should_save)}</span>
          ${t.saved < t.should_save
            ? `<button class="btn sm" id="save-rest">${compact(t.should_save - t.saved)} o'tkazish</button>`
            : `<span class="chip">${ic('check')} Bu oy to'landi</span>`}
        </div>
      </section>` : ''}

      ${recurringCard(rec)}

      <section class="card">
        <div class="card-title"><h3><span class="h-ico purple">${ic('pie')}</span> Pul qayerga ketmoqda?</h3></div>
        ${catTotal ? `<div class="chart-wrap">${donut(w.categories, catTotal)}
          <div class="legend">${w.categories.filter((c) => c.amount).sort((a, b) => b.amount - a.amount).map((c) => `
            <div class="legend-item"><span class="dot" style="background:${CATS[c.key].color}"></span>
              <span class="lname"><span>${esc(c.label)}</span><small class="muted">${som(c.amount)}</small></span>
              <b>${Math.round((c.amount * 100) / catTotal)}%</b></div>`).join('')}
          </div></div>`
        : `<div class="empty"><span class="e-ico">${ic('pie')}</span>Bu oy xarajat kiritilmagan</div>`}
      </section>

      ${needsCard(w.needs)}

      <section class="card" id="tarix">
        <div class="card-title"><h3><span class="h-ico gray">${ic('history')}</span> Tarix</h3><span class="muted small" id="h-count">${w.history.count} ta yozuv</span></div>
        <div class="filters">
          ${[['', 'Hammasi'], ['expense', 'Xarajat'], ['income', 'Kirim'], ['saving', "Jamg'arma"]].map(([k, l]) => `<button type="button" class="filter ${k === '' ? 'active' : ''}" data-filter="${k}">${l}</button>`).join('')}
        </div>
        <ul class="entries" id="h-list"></ul>
        <div class="empty" id="h-empty" hidden><span class="e-ico">${ic('file')}</span>Hali yozuv yo'q</div>
        <button class="btn ghost block mt" id="h-more" hidden>Ko'proq ko'rsatish</button>
      </section>`);

    setupHistory(page, w.history);

    page.querySelectorAll('[data-month]').forEach((b) => {
      b.onclick = () => {
        const next = shiftMonth(month, Number(b.dataset.month));
        if (next > B.monthKey()) return;
        month = next;
        history.replaceState(null, '', next === B.monthKey() ? location.pathname : `?oy=${next}`);
        main().catch((e) => B.errorView(e, main));
      };
    });

    const addExpense = () => B.expenseSheet(main, defaultDate);
    const addIncome = () => B.incomeSheet(p, main, defaultDate);
    page.querySelector('#add-exp').onclick = addExpense;
    page.querySelector('#add-inc').onclick = addIncome;
    const saveRest = page.querySelector('#save-rest');
    if (saveRest) saveRest.onclick = () => B.saveSheet(t.should_save - t.saved, null, 0, main);

    bindRecurring(page, rec);

    // Boshqa sahifadagi "+ Kirim" / "Xarajatni yozing" havolalaridan kelinganda kerakli oyna ochiladi
    if (firstRender) {
      const open = { '#xarajat': addExpense, '#kirim': addIncome }[location.hash];
      if (open) { history.replaceState(null, '', location.pathname + location.search); open(); }
      if (location.hash === '#doimiy') setTimeout(() => page.querySelector('#doimiy').scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
    }
    firstRender = false;
  }

  // ------------------------------------------------------------------ doimiy xarajatlar
  const HIDDEN_KEY = 'baraka_rec_hidden'; // foydalanuvchi "kerak emas" degan takliflar
  const hiddenSuggestions = () => { try { return JSON.parse(localStorage.getItem(HIDDEN_KEY) || '[]'); } catch (e) { return []; } };
  const suggestionKey = (s) => `${s.category}:${s.name.toLowerCase()}`;

  function recurringCard(rec) {
    const hidden = hiddenSuggestions();
    const sugg = rec.suggestions.filter((s) => !hidden.includes(suggestionKey(s)));
    const now = new Date();
    const nextLabel = (day) => {
      // Keyingi to'lov sanasi: bu oy yozilgan bo'lsa — kelasi oy
      const m = new Date(now.getFullYear(), now.getMonth() + (day < now.getDate() ? 1 : 0), 1).getMonth();
      return `${day}-${B.MONTHS[m].toLowerCase()}`;
    };
    const rows = rec.items.map((r) => {
      const c = CATS[r.category] || CATS.other;
      const status = !r.active ? "To'xtatilgan"
        : r.done_this_month ? `Har oy ${r.day}-kuni · bu oy yozildi`
          : `Har oy ${r.day}-kuni · keyingisi ${nextLabel(r.day)}`;
      return `<li class="entry editable ${r.active ? '' : 'off'}" data-rec="${r.id}">
        <span class="e-icon" style="--c:${c.color}">${ic(c.icon)}</span>
        <span class="e-main"><b>${esc(r.name)}</b><small>${status}</small></span>
        <span class="e-amt minus">${num(r.amount)}</span>
      </li>`;
    }).join('');
    return `<section class="card" id="doimiy">
      <div class="card-title"><h3><span class="h-ico orange">${ic('repeat')}</span> Doimiy xarajatlar</h3>
        ${rec.items.length ? `<span class="chip orange">${compact(rec.total)} / oy</span>` : ''}</div>
      ${sugg.map((s, i) => `<div class="rec-suggest">
          <span>${ic('bulb')} <b>«${esc(s.name)}»</b> — ${som(s.amount)} ${s.months} oy ketma-ket yozilgan. Har oy o'zi yozilsinmi?</span>
          <div class="btn-row"><button class="btn sm" data-sugg="${i}">Ha, doimiy qilish</button>
            <button class="btn ghost sm" data-sugg-x="${i}" style="flex:0 0 auto">Kerak emas</button></div>
        </div>`).join('')}
      ${rows ? `<ul class="entries">${rows}</ul>`
        : `<p class="muted small">Ijara, kommunal, internet kabi har oy bir xil to'lovlarni bir marta kiriting — belgilangan kuni o'zi yoziladi.
            Shunda oy boshida "majburiy to'lovlardan keyin qancha qoladi" aniq ko'rinadi.</p>`}
      <button class="btn ghost block mt" id="rec-add">${ic('plus')} Doimiy xarajat qo'shish</button>
    </section>`;
  }

  function bindRecurring(page, rec) {
    const hidden = hiddenSuggestions();
    const sugg = rec.suggestions.filter((s) => !hidden.includes(suggestionKey(s)));
    page.querySelector('#rec-add').onclick = () => B.recurringSheet(null, main);
    page.querySelectorAll('[data-rec]').forEach((li) => {
      li.onclick = () => B.recurringSheet(rec.items.find((r) => r.id === Number(li.dataset.rec)), main);
    });
    page.querySelectorAll('[data-sugg]').forEach((b) => { b.onclick = () => B.recurringSheet(null, main, sugg[Number(b.dataset.sugg)]); });
    page.querySelectorAll('[data-sugg-x]').forEach((b) => {
      b.onclick = () => {
        const list = hiddenSuggestions();
        list.push(suggestionKey(sugg[Number(b.dataset.suggX)]));
        try { localStorage.setItem(HIDDEN_KEY, JSON.stringify(list.slice(-50))); } catch (e) { /* private mode */ }
        b.closest('.rec-suggest').remove();
      };
    });
  }

  /** Tarix: 20 tadan sahifalab ("Ko'proq ko'rsatish") va turi bo'yicha filtr */
  function setupHistory(page, first) {
    const list = page.querySelector('#h-list');
    const more = page.querySelector('#h-more');
    let filter = '';
    let shown = 0;

    const byKey = {};
    const bindDel = () => {
      list.querySelectorAll('[data-del]').forEach((b) => {
        b.onclick = async (ev) => {
          ev.stopPropagation();
          if (!(await B.confirmAsk("Bu yozuv tarixdan o'chiriladi va hisob-kitob qayta hisoblanadi.", { title: "Yozuvni o'chirasizmi?", ok: "O'chirish", danger: true }))) return;
          try {
            await api(`entries/${b.dataset.del}`, { method: 'DELETE' });
            toast("O'chirildi");
            await main();
          } catch (e) { toast(e.message, true); }
        };
      });
      list.querySelectorAll('[data-edit]').forEach((row) => {
        row.onclick = () => editSheet(byKey[row.dataset.edit]);
      });
    };

    const show = (chunk, reset) => {
      if (reset) { list.innerHTML = ''; shown = 0; }
      chunk.entries.forEach((e) => { byKey[`${e.type}/${e.id}`] = e; });
      list.insertAdjacentHTML('beforeend', chunk.entries.map((e) => B.entryRow(e, true)).join(''));
      shown += chunk.entries.length;
      more.hidden = !chunk.has_more;
      page.querySelector('#h-empty').hidden = chunk.count > 0;
      page.querySelector('#h-count').textContent = `${chunk.count} ta yozuv`;
      bindDel();
    };
    const load = (offset) => api(`entries?month=${month}&type=${filter}&offset=${offset}`);

    show(first, true);
    more.onclick = (ev) => withBusy(ev.currentTarget, async () => show(await load(shown), false));
    page.querySelectorAll('[data-filter]').forEach((b) => {
      b.onclick = async () => {
        filter = b.dataset.filter;
        page.querySelectorAll('[data-filter]').forEach((x) => x.classList.toggle('active', x === b));
        try { show(await load(0), true); } catch (e) { toast(e.message, true); }
      };
    });
  }

  /** Kirim yoki xarajatni tahrirlash */
  function editSheet(e) {
    if (!e) return;
    const isExp = e.type === 'expense';
    let cat = e.category;
    let need = e.need || '';
    const body = B.openSheet(`
      <h2>${ic('edit')} ${isExp ? 'Xarajatni tahrirlash' : 'Kirimni tahrirlash'}</h2>
      ${isExp ? `<div class="cats">${Object.entries(CATS).map(([k, c]) => `<button type="button" class="cat ${k === cat ? 'active' : ''}" data-cat="${k}" style="--c:${c.color}">${ic(c.icon, 'ci')}${c.label}</button>`).join('')}</div>` : ''}
      <label class="field money"><input class="input" id="ed-amt" inputmode="numeric" value="${e.amount}"></label>
      ${isExp ? `<div class="needs">${Object.entries(B.NEEDS).map(([k, n]) => `<button type="button" class="need need-${k} ${k === need ? 'active' : ''}" data-need="${k}"><b>${n.label}</b><small>${n.hint}</small></button>`).join('')}</div>`
        : `<label class="field"><span>Manba</span><select class="input" id="ed-src">${Object.entries(SOURCES).map(([k, v]) => `<option value="${k}" ${k === e.source ? 'selected' : ''}>${v}</option>`).join('')}</select></label>`}
      <div class="form-grid">
        <label class="field"><span>Izoh</span><input class="input" id="ed-note" maxlength="200" value="${esc(e.note)}"></label>
        <label class="field"><span>Sana</span><input class="input" type="date" id="ed-date" value="${e.date}" max="${B.todayISO()}"></label>
      </div>
      <button class="btn ${isExp ? 'orange' : ''} big" id="ed-save">${ic('check')} Saqlash</button>
      <button class="btn danger block" id="ed-del">${ic('trash')} O'chirish</button>`);
    const $ = (s) => body.querySelector(s);
    const val = bindMoney($('#ed-amt'));
    body.querySelectorAll('[data-cat]').forEach((b) => {
      b.onclick = () => { cat = b.dataset.cat; body.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('active', x === b)); };
    });
    body.querySelectorAll('[data-need]').forEach((b) => {
      b.onclick = () => {
        need = need === b.dataset.need ? '' : b.dataset.need;
        body.querySelectorAll('[data-need]').forEach((x) => x.classList.toggle('active', x.dataset.need === need));
      };
    });
    $('#ed-save').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      if (!val()) { toast('Summani kiriting', true); return; }
      const payload = { amount: val(), note: $('#ed-note').value, date: $('#ed-date').value };
      if (isExp) Object.assign(payload, { category: cat, need }); else payload.source = $('#ed-src').value;
      try {
        await api(`entries/${e.type}/${e.id}`, { method: 'POST', body: payload });
        B.closeSheet(true); haptic('success'); toast('Saqlandi'); await main();
      } catch (err) { toast(err.message, true); }
    });
    $('#ed-del').onclick = async () => {
      if (!(await B.confirmAsk("Bu yozuv tarixdan o'chiriladi va hisob-kitob qayta hisoblanadi.", { title: "Yozuvni o'chirasizmi?", ok: "O'chirish", danger: true }))) return;
      try { await api(`entries/${e.type}/${e.id}`, { method: 'DELETE' }); B.closeSheet(true); toast("O'chirildi"); await main(); } catch (err) { toast(err.message, true); }
    };
  }

  /** 2-saboq: xarajatlar Zarur / Kerak / Havas bo'yicha */
  function needsCard(n) {
    const marked = n.zarur + n.kerak + n.havas;
    if (!marked) {
      return '';
    }
    const pct = (v) => Math.round((v * 100) / marked);
    return `<section class="card">
      <div class="card-title"><h3><span class="h-ico orange">${ic('target')}</span> Zarur · Kerak · Havas</h3></div>
      <div class="need-bar">${Object.entries(B.NEEDS).map(([k, x]) => (n[k] ? `<i style="width:${pct(n[k])}%;background:${x.color}"></i>` : '')).join('')}</div>
      <div class="rule-lines">${Object.entries(B.NEEDS).map(([k, x]) => `
        <div><span class="dot" style="background:${x.color}"></span>${x.label}<b>${som(n[k])} · ${pct(n[k])}%</b></div>`).join('')}
      </div>
    </section>`;
  }

  function donut(cats, total) {
    const R = 60; const C = 2 * Math.PI * R;
    const active = cats.filter((c) => c.amount > 0);
    const gap = active.length > 1 ? 2 : 0;
    let offset = 0;
    const segs = active.map((c) => {
      const len = (c.amount / total) * C;
      const s = `<circle r="${R}" cx="80" cy="80" fill="none" stroke="${CATS[c.key].color}" stroke-width="24"
        stroke-dasharray="${Math.max(len - gap, 0.1)} ${C}" stroke-dashoffset="${-offset}"><title>${esc(c.label)}: ${som(c.amount)}</title></circle>`;
      offset += len;
      return s;
    }).join('');
    return `<svg class="donut" viewBox="0 0 160 160" role="img" aria-label="Xarajatlar diagrammasi">
      <circle r="${R}" cx="80" cy="80" fill="none" stroke="#f1f5f9" stroke-width="24"/>
      <g transform="rotate(-90 80 80)">${segs}</g>
      <text x="80" y="76" text-anchor="middle" font-size="12" fill="#64748b" font-weight="800">Jami</text>
      <text x="80" y="96" text-anchor="middle" font-size="17" fill="#1e293b" font-weight="900">${compact(total)}</text>
    </svg>`;
  }

  B.ready(main);
})();
