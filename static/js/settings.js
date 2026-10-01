/* Sozlamalar: valyuta, daromad, oylik majburiy xarajatlar, jamg'arma, eslatmalar, hisob */
(() => {
  'use strict';
  const { api, esc, som, ic, toast, haptic, withBusy, bindMoney, render, CATS, NEEDS } = B;
  const BOT = B.CFG.botUsername;
  const GUARD_CHOICES = [3, 4, 5, 6];

  function incomeLine(u) {
    if (u.income_type === 'salary' && u.monthly_income) {
      return `<b>Oylik: ${som(u.monthly_income)}</b><span>O'zingizga ${u.save_percent}% — ${som(Math.floor((u.monthly_income * u.save_percent) / 100))} / oy</span>`;
    }
    if (u.income_type === 'irregular') return `<b>Oylik olmayman</b><span>Har bir kirimdan ${u.save_percent}% o'zingizga</span>`;
    return '<b>Sozlanmagan</b><span>Oylik bormi yo\'qmi va necha foiz to\'lashingizni tanlang</span>';
  }

  async function main() {
    const [me, rec] = await Promise.all([api('me'), api('recurring')]);
    const u = me.user;
    const botLink = BOT ? `https://t.me/${BOT}` : '';
    const freeAfter = u.monthly_income ? u.monthly_income - Math.floor((u.monthly_income * u.save_percent) / 100) - rec.total : 0;

    const page = render(`
      <h1 class="page-title">${ic('gear')} Sozlamalar</h1>

      <section class="card" id="valyuta">
        <div class="card-title"><h3><span class="h-ico blue">${ic('coins')}</span> Hisob valyutasi</h3></div>
        <div class="cur-grid">
          ${Object.entries(B.CURRENCIES).map(([code, c]) => `
            <button type="button" class="cur-opt ${u.currency === code ? 'active' : ''}" data-cur="${code}">
              <b>${code === 'USD' ? '$' : "so'm"}</b><span>${c.label}</span></button>`).join('')}
        </div>
        ${B.rateLine(me.rate)}
      </section>

      <section class="card">
        <div class="card-title"><h3><span class="h-ico green">${ic('wallet')}</span> Daromad</h3></div>
        <div class="income-row flat">
          <div class="ir-main">${incomeLine(u)}</div>
          <button class="btn sm ${u.income_type ? 'ghost' : ''}" id="income-btn">${u.income_type ? `${ic('edit')} O'zgartirish` : 'Sozlash'}</button>
        </div>
      </section>

      <section class="card">
        <div class="card-title"><h3><span class="h-ico orange">${ic('repeat')}</span> Har oylik to'lovlar</h3></div>
        <p class="muted small">Ijara, kommunal, internet — belgilangan kuni o'zi yoziladi.</p>
        ${rec.items.length ? `<ul class="entries mt">${rec.items.map((r) => {
          const c = CATS[r.category] || CATS.other;
          return `<li class="entry ${r.active ? '' : 'off'}">
            <span class="e-icon" style="--c:${c.color}">${ic(c.icon)}</span>
            <span class="e-main"><b>${esc(r.name)}</b><small>Har oy ${r.day}-kuni${r.done_this_month ? ' · bu oy yozildi' : ''}${r.active ? '' : ' · to\'xtatilgan'}</small></span>
            <span class="e-amt minus">${som(r.amount)}</span>
            <button class="e-del" data-edit-rec="${r.id}" aria-label="Tahrirlash">${ic('edit')}</button>
          </li>`;
        }).join('')}</ul>
        <div class="budget-lines mt">
          <div class="sum"><span>Jami har oy</span><b class="c-orange">${som(rec.total)}</b></div>
          ${u.monthly_income ? `<div><span>Oylik − o'zingizga − majburiy</span><b class="${freeAfter >= 0 ? 'c-green' : 'c-red'}">${som(freeAfter)}</b></div>` : ''}
        </div>` : ''}
        <button class="add-card mt" id="rec-add">${ic('plus')} Majburiy xarajat qo'shish</button>
      </section>

      <section class="card">
        <div class="card-title"><h3><span class="h-ico blue">${ic('shield')}</span> Qo'riqchi pul</h3></div>
        <p class="muted small">Og'ir kun uchun necha oylik xarajat yig'asiz?</p>
        <div class="pct-grid four mt">${GUARD_CHOICES.map((m) => `
          <button type="button" class="pct ${u.guard_months === m ? 'active' : ''}" data-guard="${m}"><b>${m} oy</b><small>${me.savings.monthly_need ? B.compact(me.savings.monthly_need * m) : ''}</small></button>`).join('')}
        </div>
        <a class="link small mt" href="/jamgarma/" style="display:inline-block">${ic('safe')} Jamg'armani ko'rish</a>
      </section>

      <section class="card">
        <div class="card-title"><h3><span class="h-ico purple">${ic('bell')}</span> Eslatmalar</h3></div>
        <div class="row between">
          <div><b>Bot eslatmalari</b><p class="muted small">Yangi saboq va kechki xarajat eslatmasi</p></div>
          <label class="switch"><input type="checkbox" id="notify" ${u.notify ? 'checked' : ''}><span></span></label>
        </div>
        ${!u.bot_started && botLink ? `<div class="tip">${ic('bulb')} Eslatmalarni olish uchun <a class="link" href="${botLink}" target="_blank" rel="noopener">@${esc(BOT)}</a> botida START tugmasini bosing.</div>` : ''}
        ${botLink ? `<a class="btn blue block mt" href="${botLink}" target="_blank" rel="noopener">${ic('send')} Botni ochish</a>` : ''}
      </section>

      <section class="card">
        <div class="card-title"><h3><span class="h-ico gray">${ic('users')}</span> Hisob</h3></div>
        <p>${esc(u.name)}${u.username ? ` <span class="muted">(@${esc(u.username)})</span>` : ''}</p>
        <button class="btn ghost block mt" id="tour">${ic('book')} Tanishtiruvni qayta ko'rish</button>
        <button class="btn ghost block mt" id="rate">${ic('star')} Ilovaga baho berish</button>
        ${B.IN_TG ? '' : `<button class="btn ghost block mt" id="logout">${ic('logout')} Chiqish</button>`}
        <button class="btn danger block mt" id="logout-all">${ic('lock')} Barcha qurilmalardan chiqish</button>
      </section>`);

    page.querySelectorAll('[data-cur]').forEach((b) => {
      b.onclick = () => { if (b.dataset.cur !== u.currency) B.currencySheet(u, main, b.dataset.cur); };
    });
    page.querySelector('#income-btn').onclick = () => B.incomeSetupSheet(u, main);
    page.querySelector('#rec-add').onclick = () => recurringSheet(null);
    page.querySelectorAll('[data-edit-rec]').forEach((b) => {
      b.onclick = () => recurringSheet(rec.items.find((r) => r.id === Number(b.dataset.editRec)));
    });
    page.querySelectorAll('[data-guard]').forEach((b) => {
      b.onclick = async () => {
        try {
          await api('me', { method: 'POST', body: { guard_months: Number(b.dataset.guard) } });
          haptic('light');
          toast(`Qo'riqchi pul: ${b.dataset.guard} oylik`);
          await main();
        } catch (e) { toast(e.message, true); }
      };
    });
    page.querySelector('#notify').onchange = async (ev) => {
      try {
        await api('me', { method: 'POST', body: { notify: ev.target.checked } });
        toast(ev.target.checked ? 'Eslatmalar yoqildi' : "Eslatmalar o'chirildi");
      } catch (e) { ev.target.checked = !ev.target.checked; toast(e.message, true); }
    };
    page.querySelector('#tour').onclick = () => B.onboardingSheet(u, main, me.rate);
    const out = page.querySelector('#logout');
    if (out) out.onclick = async () => { if (await B.confirmAsk("Qayta kirish uchun Telegram orqali tasdiqlaysiz.", { title: 'Hisobdan chiqasizmi?', ok: 'Chiqish' })) B.logout(); };
    page.querySelector('#rate').onclick = () => B.ratingModal();
    page.querySelector('#logout-all').onclick = async () => {
      const ok = await B.confirmAsk('Telegram, telefon va kompyuterdagi barcha ochiq kirishlar yopiladi. Ma\'lumotlaringiz o\'chmaydi.',
        { title: 'Barcha qurilmalardan chiqish', ok: 'Ha, chiqish', danger: true });
      if (!ok) return;
      try { await api('me/logout-all', { method: 'POST', body: {} }); toast('Barcha qurilmalardan chiqildi'); setTimeout(B.logout, 900); } catch (e) { toast(e.message, true); }
    };

    if (location.hash === '#valyuta') page.querySelector('#valyuta').scrollIntoView({ block: 'start' });
  }

  function recurringSheet(item) {
    const isEdit = !!item;
    let cat = item ? item.category : 'rent';
    let need = item ? item.need : 'zarur';
    const body = B.openSheet(`
      <h2>${isEdit ? 'Majburiy xarajat' : "Yangi majburiy xarajat"}</h2>
      <label class="field"><span>Nomi</span><input class="input" id="r-name" maxlength="100" placeholder="Masalan: Uy ijarasi" value="${isEdit ? esc(item.name) : ''}"></label>
      <label class="field"><span>Har oy summasi</span><div class="money"><input class="input" id="r-amt" inputmode="numeric" placeholder="${B.ph('mid')}" value="${isEdit ? item.amount : ''}"></div></label>
      <div><span class="field-label">Turi</span>
        <div class="cats">${Object.entries(CATS).map(([k, c]) => `<button type="button" class="cat ${k === cat ? 'active' : ''}" data-cat="${k}" style="--c:${c.color}">${ic(c.icon, 'ci')}${c.label}</button>`).join('')}</div>
      </div>
      <div><span class="field-label">Bu xarajat qanday?</span>
        <div class="needs">${Object.entries(NEEDS).map(([k, n]) => `<button type="button" class="need need-${k} ${k === need ? 'active' : ''}" data-need="${k}"><b>${n.label}</b><small>${n.hint}</small></button>`).join('')}</div>
      </div>
      <label class="field"><span>Oyning qaysi kuni to'lanadi? (1–28)</span><input class="input" id="r-day" inputmode="numeric" maxlength="2" value="${isEdit ? item.day : 1}"></label>
      ${isEdit ? `<label class="check"><input type="checkbox" id="r-active" ${item.active ? 'checked' : ''}> Faol (har oy yozilsin)</label>` : ''}
      <button class="btn orange big" id="r-save">${isEdit ? 'Saqlash' : `${ic('plus')} Qo'shish`}</button>
      ${isEdit ? `<button class="btn danger block" id="r-del">${ic('trash')} O'chirish</button>` : ''}`);
    const $ = (s) => body.querySelector(s);
    const amt = bindMoney($('#r-amt'));
    body.querySelectorAll('[data-cat]').forEach((b) => {
      b.onclick = () => { cat = b.dataset.cat; body.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('active', x === b)); };
    });
    body.querySelectorAll('[data-need]').forEach((b) => {
      b.onclick = () => { need = b.dataset.need; body.querySelectorAll('[data-need]').forEach((x) => x.classList.toggle('active', x === b)); };
    });
    $('#r-save').onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const payload = { name: $('#r-name').value.trim(), amount: amt(), category: cat, need, day: Number($('#r-day').value) || 1 };
      if (!payload.name) { toast('Nomini kiriting', true); return; }
      if (!payload.amount) { toast('Summani kiriting', true); return; }
      if ($('#r-active')) payload.active = $('#r-active').checked;
      try {
        await api(isEdit ? `recurring/${item.id}` : 'recurring', { method: 'POST', body: payload });
        B.closeSheet(true); haptic('success'); toast('Saqlandi'); await main();
      } catch (e) { toast(e.message, true); }
    });
    const del = $('#r-del');
    if (del) {
      del.onclick = async () => {
        if (!(await B.confirmAsk(`«${item.name}» endi har oy yozilmaydi. Avval yozilgan xarajatlar qoladi.`, { title: "O'chirasizmi?", ok: "O'chirish", danger: true }))) return;
        try { await api(`recurring/${item.id}`, { method: 'DELETE' }); B.closeSheet(true); toast("O'chirildi"); await main(); } catch (e) { toast(e.message, true); }
      };
    }
  }

  B.ready(main);
})();
