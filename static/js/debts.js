/* Qarzlar: ro'yxat, kredit kalkulyatori, to'lovlar, "qarzdan qutulish" rejasi (avval eng kichigi) */
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
  let tab = location.hash === '#berganlarim' ? 'lent' : 'mine';

  async function main() {
    const [d, plan] = await Promise.all([
      api('debts'),
      api(`debts/plan${planExtra != null ? `?extra=${planExtra}` : ''}`),
    ]);
    const s = d.summary;
    const targetId = plan.order.length ? plan.order[0].id : null;
    const monthly = d.debts.filter((x) => !x.closed).reduce((sum, x) => sum + (x.monthly_payment || 0), 0);
    const lentLeft = d.lent.reduce((sum, x) => sum + x.remaining, 0);
    const pendingCount = d.lent.reduce((sum, x) => sum + x.pending.length, 0);
    const showTabs = d.can_link || d.lent.length;
    if (!showTabs) tab = 'mine';

    const mine = `
      ${d.debts.map((x) => debtCard(x, x.id === targetId, d.can_link)).join('')}
      ${!d.debts.length ? `<section class="card empty"><span class="e-ico">${ic('check-circle')}</span>
        <p>Qarz yo'q — Alhamdulillah!</p></section>` : ''}
      ${plan.order.length ? planCard(plan) : ''}`;

    const page = render(`
      <section class="balance debt-balance">
        <p class="bal-label">Qolgan qarzim</p>
        <h2 class="bal-amount">${som(s.remaining)}</h2>
        <div class="progress white"><i data-w="${s.percent}"></i></div>
        <p class="bal-hint">${s.total ? `<b>${s.percent}%</b> to'landi · ${s.count_active} ta faol qarz` : "Qarz yo'q — Alhamdulillah!"}</p>
        <div class="bal-stats">
          <div><span>Jami</span><b>${compact(s.total)}</b></div>
          <div><span>To'landi</span><b>${compact(s.paid)}</b></div>
          <div><span>Oyiga</span><b>${monthly ? compact(monthly) : '—'}</b></div>
        </div>
      </section>

      <nav class="quick-grid three" aria-label="Qarz amallari">
        <button type="button" class="qa" id="add-debt"><span class="qa-ico orange">${ic('plus')}</span>Qarz oldim</button>
        ${d.can_link ? `<button type="button" class="qa" id="lend-btn"><span class="qa-ico green">${ic('users')}</span>Qarz berdim</button>` : ''}
        ${plan.order.length ? `<button type="button" class="qa" id="plan-btn"><span class="qa-ico blue">${ic('target')}</span>Reja</button>` : ''}
      </nav>

      ${showTabs ? `<div class="seg tabs" role="tablist">
        <button type="button" data-tab="mine" class="${tab === 'mine' ? 'active' : ''}">Mening qarzlarim${d.debts.length ? ` · ${d.debts.length}` : ''}</button>
        <button type="button" data-tab="lent" class="${tab === 'lent' ? 'active' : ''}">Menga qarzdorlar${pendingCount ? ` <i class="dot-badge">${pendingCount}</i>` : d.lent.length ? ` · ${d.lent.length}` : ''}</button>
      </div>` : ''}

      ${tab === 'lent' ? lentSection(d.lent, d.invites, lentLeft) : mine}`);

    page.querySelectorAll('[data-tab]').forEach((b) => {
      b.onclick = () => {
        tab = b.dataset.tab;
        history.replaceState(null, '', tab === 'lent' ? '#berganlarim' : location.pathname);
        main().catch((e) => B.errorView(e, main));
      };
    });
    const planBtn = page.querySelector('#plan-btn');
    if (planBtn) {
      planBtn.onclick = async () => {
        if (tab !== 'mine') { tab = 'mine'; await main(); }
        const card = document.querySelector('.plan-card');
        if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      };
    }
    const emptyLend = page.querySelector('#lend-empty');
    if (emptyLend) emptyLend.onclick = () => lendSheet();
    page.querySelector('#add-debt').onclick = () => debtForm();
    const lendBtn = page.querySelector('#lend-btn');
    if (lendBtn) lendBtn.onclick = () => lendSheet();
    page.querySelectorAll('[data-link]').forEach((b) => {
      b.onclick = (ev) => withBusy(ev.currentTarget, async () => {
        const x = d.debts.find((y) => y.id === Number(b.dataset.link));
        try {
          const r = await api(`debts/${x.id}/invite`, { method: 'POST' });
          B.shareSheet("Qarz bergan odamga yuboring",
            `Havolani <b>${esc(x.name)}</b> qarzini bergan odamga yuboring. U botda «Tasdiqlayman» ni bossa, to'lovlaringizni u ham ko'rib turadi. Havola 7 kun amal qiladi.`,
            r.url, r.text);
        } catch (e) { toast(e.message, true); }
      });
    });
    page.querySelectorAll('[data-review]').forEach((b) => {
      b.onclick = (ev) => withBusy(ev.currentTarget, async () => {
        const ok = b.dataset.ok === '1';
        if (!ok && !(await B.confirmAsk("To'lov rad etilsa, summa qarzga qaytariladi va qarzdorga xabar boradi.", { title: "Pulni olmadingizmi?", ok: 'Rad etish', danger: true }))) return;
        try {
          const r = await api(`debts/payments/${b.dataset.review}/review`, { method: 'POST', body: { ok } });
          toast(r.message);
          await main();
        } catch (e) { toast(e.message, true); }
      });
    });
    page.querySelectorAll('[data-unlink]').forEach((b) => {
      b.onclick = () => unlinkDebt(Number(b.dataset.unlink));
    });
    page.querySelectorAll('[data-reshare]').forEach((b) => {
      const inv = d.invites.find((y) => y.id === Number(b.dataset.reshare));
      b.onclick = () => B.share(inv.url, inv.text);
    });
    page.querySelectorAll('[data-cancel-inv]').forEach((b) => {
      b.onclick = async () => {
        if (!(await B.confirmAsk('Havola ishlamay qoladi.', { title: 'Taklifni bekor qilasizmi?', ok: 'Bekor qilish', danger: true }))) return;
        try { await api(`debts/invites/${b.dataset.cancelInv}`, { method: 'DELETE' }); await main(); } catch (e) { toast(e.message, true); }
      };
    });
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

  // ------------------------------------------------------------------ qarzdan qutulish rejasi
  function planCard(p) {
    const target = p.order[0];
    let result;
    if (p.months) {
      const faster = p.months_min_only && p.months_min_only > p.months ? p.months_min_only - p.months : 0;
      result = `<div class="freedom"><span>${ic('sparkles')} Barcha qarzlardan qutulasiz</span>
        <b>${p.months} oyda</b><span>${monthName(p.free_date)}${faster ? ` · ${faster} oy tezroq` : ''}</span></div>`;
    } else {
      result = `<div class="freedom warn">${ic('alert')} Hisoblash uchun qarzlarga oylik to'lovni kiriting.</div>`;
    }
    return `<section class="card plan-card">
      <div class="card-title"><h3><span class="h-ico blue">${ic('target')}</span> Qarzdan qutulish rejasi</h3></div>
      ${result}
      <label class="field mt"><span>Har oy qo'shimcha to'layman</span>
        <div class="row"><div class="money" style="flex:1"><input class="input" id="plan-extra" inputmode="numeric" value="${p.extra}"></div>
        <button class="btn sm" id="plan-go">Hisoblash</button></div></label>
      ${p.extra > 0 ? `<div class="tip">${ic('target')} Qo'shimcha <b>${som(p.extra)}</b> ni avval «${esc(target.name)}» ga to'lang.</div>` : ''}
      <ol class="order">${p.order.map((o) => `<li class="${o.target ? 'target' : ''}"><span class="o-main">
          <b>${o.target ? ic('target') + ' ' : ''}${esc(o.name)}</b>
          <small>${som(o.remaining)}${o.payoff_date ? ` · ${monthName(o.payoff_date)}` : ''}</small></span></li>`).join('')}</ol>
      ${p.income ? `<details class="more mt"><summary>Batafsil: pul qayerdan topiladi</summary>
        <div class="budget-lines mt">
          <div><span>Oylik daromad</span><b>${som(p.income)}</b></div>
          <div><span>O'zingizga (${p.save_percent}%)</span><b>− ${som(p.save)}</b></div>
          <div><span>Bu oy xarajatlar</span><b>− ${som(p.expense)}</b></div>
          <div><span>Minimal to'lovlar</span><b>− ${som(p.minimums_total)}</b></div>
          <div class="sum"><span>Qarzga qo'shimcha</span><b class="${p.free >= 0 ? 'c-green' : 'c-red'}">${p.free >= 0 ? '' : '− '}${som(Math.abs(p.free))}</b></div>
        </div>
        <div class="rule-box mt">
          <b>70 / 20 / 10 qoidasi</b>
          <div class="rule-bar"><i style="flex:70" class="r-home">70%</i><i style="flex:20" class="r-debt">20%</i><i style="flex:10" class="r-self">10%</i></div>
          <div class="rule-lines">
            <div><span class="dot r-home"></span>Ro'zg'orga<b>${som(p.rule_70_20_10.home)}</b></div>
            <div><span class="dot r-debt"></span>Qarzga<b>${som(p.rule_70_20_10.debt)}</b></div>
            <div><span class="dot r-self"></span>O'zingizga<b>${som(p.rule_70_20_10.self)}</b></div>
          </div>
          <button class="btn sm mt" id="rule-go">20% bilan hisoblash</button>
        </div>
      </details>` : `<div class="tip">${ic('bulb')} Aniqroq reja uchun <button class="link" id="mi-btn">daromadingizni sozlang</button>.</div>`}
    </section>`;
  }

  // ------------------------------------------------------------------ bog'langan qarzlar
  async function unlinkDebt(id) {
    if (!(await B.confirmAsk("Qarz ikkinchi tomonda yangilanmay qoladi va unga xabar boradi. Yozuvlar o'chmaydi.", { title: "Bog'lanishni uzasizmi?", ok: 'Uzish', danger: true }))) return;
    try {
      await api(`debts/${id}/unlink`, { method: 'POST' });
      B.closeSheet(true);
      toast("Bog'lanish uzildi");
      await main();
    } catch (e) { toast(e.message, true); }
  }

  /** «Menga qarzdorlar»: boshqalar tasdiqlagan, siz bergan qarzlar (faqat ko'rish + to'lovni tasdiqlash) */
  function lentSection(lent, invites, remaining) {
    if (!lent.length && !invites.length) {
      return `<section class="card empty lent-empty">
        <span class="e-ico">${ic('users')}</span>
        <p><b>Kimgadir qarz berganmisiz?</b></p>
        <p class="muted small">Yozib qo'ying va unga havola yuboring. U tasdiqlasa, qancha qaytarganini shu yerda ko'rib turasiz — eslab yurish shart emas.</p>
        <button class="btn sm mt" id="lend-empty">${ic('plus')} Qarz berdim</button>
      </section>`;
    }
    return `<section class="card">
      <div class="card-title"><h3><span class="h-ico green">${ic('users')}</span> Menga qarzdorlar</h3>${remaining ? `<span class="chip">${compact(remaining)} qoldi</span>` : ''}</div>
      ${lent.map((x) => `
        <div class="lent-item ${x.closed ? 'closed' : ''}">
          <div class="d-head">
            <span class="d-icon">${ic(x.closed ? 'check-circle' : 'users')}</span>
            <div class="d-main"><b>${esc(x.borrower)}</b><span class="muted small">${esc(x.name)}</span></div>
            <span class="pct-badge">${x.percent}%</span>
          </div>
          <div class="progress"><i data-w="${x.percent}"></i></div>
          <div class="d-nums"><span>Qaytardi: <b>${num(x.paid)}</b></span><span>Qoldi: <b>${num(x.remaining)}</b></span></div>
          ${x.pending.map((p) => `
            <div class="pending-pay">
              <span>${ic('coins')} <b>${som(p.amount)}</b> qaytardim deb yozdi. Oldingizmi?</span>
              <div class="btn-row"><button class="btn sm" data-review="${p.id}" data-ok="1">Ha, oldim</button>
                <button class="btn ghost sm" data-review="${p.id}" data-ok="0">Olmadim</button></div>
            </div>`).join('')}
          <button class="link small mt" data-unlink="${x.id}">Bog'lanishni uzish</button>
        </div>`).join('')}
      ${invites.map((v) => `
        <div class="lent-item invite">
          <div class="d-head">
            <span class="d-icon">${ic('send')}</span>
            <div class="d-main"><b>${esc(v.note)} · ${som(v.amount)}</b><span class="muted small">Tasdiq kutilmoqda</span></div>
          </div>
          <div class="btn-row"><button class="btn ghost sm" data-reshare="${v.id}">${ic('send')} Qayta yuborish</button>
            <button class="btn ghost sm" data-cancel-inv="${v.id}" style="flex:0 0 auto">Bekor qilish</button></div>
        </div>`).join('')}
    </section>`;
  }

  /** «Qarz berdim»: summa va kimga — havola yaratiladi, u tasdiqlasa qarz uning ro'yxatiga tushadi */
  function lendSheet() {
    const body = B.openSheet(`
      <h2>${ic('users')} Qarz berdim</h2>
      <p class="muted">Havola yaratamiz — uni qarz olgan odamga yuborasiz. U tasdiqlasa, qarz uning ro'yxatiga qo'shiladi va qaytargan pullarini ko'rib turasiz.</p>
      <label class="field"><span>Kimga berdingiz?</span><input class="input" id="l-note" maxlength="100" placeholder="Masalan: Jasur, telefon uchun"></label>
      <label class="field"><span>Qancha?</span><div class="money"><input class="input" id="l-amt" inputmode="numeric" placeholder="${B.ph('mid')}"></div></label>
      <button class="btn big" id="l-go">${ic('send')} Havola yaratish</button>`);
    const val = bindMoney(body.querySelector('#l-amt'));
    body.querySelector('#l-go').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const note = body.querySelector('#l-note').value.trim();
      if (!note) { toast('Kimga berganingizni yozing', true); return; }
      if (!val()) { toast('Summani kiriting', true); return; }
      try {
        const r = await api('debts/lend', { method: 'POST', body: { note, amount: val() } });
        B.shareSheet('Havola tayyor', `Havolani qarz olgan odamga yuboring (<b>${esc(note)}</b>). Tasdiqlaguncha qarz «Menga qarzdorlar» bo'limida «kutilmoqda» bo'lib turadi. Havola 7 kun amal qiladi.`, r.url, r.text, main);
      } catch (e) { toast(e.message, true); }
    });
  }

  // ------------------------------------------------------------------ qarz kartasi
  function debtCard(x, isTarget, canLink) {
    const k = KINDS[x.kind] || KINDS.other;
    const c = x.credit;
    const sub = c ? `${esc(k.label)} · yillik ${+c.interest_rate}% · ${duration(c.term_months)}` : esc(k.label);
    let creditInfo = '';
    if (c && !x.closed) {
      creditInfo = `
        <div class="dc-meta"><span>Olingan: <b>${num(c.principal)}</b></span><span>Ustama: <b>${num(Math.max(0, x.total - c.principal))}</b></span></div>
        ${c.extra_percent && c.saved > 0
          ? `<div class="win-line">${ic('sparkles')} +${c.extra_percent}% (${num(c.extra_payment)}/oy) bilan <b>${c.months_with_extra} oyda</b> tugaydi — <b>${B.compactMoney(c.saved)}</b> yutasiz</div>`
          : `<button class="link small mt" data-edit="${x.id}">${ic('sparkles')} Qo'shib to'lasam qancha yutaman?</button>`}`;
    }
    if (x.closed) {
      return `<section class="card dcard closed">
        <div class="dc-top">
          <span class="d-icon">${ic('check-circle')}</span>
          <div class="d-main"><b>${esc(x.name)}</b><span class="muted small">Yopildi · ${som(x.total)}</span></div>
          <button class="icon-btn" data-edit="${x.id}" aria-label="Tahrirlash">${ic('edit')}</button>
        </div>
      </section>`;
    }
    return `<section class="card dcard ${isTarget ? 'target' : ''}">
      ${isTarget ? `<span class="dc-flag">${ic('target')} Birinchi navbatda</span>` : ''}
      <div class="dc-top">
        <span class="d-icon">${ic(k.icon)}</span>
        <div class="d-main"><b>${esc(x.name)}</b><span class="muted small">${sub}</span></div>
        <div class="dc-amt"><b>${compact(x.remaining)}</b><small>qoldi</small></div>
      </div>
      <div class="progress orange thin"><i data-w="${x.percent}"></i></div>
      <div class="dc-meta"><span><b>${x.percent}%</b> to'landi · ${num(x.paid)} / ${num(x.total)}</span>${x.monthly_payment ? `<span>Oyiga <b>${compact(x.monthly_payment)}</b></span>` : ''}</div>
      ${x.lender ? `<p class="link-chip">${ic('users')} <span><b>${esc(x.lender)}</b> bilan bog'langan${x.pending ? ` · ${x.pending} ta to'lov tasdiq kutmoqda` : ''}</span></p>` : ''}
      ${creditInfo}
      <div class="dc-actions">
        <button class="btn orange sm" data-pay="${x.id}">${ic('coins')} To'lov</button>
        ${canLink && x.linkable ? `<button class="btn ghost sm dc-link" data-link="${x.id}" title="Qarz bergan odamga ulashish">${ic('send')} Bog'lash</button>` : ''}
        <button class="icon-btn" data-edit="${x.id}" aria-label="Tahrirlash">${ic('edit')}</button>
      </div>
    </section>`;
  }

  // ------------------------------------------------------------------ qo'shish / tahrirlash
  function debtForm(debt) {
    const isEdit = !!debt;
    const linked = !!(debt && debt.lender);
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
        <label class="field"><span>Umumiy summa</span><div class="money"><input class="input" id="d-total" inputmode="numeric" placeholder="${B.ph('mid')}" value="${isEdit && !c ? debt.total : ''}" ${linked ? 'disabled' : ''}></div></label>
        ${linked ? `<p class="muted small">${ic('users')} ${esc(debt.lender)} bilan bog'langan — summani o'zgartirish uchun avval bog'lanishni uzing.</p>` : ''}
        ${isEdit ? '' : `<label class="field"><span>Allaqachon to'langan (ixtiyoriy)</span><div class="money"><input class="input" id="d-paid" inputmode="numeric" placeholder="0"></div></label>`}
        <label class="field"><span>Oylik to'lov (ixtiyoriy)</span><div class="money"><input class="input" id="d-monthly" inputmode="numeric" placeholder="${B.ph('small')}" value="${isEdit && !c ? debt.monthly_payment : ''}"></div></label>
      </div>

      <button class="btn orange big" id="d-save">${isEdit ? 'Saqlash' : `${ic('plus')} Qo'shish`}</button>
      ${linked ? `<button class="btn ghost block" id="d-unlink">Bog'lanishni uzish</button>`
        : isEdit ? `<button class="btn danger block" id="d-del">${ic('trash')} Qarzni o'chirish</button>` : ''}`);

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
    if (linked) $('#d-unlink').onclick = () => unlinkDebt(debt.id);
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
      ${debt.lender ? `<p class="tip">${ic('users')} <b>${esc(debt.lender)}</b> ga bot orqali xabar boradi va u pulni olganini tasdiqlaydi.</p>` : ''}
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
          haptic('success');
          B.setSheet(B.celebrate('check-circle', 'Qarz yopildi',
            `«${esc(debt.name)}» to'liq to'landi. Endi shu oylik to'lovni keyingi qarzga yo'naltiring — u tezroq yopiladi.`,
            '<button class="btn big" id="p-done">Davom etish</button>'))
            .querySelector('#p-done').onclick = () => B.closeSheet();
          B.onSheetClose(main);
        } else {
          B.closeSheet(true);
          haptic('success');
          toast(`To'lov yozildi. Qarzning ${r.debt.percent}% i to'landi`);
          await main();
        }
      } catch (e) { toast(e.message, true); }
    });
  }

  B.ready(main);
})();
