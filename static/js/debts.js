/* Qarzlar: ro'yxat, kredit kalkulyatori, to'lovlar, "qor bo'lagi" rejasi */
(() => {
  'use strict';
  const { api, esc, num, som, compact, ic, toast, haptic, withBusy, bindMoney, render, digits, MONTHS } = B;

  const KINDS = {
    credit: { label: 'Bank krediti', icon: 'bank' },
    personal: { label: 'Tanishdan qarz', icon: 'users' },
    nasiya: { label: 'Nasiya', icon: 'bag' },
    other: { label: 'Boshqa', icon: 'file' },
  };
  const EXTRA_CHOICES = [0, 10, 20, 30, 50];
  const monthName = (iso) => { const [y, m] = iso.split('-').map(Number); return `${MONTHS[m - 1]} ${y}`; };
  const inMonths = (n) => {
    const now = new Date();
    return `${MONTHS[(now.getMonth() + n) % 12]} ${now.getFullYear() + Math.floor((now.getMonth() + n) / 12)}`;
  };
  const duration = (m) => (m >= 12 && m % 12 === 0 ? `${m / 12} yil` : m > 12 ? `${m} oy (${Math.floor(m / 12)} yil ${m % 12} oy)` : `${m} oy`);
  let planExtra = null;

  async function main() {
    const [d, plan] = await Promise.all([
      api('debts'),
      api(`debts/plan${planExtra != null ? `?extra=${planExtra}` : ''}`),
    ]);
    const s = d.summary;
    const targetId = plan.order.length ? plan.order[0].id : null;

    const page = render(`
      <section class="card debt-hero">
        <span class="chip on-dark">${ic('snow')} Qarzdan qutulish rejasi</span>
        <p class="mt" style="opacity:.9">Qolgan qarz</p>
        <h2>${som(s.remaining)}</h2>
        <div class="progress white"><i data-w="${s.percent}"></i></div>
        <p class="small" style="opacity:.95">${s.total ? `Qarzning <b>${s.percent}%</b> i to'landi · ${s.count_active} ta faol qarz` : 'Hali qarz kiritilmagan'}</p>
      </section>

      <button class="add-card" id="add-debt">${ic('plus')} Qarz yoki kredit qo'shish</button>

      ${d.debts.map((x) => debtCard(x, x.id === targetId)).join('')}

      ${plan.order.length ? planCard(plan) : ''}

      ${!d.debts.length ? `<section class="card empty"><span class="e-ico">${ic('check-circle')}</span>
        <p>Qarzingiz yo'qmi? Alhamdulillah! Agar bo'lsa — barchasini (kredit, tanishdan qarz, nasiya) shu yerga kiriting.</p></section>` : ''}`);

    page.querySelector('#add-debt').onclick = () => debtForm();
    const miBtn = page.querySelector('#mi-btn');
    if (miBtn) miBtn.onclick = () => api('me').then((r) => B.incomeSetupSheet(r.user, main)).catch((e) => toast(e.message, true));
    page.querySelectorAll('[data-pay]').forEach((b) => {
      b.onclick = () => paySheet(d.debts.find((x) => x.id === Number(b.dataset.pay)));
    });
    page.querySelectorAll('[data-edit]').forEach((b) => {
      b.onclick = () => debtForm(d.debts.find((x) => x.id === Number(b.dataset.edit)));
    });
    const ruleBtn = page.querySelector('#rule-go');
    if (ruleBtn) {
      ruleBtn.onclick = (ev) => withBusy(ev.currentTarget, async () => {
        planExtra = plan.rule_70_20_10.debt;
        await main();
        const card = document.querySelector('.plan-card');
        if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
    const extraInput = page.querySelector('#plan-extra');
    if (extraInput) {
      const val = bindMoney(extraInput);
      page.querySelector('#plan-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
        planExtra = val();
        await main();
      });
    }
  }

  // ------------------------------------------------------------------ qor bo'lagi
  function planCard(p) {
    const target = p.order[0];
    let result;
    if (p.months) {
      const faster = p.months_min_only && p.months_min_only > p.months ? p.months_min_only - p.months : 0;
      result = `<div class="freedom"><span>${ic('sparkles')} Barcha qarzlardan qutulasiz:</span>
        <b>${p.months} oyda</b><span>${monthName(p.free_date)}</span>
        ${faster ? `<p class="small" style="margin-top:6px;opacity:.95">Faqat minimal to'lov bilan ${p.months_min_only} oy ketardi — siz ${faster} oy tezroq qutulasiz!</p>` : ''}</div>`;
    } else {
      result = `<div class="freedom warn">${ic('alert')} Hisoblab bo'lmadi. Qarzlarga oylik to'lov summasini kiriting yoki qo'shimcha summa belgilang.</div>`;
    }
    return `<section class="card plan-card">
      <div class="card-title"><h3><span class="h-ico blue">${ic('snow')}</span> Qor bo'lagi usuli</h3></div>
      <p class="muted small">Eng kichik qarzdan boshlang: qolganlariga minimal to'lov, ortgan hamma pul — eng kichigiga. U yopilgach, uning to'lovi keyingisiga qo'shiladi.</p>
      ${p.income ? `<div class="budget-lines mt">
        <div><span>Oylik daromad</span><b>${som(p.income)}</b></div>
        <div><span>O'zingizga (${p.save_percent}%)</span><b>− ${som(p.save)}</b></div>
        <div><span>Bu oy xarajatlar</span><b>− ${som(p.expense)}</b></div>
        <div><span>Minimal to'lovlar</span><b>− ${som(p.minimums_total)}</b></div>
        <div class="sum"><span>Qarzga qo'shimcha</span><b class="${p.free >= 0 ? 'c-green' : 'c-red'}">${p.free >= 0 ? '' : '− '}${som(Math.abs(p.free))}</b></div>
      </div>` : `<div class="tip">${ic('bulb')} Aniqroq reja uchun <button class="link" id="mi-btn">daromadingizni sozlang</button>.</div>`}
      ${p.income ? `<div class="rule-box mt">
        <b>${ic('book')} Sobir hojining qoidasi (4-saboq)</b>
        <p class="muted small">Qarzdor bo'lsangiz, topganingiz uch bo'lakka bo'linadi:</p>
        <div class="rule-bar"><i style="flex:70" class="r-home">70%</i><i style="flex:20" class="r-debt">20%</i><i style="flex:10" class="r-self">10%</i></div>
        <div class="rule-lines">
          <div><span class="dot r-home"></span>Ro'zg'orga<b>${som(p.rule_70_20_10.home)}</b></div>
          <p class="muted small" style="margin:-2px 0 4px 18px">Ro'zg'or — barcha uy xarajatlari: ijara, oziq-ovqat, kommunal, kiyim-kechak va boshqalar.
            Bu oy: <b class="${p.expense > p.rule_70_20_10.home ? 'c-red' : 'c-green'}">${som(p.expense)}</b>${p.expense > p.rule_70_20_10.home ? ' — chegaradan oshdi' : ''}</p>
          <div><span class="dot r-debt"></span>Qarzga qo'shimcha<b>${som(p.rule_70_20_10.debt)}</b></div>
          <div><span class="dot r-self"></span>O'zingizga<b>${som(p.rule_70_20_10.self)}</b></div>
        </div>
        <button class="btn sm mt" id="rule-go">20% ni qo'shimcha to'lov qilib hisoblash</button>
      </div>` : ''}
      <label class="field mt"><span>Har oy qarzga qo'shimcha yo'naltiraman:</span>
        <div class="row"><div class="money" style="flex:1"><input class="input" id="plan-extra" inputmode="numeric" value="${p.extra}"></div>
        <button class="btn sm" id="plan-go">Hisoblash</button></div></label>
      ${result}
      ${p.extra > 0 ? `<div class="tip">${ic('target')} <b>Tavsiya:</b> bu oy qo'shimcha <b>${som(p.extra)}</b> ni «${esc(target.name)}» qarziga yo'naltiring.</div>` : ''}
      <ol class="order">${p.order.map((o) => `<li class="${o.target ? 'target' : ''}"><span class="o-main">
          <b>${o.target ? ic('target') + ' ' : ''}${esc(o.name)}</b>
          <small>${som(o.remaining)}${o.payoff_date ? ` · ${monthName(o.payoff_date)} da yopiladi` : ''}</small></span></li>`).join('')}</ol>
    </section>`;
  }

  // ------------------------------------------------------------------ qarz kartasi
  function debtCard(x, isTarget) {
    const k = KINDS[x.kind] || KINDS.other;
    const c = x.credit;
    const sub = c ? `${esc(k.label)} · yillik ${+c.interest_rate}% · ${duration(c.term_months)}` : esc(k.label);
    let creditInfo = '';
    if (c && !x.closed) {
      creditInfo = `
        <div class="d-nums mt"><span>Olingan: <b>${num(c.principal)}</b></span><span>Ustama: <b>${num(Math.max(0, x.total - c.principal))}</b></span></div>
        ${c.extra_percent && c.saved > 0
          ? `<div class="win-line">${ic('sparkles')} +${c.extra_percent}% (${num(c.extra_payment)}/oy) bilan <b>${c.months_with_extra} oyda</b> tugaydi — <b>${B.compactMoney(c.saved)}</b> yutasiz</div>`
          : `<button class="link small mt" data-edit="${x.id}">${ic('sparkles')} Qo'shib to'lasam qancha yutaman?</button>`}`;
    }
    return `<section class="card debt-card ${x.closed ? 'closed' : ''} ${isTarget ? 'target' : ''}">
      <div class="d-head">
        <span class="d-icon">${ic(x.closed ? 'check-circle' : k.icon)}</span>
        <div class="d-main"><b>${esc(x.name)}</b><span class="muted small">${sub}${isTarget ? ' · Hozir shunga hujum!' : ''}</span></div>
        <span class="pct-badge">${x.percent}%</span>
      </div>
      <div class="progress ${x.closed ? '' : 'orange'}"><i data-w="${x.percent}"></i></div>
      <div class="d-nums"><span>To'landi: <b>${num(x.paid)}</b></span><span>Jami: <b>${num(x.total)}</b></span></div>
      ${x.closed ? `<p class="done-box mt">${ic('check-circle')} Bu qarz yopildi. Alhamdulillah!</p>
        <div class="btn-row mt"><button class="btn ghost sm" data-edit="${x.id}">${ic('edit')} Tahrirlash</button></div>` : `
      <div class="d-nums mt"><span>Qoldi: <b>${som(x.remaining)}</b></span>${x.monthly_payment ? `<span>Oyiga: <b>${num(x.monthly_payment)}</b></span>` : ''}</div>
      ${creditInfo}
      <div class="btn-row mt">
        <button class="btn orange sm" data-pay="${x.id}">${ic('coins')} To'lov qilish</button>
        <button class="btn ghost sm" data-edit="${x.id}" style="flex:0 0 auto" aria-label="Tahrirlash">${ic('edit')}</button>
      </div>`}
    </section>`;
  }

  // ------------------------------------------------------------------ qo'shish / tahrirlash
  function debtForm(debt) {
    const isEdit = !!debt;
    const c = debt && debt.credit;
    let kind = debt ? debt.kind : 'credit';
    let paidMode = 'months';
    let extra = c ? c.extra_percent : 20;
    const customExtra = !EXTRA_CHOICES.includes(extra);
    const termYears = c && c.term_months % 12 === 0;

    const body = B.openSheet(`
      <h2>${isEdit ? 'Qarzni tahrirlash' : "Yangi qarz qo'shish"}</h2>
      ${isEdit ? '' : `<div class="kind-grid">${Object.entries(KINDS).map(([key, v]) => `
        <button type="button" class="cat" data-kind="${key}">${ic(v.icon, 'ci')}${v.label}</button>`).join('')}</div>`}
      <label class="field"><span>Nomi</span><input class="input" id="d-name" maxlength="100" placeholder="Masalan: Avtokredit" value="${isEdit ? esc(debt.name) : ''}"></label>

      <div id="f-credit" class="stack">
        <label class="field"><span>Bankdan qancha oldingiz?</span><div class="money"><input class="input" id="c-principal" inputmode="numeric" placeholder="${B.ph('big')}" value="${c ? c.principal : ''}"></div></label>
        <div class="form-grid">
          <label class="field"><span>Yillik foiz</span><div class="money pct-input"><input class="input" id="c-rate" inputmode="decimal" placeholder="25" value="${c ? +c.interest_rate : ''}"></div></label>
          <label class="field"><span>Muddat</span><div class="row term-row">
            <input class="input" id="c-term" inputmode="numeric" placeholder="3" value="${c ? (termYears ? c.term_months / 12 : c.term_months) : ''}">
            <select class="input" id="c-unit"><option value="12" ${!c || termYears ? 'selected' : ''}>yil</option><option value="1" ${c && !termYears ? 'selected' : ''}>oy</option></select>
          </div></label>
        </div>
        ${isEdit ? `<p class="muted small">To'langan: <b>${som(debt.paid)}</b> — to'lovlar tarixidan olinadi.</p>` : `
        <div>
          <span class="field-label">Hozirgacha qancha to'lagansiz?</span>
          <div class="seg"><button type="button" data-paid="months">Necha oy to'ladim</button><button type="button" data-paid="amount">Qancha summa</button></div>
          <div class="money mt" id="c-paid-wrap"><input class="input" id="c-paid" inputmode="numeric" placeholder="0"></div>
        </div>`}
        <div id="c-result"></div>
        <div class="extra-box">
          <h3 class="sub-title">${ic('sparkles')} Har oy qancha qo'shib to'laysiz?</h3>
          <div class="pct-grid six">
            ${EXTRA_CHOICES.map((p) => `<button type="button" class="pct" data-extra="${p}"><b>${p ? `+${p}%` : "Yo'q"}</b><small data-extra-amt="${p}"></small></button>`).join('')}
            <button type="button" class="pct" data-extra="custom"><b>Boshqa</b><small>foiz</small></button>
          </div>
          <div class="money pct-input mt" id="c-extra-wrap" ${customExtra ? '' : 'hidden'}><input class="input" id="c-extra" inputmode="numeric" maxlength="3" placeholder="25" value="${customExtra ? extra : ''}"></div>
          <div id="c-win"></div>
        </div>
      </div>

      <div id="f-simple" class="stack">
        <label class="field"><span>Umumiy summa</span><div class="money"><input class="input" id="d-total" inputmode="numeric" placeholder="${B.ph('mid')}" value="${isEdit && !c ? debt.total : ''}"></div></label>
        ${isEdit ? '' : `<label class="field"><span>Allaqachon to'langan (ixtiyoriy)</span><div class="money"><input class="input" id="d-paid" inputmode="numeric" placeholder="0"></div></label>`}
        <label class="field"><span>Oylik to'lov (ixtiyoriy)</span><div class="money"><input class="input" id="d-monthly" inputmode="numeric" placeholder="${B.ph('small')}" value="${isEdit && !c ? debt.monthly_payment : ''}"></div></label>
      </div>

      <button class="btn orange big" id="d-save">${isEdit ? 'Saqlash' : `${ic('plus')} Qo'shish`}</button>
      ${isEdit ? `<button class="btn danger block" id="d-del">${ic('trash')} Qarzni o'chirish</button>` : ''}`);

    const $ = (sel) => body.querySelector(sel);
    const paidInput = $('#c-paid');
    let ready = false; // bindMoney darhol onChange chaqiradi — forma to'liq ulanmaguncha hisoblamaymiz
    const principalVal = bindMoney($('#c-principal'), () => { if (ready) update(); });
    const totalVal = bindMoney($('#d-total'));
    const monthlyVal = bindMoney($('#d-monthly'));
    const paidSimpleVal = $('#d-paid') ? bindMoney($('#d-paid')) : null;

    const rate = () => Math.min(200, Math.max(0, parseFloat(String($('#c-rate').value).replace(',', '.')) || 0));
    const term = () => (Number(digits($('#c-term').value)) || 0) * Number($('#c-unit').value);
    const paidValue = (payment) => {
      if (isEdit) return debt.paid;
      const v = Number(digits(paidInput.value)) || 0;
      return paidMode === 'months' ? Math.min(v, term()) * payment : v;
    };

    function update() {
      const isCredit = kind === 'credit';
      body.querySelectorAll('[data-kind]').forEach((b) => b.classList.toggle('active', b.dataset.kind === kind));
      $('#f-credit').hidden = !isCredit;
      $('#f-simple').hidden = isCredit;
      if (!isCredit) return;

      body.querySelectorAll('[data-paid]').forEach((b) => b.classList.toggle('active', b.dataset.paid === paidMode));
      if (paidInput) {
        paidInput.placeholder = paidMode === 'months' ? 'Masalan: 5' : '0';
        $('#c-paid-wrap').classList.toggle('months-input', paidMode === 'months');
      }
      const isCustom = !$('#c-extra-wrap').hidden;
      body.querySelectorAll('[data-extra]').forEach((b) => {
        b.classList.toggle('active', b.dataset.extra === 'custom' ? isCustom : !isCustom && Number(b.dataset.extra) === extra);
      });

      const P = principalVal(); const n = term(); const a = rate();
      if (!P || !n) {
        $('#c-result').innerHTML = `<p class="tip">${ic('bulb')} Summa, foiz va muddatni kiriting — bank foizi bilan jami qancha bo'lishini hisoblab beraman.</p>`;
        $('#c-win').innerHTML = '';
        body.querySelectorAll('[data-extra-amt]').forEach((s) => { s.textContent = ''; });
        return;
      }
      const r = Credit.calc(P, a, n, paidValue(Credit.annuity(P, a, n)), extra);
      body.querySelectorAll('[data-extra-amt]').forEach((s) => {
        const e = Number(s.dataset.extraAmt);
        s.textContent = e ? `+${compact(Math.floor((r.payment * e) / 100))}` : '';
      });
      const paidMonths = r.payment ? Math.floor(r.paid / r.payment) : 0;
      $('#c-result').innerHTML = `
        <div class="credit-result">
          <p>Siz <b>${som(P)}</b> olgansiz.</p>
          <p>Bank foizi bilan jami <b>${som(r.total)}</b> bo'ladi <span class="muted">(ustama: ${som(r.overpay)})</span>.</p>
          <p>Oyiga <b>${som(r.payment)}</b>dan, <b>${duration(n)}</b> to'laysiz.</p>
          ${r.paid ? `<p class="cr-paid">To'langan: <b>${som(r.paid)}</b>${paidMonths ? ` (${paidMonths} oy)` : ''} · Qoldi: <b>${som(r.remaining)}</b>, ${r.monthsLeft} oy</p>` : ''}
        </div>`;
      if (!extra) {
        $('#c-win').innerHTML = `<p class="muted small mt">Qo'shib to'lash foizini tanlang — qancha pul va vaqt yutishingizni ko'rasiz.</p>`;
      } else if (!r.monthsExtra) {
        $('#c-win').innerHTML = '';
      } else {
        const maxM = Math.max(r.monthsLeft, 1);
        $('#c-win').innerHTML = `
          <div class="win-box">
            <p>Har oy <b>+${extra}%</b> (${som(r.extraAmount)}) qo'shib, <b>${som(r.extraPayment)}</b>dan to'lasangiz:</p>
            <div class="win-big"><span>${ic('calendar')} <b>${r.monthsExtra} oyda</b> to'lab bo'lasiz${r.monthsSaved > 0 ? ` — ${r.monthsSaved} oy erta` : ''}</span>
              <span>${ic('coins')} <b>${som(r.saved)}</b> yutasiz!</span></div>
            <div class="compare">
              <div><span>Oddiy</span><i style="width:100%"></i><b>${r.monthsLeft} oy · ${compact(r.remaining)}</b></div>
              <div class="good"><span>+${extra}%</span><i style="width:${Math.round((r.monthsExtra * 100) / maxM)}%"></i><b>${r.monthsExtra} oy · ${compact(r.remainingExtra)}</b></div>
            </div>
            <p class="small muted">Tugash: ${inMonths(r.monthsExtra)} (oddiy holatda ${inMonths(r.monthsLeft)})</p>
          </div>`;
      }
    }

    body.querySelectorAll('[data-kind]').forEach((b) => { b.onclick = () => { kind = b.dataset.kind; haptic('light'); update(); }; });
    body.querySelectorAll('[data-paid]').forEach((b) => { b.onclick = () => { paidMode = b.dataset.paid; paidInput.value = ''; update(); }; });
    body.querySelectorAll('[data-extra]').forEach((b) => {
      b.onclick = () => {
        const wrap = $('#c-extra-wrap');
        if (b.dataset.extra === 'custom') {
          wrap.hidden = false;
          $('#c-extra').focus();
          extra = Number($('#c-extra').value) || extra;
        } else {
          wrap.hidden = true;
          extra = Number(b.dataset.extra);
        }
        haptic('light');
        update();
      };
    });
    $('#c-extra').addEventListener('input', (ev) => {
      ev.target.value = digits(ev.target.value).slice(0, 3);
      extra = Math.min(300, Number(ev.target.value) || 0);
      update();
    });
    ['#c-rate', '#c-term', '#c-unit'].forEach((sel) => $(sel).addEventListener('input', update));
    if (paidInput) {
      paidInput.addEventListener('input', () => {
        if (paidMode === 'amount') {
          const d = digits(paidInput.value);
          paidInput.value = d ? num(d) : '';
        } else {
          paidInput.value = digits(paidInput.value).slice(0, 3);
        }
        update();
      });
    }
    ready = true;
    update();

    $('#d-save').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const name = $('#d-name').value.trim();
      if (!name) { toast('Qarz nomini kiriting', true); return; }
      let payload;
      if (kind === 'credit') {
        if (!principalVal()) { toast('Olingan summani kiriting', true); return; }
        if (!term()) { toast('Muddatni kiriting', true); return; }
        payload = { name, kind, principal: principalVal(), interest_rate: rate(), term_months: term(), extra_percent: extra };
        if (!isEdit) {
          const v = Number(digits(paidInput.value)) || 0;
          if (paidMode === 'months') payload.paid_months = v; else payload.paid = v;
        }
      } else {
        if (!totalVal()) { toast('Umumiy summani kiriting', true); return; }
        payload = { name, kind, total: totalVal(), monthly_payment: monthlyVal() };
        if (paidSimpleVal) payload.paid = paidSimpleVal();
      }
      try {
        await api(isEdit ? `debts/${debt.id}` : 'debts', { method: 'POST', body: payload });
        B.closeSheet(true);
        haptic('success');
        toast(isEdit ? 'Saqlandi' : "Qarz ro'yxatga qo'shildi");
        await main();
      } catch (e) { toast(e.message, true); }
    });
    const del = $('#d-del');
    if (del) {
      del.onclick = async () => {
        if (!(await B.confirmAsk(`«${debt.name}» va uning to'lovlar tarixi butunlay o'chadi.`, { title: "Qarzni o'chirasizmi?", ok: "O'chirish", danger: true }))) return;
        try {
          await api(`debts/${debt.id}`, { method: 'DELETE' });
          B.closeSheet(true);
          toast("O'chirildi");
          await main();
        } catch (e) { toast(e.message, true); }
      };
    }
  }

  // ------------------------------------------------------------------ to'lov
  function paySheet(debt) {
    const c = debt.credit;
    const fullPay = c ? Credit.payoff(c.balance, c.interest_rate) : debt.remaining;
    const monthly = Math.min(debt.monthly_payment || fullPay, fullPay);
    const withExtra = c && c.extra_percent ? Math.min(c.extra_payment, fullPay) : 0;
    const suggested = withExtra || monthly;
    const body = B.openSheet(`
      <h2>To'lov: ${esc(debt.name)}</h2>
      <p class="muted">Qoldi: <b>${som(debt.remaining)}</b>${c ? ` · hozir yopish uchun: <b>${som(fullPay)}</b>` : ''}</p>
      <label class="field money"><input class="input" id="p-amt" inputmode="numeric" value="${suggested}"></label>
      <div class="btn-row wrap">
        ${debt.monthly_payment ? `<button class="btn ghost sm" data-fill="${monthly}">Oylik to'lov</button>` : ''}
        ${withExtra ? `<button class="btn ghost sm" data-fill="${withExtra}">+${c.extra_percent}% bilan</button>` : ''}
        <button class="btn ghost sm" data-fill="${fullPay}">Hammasini yopish</button>
      </div>
      ${c ? `<p class="tip">${ic('bulb')} Oylik to'lovdan ortiq summa to'liq asosiy qarzga ketadi — bank foizi kamayadi.</p>` : ''}
      <button class="btn orange big" id="p-go">To'lovni kiritish</button>`);
    const input = body.querySelector('#p-amt');
    const val = bindMoney(input);
    body.querySelectorAll('[data-fill]').forEach((b) => {
      b.onclick = () => { input.value = b.dataset.fill; input.dispatchEvent(new Event('input')); };
    });
    body.querySelector('#p-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const amount = val();
      if (!amount) { toast("To'lov summasini kiriting", true); return; }
      try {
        const r = await api(`debts/${debt.id}/pay`, { method: 'POST', body: { amount } });
        if (r.just_closed) {
          B.confetti(200);
          B.setSheet(B.celebrate('check-circle', 'Qarz yopildi!',
            `«${esc(debt.name)}» to'liq to'landi. Alhamdulillah! Endi uning to'lovini keyingi qarzga yo'naltiring — qor bo'lagi kattalashmoqda.`,
            '<button class="btn big" id="p-done">Davom etish</button>'))
            .querySelector('#p-done').onclick = () => B.closeSheet();
          B.onSheetClose(main);
        } else {
          B.closeSheet(true);
          haptic('success');
          toast(`Qarzning ${r.debt.percent}% i to'landi!`);
          await main();
        }
      } catch (e) { toast(e.message, true); }
    });
  }

  B.ready(main);
})();
