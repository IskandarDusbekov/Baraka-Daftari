/* Hisobot: oxirgi 7 / 10 / 30 kun yoki tanlangan oy bo'yicha umumiy hisob */
(() => {
  'use strict';
  const { api, esc, som, ic, render, haptic, CATS, NEEDS, MONTHS, monthKey, monthLabel } = B;

  const PERIODS = [['7', '7 kun'], ['10', '10 kun'], ['30', '30 kun'], ['month', 'Oy']];
  let period = ['7', '10', '30', 'month'].includes(location.hash.slice(1)) ? location.hash.slice(1) : '7';
  let month = monthKey();

  const dm = (iso) => { const [, m, d] = iso.split('-'); return `${d}.${m}`; };
  const shiftMonth = (key, delta) => {
    const [y, m] = key.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return monthKey(d);
  };

  function summary(r) {
    const netLabel = r.net >= 0 ? 'Ortib qoldi' : 'Kamomad';
    const change = r.change_pct === null ? ''
      : r.change_pct > 0 ? `<p class="tip">${ic('up')} Oldingi ${r.days} kunga nisbatan xarajat <b class="c-red">${r.change_pct}% ko'p</b> (${som(r.prev_expense)} edi).</p>`
        : r.change_pct < 0 ? `<p class="tip green-tip">${ic('down')} Oldingi ${r.days} kunga nisbatan xarajat <b>${-r.change_pct}% kam</b> — barakalla! (${som(r.prev_expense)} edi)</p>`
          : `<p class="tip">Oldingi ${r.days} kun bilan bir xil.</p>`;
    const m = r.month;
    return `
      <section class="card">
        <p class="muted small">${dm(r.start)} – ${dm(r.end)} · ${r.days} kun</p>
        <div class="kv mt">
          <div><span>${ic('up')} Kirim</span><b class="c-green">${som(r.income)}</b></div>
          <div><span>${ic('down')} Xarajat</span><b class="c-orange">${som(r.expense)}</b></div>
          <div><span>${ic('safe')} Jamg'armaga</span><b>${som(r.saved)}</b>${r.income ? `<small class="muted">kirimning ${r.save_rate}%</small>` : ''}</div>
          <div><span>${ic('card')} Qarzga to'landi</span><b>${som(r.debt_paid)}</b></div>
        </div>
        ${r.income ? `<div class="big-result ${r.net >= 0 ? 'green' : 'red'} mt"><span>${netLabel} (kirim − xarajat − jamg'arma)</span><b>${som(Math.abs(r.net))}</b></div>` : ''}
        ${m && m.base_income ? `<p class="muted small mt">Oy bo'yicha qolgan pul: <b>${som(m.left)}</b>${m.income_is_planned ? " (oylik bo'yicha)" : ''}</p>` : ''}
        <div class="kv mt">
          <div><span>Kuniga o'rtacha xarajat</span><b>${som(r.daily_avg)}</b></div>
          <div><span>Xarajat yozilgan kunlar</span><b>${r.days_with_entries} / ${r.days}</b></div>
        </div>
        ${change}
      </section>`;
  }

  function dailyChart(r) {
    const max = Math.max(1, ...r.daily.map((d) => d.amount));
    const step = r.daily.length > 14 ? Math.ceil(r.daily.length / 7) : 1;
    return `
      <section class="card">
        <div class="card-title"><h3>${ic('chart')} Kunlar bo'yicha xarajat</h3></div>
        <div class="day-bars">
          ${r.daily.map((d, i) => `<div class="day-bar" title="${dm(d.date)}: ${som(d.amount)}">
            <i style="height:${d.amount ? Math.max(4, Math.round((d.amount * 100) / max)) : 0}%"></i>
            <em>${i % step === 0 ? dm(d.date).slice(0, 2) : ''}</em></div>`).join('')}
        </div>
      </section>`;
  }

  function categories(r) {
    if (!r.by_category.length) return '';
    return `
      <section class="card">
        <div class="card-title"><h3>Nimalarga sarflandi</h3></div>
        <ul class="cat-report">${r.by_category.map((c) => {
          const cat = CATS[c.key] || CATS.other;
          const pct = Math.round((c.amount * 100) / r.expense);
          return `<li><span class="e-icon" style="--c:${cat.color}">${ic(cat.icon)}</span>
            <div class="cr-main"><div class="cr-top"><b>${esc(c.label)}</b><span>${som(c.amount)}</span></div>
              <div class="progress thin"><i data-w="${pct}" style="background:${cat.color}"></i></div>
              <small class="muted">${pct}% · ${c.count} ta yozuv</small></div></li>`;
        }).join('')}</ul>
      </section>`;
  }

  function needs(r) {
    const total = r.expense;
    if (!total) return '';
    const marked = ['zarur', 'kerak', 'havas'].filter((k) => r.by_need[k]);
    if (!marked.length) return '';
    return `
      <section class="card">
        <div class="card-title"><h3>Zarur · Kerak · Havas</h3></div>
        <div class="need-bar">${[...marked.map((k) => `<i style="width:${(r.by_need[k] * 100) / total}%;background:${NEEDS[k].color}"></i>`),
          r.by_need.unmarked ? `<i style="width:${(r.by_need.unmarked * 100) / total}%;background:#cbd5e1"></i>` : ''].join('')}</div>
        <div class="budget-lines">${marked.map((k) => `<div><span><b style="color:${NEEDS[k].color}">${NEEDS[k].label}</b></span>
          <b>${som(r.by_need[k])} · ${Math.round((r.by_need[k] * 100) / total)}%</b></div>`).join('')}
          ${r.by_need.unmarked ? `<div><span class="muted">Belgilanmagan</span><b class="muted">${som(r.by_need.unmarked)}</b></div>` : ''}</div>
        ${r.by_need.havas && r.by_need.havas * 100 / total > 20 ? `<p class="tip">${ic('bulb')} Havas xarajatlari ${Math.round((r.by_need.havas * 100) / total)}% — shuni qisqartirsangiz, jamg'arma tezroq o'sadi.</p>` : ''}
      </section>`;
  }

  function top(r) {
    if (!r.top.length) return '';
    return `
      <section class="card">
        <div class="card-title"><h3>Eng katta xarajatlar</h3></div>
        <ul class="entries">${r.top.map((e) => {
          const cat = CATS[e.category] || CATS.other;
          return `<li class="entry"><span class="e-icon" style="--c:${cat.color}">${ic(cat.icon)}</span>
            <span class="e-main"><b>${esc(e.note || e.label)}</b><small>${dm(e.date)} · ${esc(e.label)}</small></span>
            <span class="e-amt minus">${som(e.amount)}</span></li>`;
        }).join('')}</ul>
      </section>`;
  }

  async function main() {
    const q = period === 'month' ? `period=month&month=${month}` : `period=${period}`;
    const r = await api(`report?${q}`);
    const isCurrent = month === monthKey();
    const empty = !r.income && !r.expense && !r.saved;

    const page = render(`
      <h1 class="page-title">${ic('chart')} Hisobot</h1>
      <div class="calc-tabs" role="tablist">${PERIODS.map(([k, l]) => `<button type="button" data-p="${k}" class="${k === period ? 'active' : ''}">${l}</button>`).join('')}</div>
      ${period === 'month' ? `<div class="month-switch card">
        <button class="icon-btn" id="m-prev" aria-label="Oldingi oy">${ic('left')}</button>
        <b>${monthLabel(month)}</b>
        <button class="icon-btn" id="m-next" aria-label="Keyingi oy" ${isCurrent ? 'disabled' : ''}>${ic('right')}</button></div>` : ''}
      ${empty ? `<section class="card empty"><span class="e-ico">${ic('receipt')}</span>
        <p>Bu davrda hali yozuv yo'q. Xarajat va kirimlarni yozib boring — hisobot shu yerda paydo bo'ladi.</p>
        <a class="btn mt" href="/hamyon/">${ic('plus')} Yozuv qo'shish</a></section>`
        : `${summary(r)}${dailyChart(r)}${categories(r)}${needs(r)}${top(r)}`}`);

    page.querySelectorAll('[data-p]').forEach((b) => {
      b.onclick = () => { period = b.dataset.p; history.replaceState(null, '', `#${period}`); haptic('light'); main(); };
    });
    const prev = page.querySelector('#m-prev');
    if (prev) {
      prev.onclick = () => { month = shiftMonth(month, -1); main(); };
      page.querySelector('#m-next').onclick = () => { if (!isCurrent) { month = shiftMonth(month, 1); main(); } };
    }
  }

  B.ready(main);
})();
