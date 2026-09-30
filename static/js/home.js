/* Asosiy sahifa (Dashboard) */
(() => {
  'use strict';
  const { api, esc, som, compact, ic, render, MONTHS } = B;

  function incomeLine(u) {
    if (u.income_type === 'salary' && u.monthly_income) {
      return `<b>Oylik: ${som(u.monthly_income)}</b>
        <span>O'zingizga ${u.save_percent}% — ${som(Math.floor((u.monthly_income * u.save_percent) / 100))} / oy</span>`;
    }
    if (u.income_type === 'irregular') {
      return `<b>Oylik olmayman</b><span>Har bir kirimdan ${u.save_percent}% o'zingizga</span>`;
    }
    return `<b>Daromad sozlanmagan</b><span>Oylik bormi yo'qmi va necha foiz to'lashingizni tanlang</span>`;
  }

  async function main() {
    const d = await api('me');
    const u = d.user;
    const L = d.lessons;
    const cur = L.current;
    const pct = L.total ? Math.round((L.done * 100) / L.total) : 0;
    const m = d.month;
    const needSave = Math.max(m.should_save - m.saved, 0);
    const monthName = MONTHS[new Date().getMonth()];

    const balance = m.base_income ? `
        <p class="bal-label">${monthName} oyida qolgan pulingiz</p>
        <h2 class="bal-amount ${m.left < 0 ? 'neg' : ''}">${m.left < 0 ? '−' : ''}${som(Math.abs(m.left))}</h2>
        ${d.rate ? `<p class="bal-other">${B.otherCurrency(m.left, d.rate)}</p>` : ''}
        <div class="progress white"><i data-w="${m.spent_percent}"></i></div>
        <p class="bal-hint">Daromadning <b>${m.spent_percent}%</b> i sarflandi${m.income_is_planned ? ' · oylik bo\'yicha' : ''}</p>
        ${m.planned_pending ? `<p class="bal-planned">${ic('repeat')} Hali to'lanadigan majburiy: <b>${som(m.planned_pending)}</b> → erkin pul:
          <b>${m.free_after_planned < 0 ? '−' : ''}${som(Math.abs(m.free_after_planned))}</b></p>` : ''}`
      : `
        <p class="bal-label">${monthName} oyida qolgan pulingiz</p>
        <h2 class="bal-amount">—</h2>
        <p class="bal-hint">${u.income_type === 'irregular'
          ? 'Bu oy hali kirim yozilmagan. Pul tushganda «+ Kirim» ni bosing.'
          : 'Qolgan pulni ko\'rish uchun daromadingizni kiriting: oylik summasini yoki birinchi kirimni.'}</p>`;

    let task;
    if (!L.total) {
      task = `<section class="card lesson-mini">
        <span class="h-ico blue">${ic('book')}</span>
        <div><b>Saboqlar tez orada</b><p class="muted small">Har hafta yangi video bilan saboq qo'shiladi — bot xabar beradi.</p></div>
      </section>`;
    } else if (cur && cur.state === 'open') {
      task = `<section class="task-card">
        <span class="chip">${ic('target')} ${cur.number}-saboq · navbatdagi vazifa</span>
        <h3>${esc(cur.task_title)}</h3>
        <p>${esc(cur.title)}</p>
        <div class="progress white thin mt"><i data-w="${pct}"></i></div>
        <p class="small mt">${L.total} ta saboqdan ${L.done} tasi bajarildi</p>
        <a class="btn white big" href="/saboqlar/${cur.number}/">Saboqni ochish ${ic('arrow')}</a>
      </section>`;
    } else {
      task = `<section class="card lesson-mini">
        <span class="h-ico green">${ic(cur ? 'check-circle' : 'trophy')}</span>
        <div><b>${cur ? 'Bugungi saboq bajarildi!' : `Barcha ${L.total} ta saboq o'tildi!`}</b>
          <p class="muted small">${cur ? `Keyingisi — «${esc(cur.title)}» ertaga ochiladi.` : 'Yangi video chiqishi bilan keyingi saboq qo\'shiladi.'}</p></div>
        <a class="icon-btn" href="/saboqlar/" aria-label="Saboqlar">${ic('right')}</a>
      </section>`;
    }

    const page = render(`
      <section class="hello">
        <div><p class="muted">Assalomu alaykum,</p><h1>${esc(u.first_name || u.name)}</h1></div>
        <div class="stars" title="Yulduzlar">${ic('star')} ${L.done * 10}</div>
      </section>

      <section class="balance">
        ${balance}
        <div class="bal-stats">
          <div><span>${ic('up')} Daromad</span><b>${compact(m.base_income)}</b></div>
          <div><span>${ic('down')} Xarajat</span><b>${compact(m.expense)}</b></div>
          <div><span>${ic('safe')} Jamg'arma</span><b>${compact(m.saved)}</b></div>
        </div>
        <div class="bal-actions">
          <button class="btn white" id="exp-btn">${ic('minus')} Xarajat</button>
          <a class="btn ghost-white" href="/hamyon/#kirim">${ic('plus')} Kirim</a>
        </div>
      </section>
      <a class="rate-chip" href="/sozlamalar/#valyuta">${B.rateLine(d.rate, ` <span class="muted">· hisob: ${B.CURRENCIES[u.currency].label.toLowerCase()}</span>`)}</a>

      ${roadCard(d.onboarding)}

      <section class="card income-row">
        <span class="h-ico green">${ic('wallet')}</span>
        <div class="ir-main">${incomeLine(u)}</div>
        <button class="btn sm ${u.income_type ? 'ghost' : ''}" id="setup-btn">${u.income_type ? ic('edit') : 'Sozlash'}</button>
      </section>

      ${needSave > 0 ? `
      <section class="card nudge">
        <span class="n-ico">${ic('coins')}</span>
        <div style="flex:1"><p>Bu oy o'zingizga yana <b>${som(needSave)}</b> to'lashingiz kerak (${m.save_percent}%).</p>
          <button class="btn sm mt" id="save-btn">Zaxiraga o'tkazish</button></div>
      </section>` : ''}

      <section class="grid2">
        <a href="/jamgarma/" class="stat green">
          <span class="stat-ico">${ic('safe')}</span>
          <span class="stat-label">Jamg'armam</span>
          <b>${som(d.reserve_total)}</b>
          <small>${ic('shield')} ${B.compact(d.savings.guard)} · ${ic('sprout')} ${B.compact(d.savings.grow)}</small>
        </a>
        <a href="/qarzlar/" class="stat orange">
          <span class="stat-ico">${ic('card')}</span>
          <span class="stat-label">Umumiy qarzlarim</span>
          <b>${som(d.debts.remaining)}</b>
          ${d.debts.total
            ? `<div class="progress thin white"><i data-w="${d.debts.percent}"></i></div><small>${d.debts.percent}% to'landi</small>`
            : '<small>Qarz kiritilmagan</small>'}
        </a>
      </section>

      ${task}

      <section class="card">
        <div class="card-title"><h3>Yutuqlarim</h3><span class="chip gold">${d.badges.filter((b) => b.earned).length}/${d.badges.length}</span></div>
        <div class="badges">
          ${d.badges.map((b) => `<div class="badge ${b.earned ? 'on' : 'off'}"><span class="bi">${ic(b.icon)}</span>${esc(b.title)}</div>`).join('')}
        </div>
      </section>`);

    page.querySelector('#exp-btn').onclick = () => B.expenseSheet(main);
    page.querySelector('#setup-btn').onclick = () => B.incomeSetupSheet(u, main);
    const saveBtn = page.querySelector('#save-btn');
    if (saveBtn) saveBtn.onclick = () => B.saveSheet(needSave, null, 0, main);

    const hideRoad = page.querySelector('#road-hide');
    if (hideRoad) {
      hideRoad.onclick = async () => {
        try { await api('me', { method: 'POST', body: { onboarding_hidden: true } }); await main(); } catch (e) { B.toast(e.message, true); }
      };
    }
    const currencyStep = page.querySelector('[data-step="currency"]');
    if (currencyStep) currencyStep.onclick = (ev) => { ev.preventDefault(); B.currencySheet(u, main); };
    const incomeStep = page.querySelector('[data-step="income"]');
    if (incomeStep) incomeStep.onclick = (ev) => { ev.preventDefault(); B.incomeSetupSheet(u, main); };

    // Birinchi kirish: tanishtiruv (yo'l xaritasi → valyuta → daromad)
    if (!u.accepted_disclaimer) B.onboardingSheet(u, main, d.rate);
    // 3-marta qaytib kirganda yoki bir necha kundan keyin — baho so'raladi (server hal qiladi)
    else B.maybeAskRating(d);
  }

  /** «Boshlash yo'li»: yangi foydalanuvchi uchun qadamlar va keyingisi */
  function roadCard(o) {
    if (!o || o.hidden || o.done >= o.total) return '';
    const pct = Math.round((o.done * 100) / o.total);
    return `<section class="card road-card">
      <div class="card-title"><h3><span class="h-ico green">${ic('target')}</span> Boshlash yo'li</h3><span class="chip">${o.done}/${o.total}</span></div>
      <div class="progress"><i data-w="${pct}"></i></div>
      <ol class="road-steps">${o.steps.map((s) => `
        <li class="${s.done ? 'done' : ''} ${s.key === o.next ? 'next' : ''}">
          <a href="${s.href}" data-step="${s.key}">
            <span class="rs-dot">${s.done ? ic('check') : ''}</span>
            <span class="rs-text"><b>${esc(s.title)}</b>${s.key === o.next ? `<small>${esc(s.hint)}</small>` : ''}</span>
            ${s.done ? '' : ic('right', 'rs-go')}
          </a></li>`).join('')}
      </ol>
      <button class="link small mt" id="road-hide">Yashirish</button>
    </section>`;
  }

  B.ready(main);
})();
