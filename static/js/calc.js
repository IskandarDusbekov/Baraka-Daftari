/* Kalkulyatorlar: kredit, nasiya, qarzdan chiqish, jamg'arma maqsadi, valyuta.
   Barcha hisob brauzerning o'zida — tez ishlaydi va kirmagan mehmonlarga ham ochiq.
   Kredit formulasi credit.js (serverdagi core/services.py bilan bir xil) dan olinadi. */
(() => {
  'use strict';
  const { num, ic, haptic, bindMoney, render, digits, MONTHS } = B;

  const TABS = [
    ['kredit', 'bank', 'Kredit'],
    ['nasiya', 'cart', 'Nasiya'],
    ['qarz', 'card', 'Qarzdan chiqish'],
    ['jamgarma', 'safe', "Jamg'arma"],
    ['valyuta', 'swap', 'Valyuta'],
  ];
  const SIGN = { UZS: "so'm", USD: '$' };
  const PH = { UZS: { big: '50 000 000', mid: '2 000 000' }, USD: { big: '5 000', mid: '300' } };

  let cur = B.currency || 'UZS';
  let tab = 'kredit';
  let rate = null;
  const state = {}; // har bir kalkulyatorning kiritilgan qiymatlari (tablar almashganda yo'qolmasin)

  // ------------------------------------------------------------ yordamchilar
  const money = (n) => {
    const v = num(Math.abs(n));
    const s = n < 0 ? '−' : '';
    return cur === 'USD' ? `${s}$${v}` : `${s}${v} so'm`;
  };
  const pctOf = (input) => {
    const v = parseFloat(String(input.value).replace(',', '.'));
    return Number.isFinite(v) ? Math.min(Math.max(v, 0), 300) : 0;
  };
  const intOf = (input, max = 600) => Math.min(Number(digits(input.value)) || 0, max);
  const duration = (n) => {
    if (n < 12) return `${n} oy`;
    const y = Math.floor(n / 12);
    const m = n % 12;
    return `${y} yil${m ? ` ${m} oy` : ''}`;
  };
  const monthFrom = (n) => {
    const d = new Date();
    d.setMonth(d.getMonth() + n);
    return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  };
  const mrate = (annual) => annual / 100 / 12;

  const moneyField = (key, label, size = 'big', hint = '') => `
    <label class="field"><span>${label}</span>
      <div class="money"><input class="input" data-k="${key}" inputmode="numeric" autocomplete="off" placeholder="${PH[cur][size]}"></div>
      ${hint ? `<small class="muted small">${hint}</small>` : ''}</label>`;
  const pctField = (key, label, ph = '24') => `
    <label class="field"><span>${label}</span>
      <div class="money pct-input"><input class="input" data-k="${key}" inputmode="decimal" autocomplete="off" placeholder="${ph}" maxlength="6"></div></label>`;
  const monthsField = (key, label, chips = []) => `
    <label class="field"><span>${label}</span>
      <div class="money months-input"><input class="input" data-k="${key}" inputmode="numeric" autocomplete="off" placeholder="36" maxlength="3"></div></label>
    ${chips.length ? `<div class="quick">${chips.map((c) => `<button type="button" data-fill="${key}" data-v="${c}">${duration(c)}</button>`).join('')}</div>` : ''}`;
  const seg = (key, options) => `<div class="seg" data-seg="${key}">${options.map(([v, l]) => `<button type="button" data-v="${v}">${l}</button>`).join('')}</div>`;

  /** Kalkulyator formasini ulaydi: qiymatlar state'da saqlanadi, har o'zgarishda compute() */
  function wire(box, name, defaults, compute) {
    const s = (state[name] = state[name] || { ...defaults });
    const inputs = {};
    let ready = false; // bindMoney darhol onChange chaqiradi — hamma maydon ulanmaguncha hisoblamaymiz
    box.querySelectorAll('[data-k]').forEach((input) => {
      const k = input.dataset.k;
      inputs[k] = input;
      if (s[k] !== undefined && s[k] !== '') input.value = s[k];
      const isMoney = input.closest('.money') && !input.closest('.pct-input') && !input.closest('.months-input');
      const save = () => { s[k] = input.value; if (ready) compute(s, inputs); };
      if (isMoney) bindMoney(input, save);
      else input.addEventListener('input', () => {
        if (input.closest('.months-input')) input.value = digits(input.value).slice(0, 3);
        else input.value = input.value.replace(/[^\d.,]/g, '').slice(0, 6);
        save();
      });
    });
    box.querySelectorAll('[data-seg]').forEach((el) => {
      const k = el.dataset.seg;
      const paint = () => el.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.v === s[k]));
      el.querySelectorAll('button').forEach((b) => {
        b.onclick = () => { s[k] = b.dataset.v; paint(); haptic('light'); name === 'valyuta' ? compute(s, inputs) : renderTab(); };
      });
      paint();
    });
    box.querySelectorAll('[data-fill]').forEach((b) => {
      b.onclick = () => {
        const input = inputs[b.dataset.fill];
        input.value = b.dataset.v;
        input.dispatchEvent(new Event('input'));
        haptic('light');
      };
    });
    ready = true;
    compute(s, inputs);
    return s;
  }

  const out = (box, html) => { box.querySelector('.calc-out').innerHTML = html; B.animateBars(box); };
  const emptyOut = (text) => `<p class="calc-empty">${ic('bulb')} ${text}</p>`;

  // ------------------------------------------------------------ 1. Kredit
  function schedule(P, annual, n, type) {
    const r = mrate(annual);
    const rows = [];
    let bal = P;
    const A = type === 'diff' ? 0 : window.Credit.annuity(P, annual, n);
    const part = Math.ceil(P / n);
    for (let i = 1; i <= n && bal > 0; i += 1) {
      const interest = Math.round(bal * r);
      let principal = type === 'diff' ? Math.min(part, bal) : Math.min(A - interest, bal);
      if (i === n) principal = bal; // oxirgi oy — qoldiq to'liq yopiladi
      bal -= principal;
      rows.push({ i, pay: principal + interest, interest, principal, bal });
    }
    return rows;
  }

  function kredit(box) {
    box.innerHTML = `
      ${seg('type', [['ann', 'Annuitet (teng to\'lov)'], ['diff', 'Differensial']])}
      ${moneyField('P', 'Kredit summasi')}
      <div class="form-grid">${pctField('a', 'Yillik foiz')}${monthsField('n', 'Muddat')}</div>
      <div class="quick">${[12, 24, 36, 60].map((c) => `<button type="button" data-fill="n" data-v="${c}">${duration(c)}</button>`).join('')}</div>
      <div class="calc-out"></div>`;
    wire(box, 'kredit', { type: 'ann', extra: '0' }, (s, f) => {
      const P = Number(digits(f.P.value)) || 0;
      const a = pctOf(f.a);
      const n = intOf(f.n);
      if (!P || !n) { out(box, emptyOut('Summa, foiz va muddatni kiriting — oylik to\'lov va ortiqcha pul darhol chiqadi.')); return; }
      const rows = schedule(P, a, n, s.type);
      const total = rows.reduce((t, x) => t + x.pay, 0);
      const over = total - P;
      const other = schedule(P, a, n, s.type === 'diff' ? 'ann' : 'diff').reduce((t, x) => t + x.pay, 0) - P;
      const overPct = Math.round((over * 100) / P);
      const main = s.type === 'diff'
        ? `<div class="big-result"><span>Birinchi oy → oxirgi oy</span><b>${money(rows[0].pay)} → ${money(rows[rows.length - 1].pay)}</b></div>`
        : `<div class="big-result"><span>Har oylik to'lov</span><b>${money(rows[0].pay)}</b></div>`;
      let extraHtml = '';
      if (s.type === 'ann' && a > 0) {
        const ex = Number(s.extra) || 0;
        const c = window.Credit.calc(P, a, n, 0, ex);
        extraHtml = `
          <div class="extra-box">
            <b>${ic('target')} Har oy qo'shib to'lasam-chi?</b>
            <div class="quick">${[0, 10, 20, 30, 50].map((p) => `<button type="button" data-extra="${p}" class="${p === ex ? 'active' : ''}">${p ? `+${p}%` : "Yo'q"}</button>`).join('')}</div>
            ${ex && c.monthsSaved > 0 ? `<p>Har oy <b>${money(c.extraPayment)}</b> to'lasangiz, kredit <b>${duration(c.monthsExtra)}</b> da yopiladi —
              <b class="c-green">${duration(c.monthsSaved)} oldin</b> va <b class="c-green">${money(c.saved)} tejaysiz</b>.</p>`
              : `<p class="muted small">Oylik to'lovga ozgina qo'shsangiz, foiz kamayadi va kredit ertaroq yopiladi.</p>`}
          </div>`;
      }
      out(box, `
        ${main}
        <div class="kv">
          <div><span>Jami qaytarasiz</span><b>${money(total)}</b></div>
          <div><span>Ortiqcha (foizga)</span><b class="c-orange">${money(over)}</b></div>
          <div><span>Ortiqcha ulushi</span><b>${overPct}%</b></div>
          <div><span>Tugash vaqti</span><b>${monthFrom(n)}</b></div>
        </div>
        <div class="split-bar"><i style="width:${Math.round((P * 100) / total)}%"></i></div>
        <p class="muted small">${ic('safe')} Asosiy qarz ${Math.round((P * 100) / total)}% · ${ic('down')} foiz ${100 - Math.round((P * 100) / total)}%</p>
        ${a > 0 ? `<p class="tip">${ic('bulb')} ${s.type === 'ann'
          ? `Differensial usulda ortiqcha to'lov <b>${money(other)}</b> — <b>${money(over - other)}</b> kam. Lekin birinchi oylari to'lov kattaroq bo'ladi.`
          : `Annuitetda har oy bir xil to'laysiz, lekin ortiqcha to'lov <b>${money(other)}</b> — <b>${money(other - over)}</b> ko'p.`}</p>` : ''}
        ${extraHtml}
        <button class="btn ghost block mt" id="sch-btn">${ic('calendar')} To'lov jadvali (${rows.length} oy)</button>
        <div id="sch" hidden></div>`);
      box.querySelectorAll('[data-extra]').forEach((b) => {
        b.onclick = () => { s.extra = b.dataset.extra; haptic('light'); f.P.dispatchEvent(new Event('input')); };
      });
      box.querySelector('#sch-btn').onclick = () => {
        const el = box.querySelector('#sch');
        if (el.hidden && !el.innerHTML) {
          el.innerHTML = `<div class="sch-wrap"><table class="sch"><thead><tr><th>Oy</th><th>To'lov</th><th>Foiz</th><th>Qoldiq</th></tr></thead>
            <tbody>${rows.map((x) => `<tr><td>${x.i}</td><td>${num(x.pay)}</td><td>${num(x.interest)}</td><td>${num(x.bal)}</td></tr>`).join('')}</tbody></table></div>`;
        }
        el.hidden = !el.hidden;
      };
    });
  }

  // ------------------------------------------------------------ 2. Nasiya
  /** Nasiyaning yashirin oylik foizi: (narx − boshlang'ich) ni M × n bilan tenglashtiruvchi r (bisektsiya) */
  function nasiyaRate(financed, M, n) {
    if (M * n <= financed) return 0;
    const pv = (r) => (r === 0 ? M * n : M * (1 - (1 + r) ** -n) / r);
    let lo = 0; let hi = 1;
    for (let i = 0; i < 100; i += 1) {
      const mid = (lo + hi) / 2;
      if (pv(mid) > financed) lo = mid; else hi = mid;
    }
    return (lo + hi) / 2;
  }

  function nasiya(box) {
    box.innerHTML = `
      ${moneyField('C', 'Naqd narxi', 'mid', "Do'konda naqd pulga necha pul turadi")}
      ${moneyField('D', "Boshlang'ich to'lov (bo'lsa)", 'mid')}
      <div class="form-grid">${moneyField('M', "Oylik to'lov", 'mid')}${monthsField('n', 'Necha oy')}</div>
      <div class="quick">${[3, 6, 12, 24].map((c) => `<button type="button" data-fill="n" data-v="${c}">${duration(c)}</button>`).join('')}</div>
      <div class="calc-out"></div>`;
    wire(box, 'nasiya', {}, (s, f) => {
      const C = Number(digits(f.C.value)) || 0;
      const D = Number(digits(f.D.value)) || 0;
      const M = Number(digits(f.M.value)) || 0;
      const n = intOf(f.n);
      if (!C || !M || !n) { out(box, emptyOut("Naqd narx, oylik to'lov va muddatni kiriting — nasiyaning haqiqiy foizini ko'rasiz.")); return; }
      const total = D + M * n;
      const over = total - C;
      if (D >= C) { out(box, emptyOut("Boshlang'ich to'lov naqd narxdan kichik bo'lishi kerak.")); return; }
      if (over <= 0) {
        out(box, `<div class="big-result green"><span>Ortiqcha to'lov</span><b>Yo'q — foizsiz nasiya</b></div>
          <p class="tip">${ic('check')} Jami ${money(total)} to'laysiz — naqd narxdan oshmaydi. Shartnomadagi jarima va qo'shimcha to'lovlarni tekshiring.</p>`);
        return;
      }
      const r = nasiyaRate(C - D, M, n);
      const annual = Math.round(r * 12 * 1000) / 10;
      const effective = Math.round(((1 + r) ** 12 - 1) * 1000) / 10;
      const saveMonths = Math.ceil((C - D) / M);
      out(box, `
        <div class="big-result orange"><span>Ortiqcha to'laysiz</span><b>${money(over)}</b></div>
        <div class="kv">
          <div><span>Nasiyada jami</span><b>${money(total)}</b></div>
          <div><span>Narxdan qimmat</span><b class="c-orange">+${Math.round((over * 100) / C)}%</b></div>
          <div><span>Yillik foiz ekvivalenti</span><b class="c-red">${annual}%</b></div>
          <div><span>Samarali yillik</span><b>${effective}%</b></div>
        </div>
        <p class="tip">${ic('bulb')} Bu nasiya — yillik <b>${annual}%</b> li kredit bilan bir xil.
          ${annual > 25 ? "Bank kreditidan ham qimmat bo'lishi mumkin." : ''}
          Agar har oy <b>${money(M)}</b> ni jamg'arsangiz, <b>${duration(saveMonths)}</b> da naqd sotib olib, <b>${money(over)}</b> tejaysiz.</p>`);
    });
  }

  // ------------------------------------------------------------ 3. Qarzdan chiqish
  function payoff(B0, annual, M) {
    const r = mrate(annual);
    let bal = B0; let months = 0; let paid = 0;
    while (bal > 0.5 && months < 1200) {
      const interest = bal * r;
      if (M <= interest) return null;
      const pay = Math.min(M, bal + interest);
      bal = bal + interest - pay;
      paid += pay;
      months += 1;
    }
    return months >= 1200 ? null : { months, paid: Math.round(paid) };
  }

  function qarz(box) {
    const st = state.qarz || { mode: 'when' };
    box.innerHTML = `
      ${seg('mode', [['when', 'Qachon tugaydi?'], ['how', 'Oyiga qancha?']])}
      ${moneyField('B', 'Qarz qoldig\'i')}
      <div class="form-grid">${pctField('a', 'Yillik foiz (bo\'lmasa 0)', '0')}
        ${st.mode === 'how' ? monthsField('n', 'Necha oyda yopmoqchisiz') : moneyField('M', "Oyiga to'lay olaman", 'mid')}</div>
      <div class="calc-out"></div>`;
    wire(box, 'qarz', { mode: 'when' }, (s, f) => {
      const B0 = Number(digits(f.B.value)) || 0;
      const a = pctOf(f.a);
      if (s.mode === 'how') {
        const n = intOf(f.n);
        if (!B0 || !n) { out(box, emptyOut('Qarz va muddatni kiriting — har oy qancha to\'lash kerakligini ko\'rasiz.')); return; }
        const M = window.Credit.annuity(B0, a, n);
        out(box, `
          <div class="big-result"><span>Har oy to'lash kerak</span><b>${money(M)}</b></div>
          <div class="kv"><div><span>Jami to'laysiz</span><b>${money(M * n)}</b></div>
            <div><span>Foizga ketadi</span><b class="c-orange">${money(M * n - B0)}</b></div>
            <div><span>Qarzdan qutulasiz</span><b>${monthFrom(n)}</b></div></div>
          <p class="tip">${ic('snow')} Bir nechta qarzingiz bo'lsa, ularni <a class="link" href="/qarzlar/">Qarzlar</a> bo'limiga kiriting — qor bo'lagi usulida qaysi birini birinchi yopishni ko'rsatamiz.</p>`);
        return;
      }
      const M = Number(digits(f.M.value)) || 0;
      if (!B0 || !M) { out(box, emptyOut("Qarz va oyiga qancha to'lay olishingizni kiriting.")); return; }
      const res = payoff(B0, a, M);
      if (!res) {
        out(box, `<div class="big-result red"><span>Bu to'lov bilan</span><b>Qarz tugamaydi</b></div>
          <p class="tip">${ic('alert')} Oylik to'lov foizni ham qoplamayapti. Kamida <b>${money(Math.ceil(B0 * mrate(a)) + 1)}</b> dan ko'proq to'lash kerak.</p>`);
        return;
      }
      const faster = payoff(B0, a, Math.round(M * 1.2));
      out(box, `
        <div class="big-result green"><span>Qarzdan qutulasiz</span><b>${duration(res.months)} · ${monthFrom(res.months)}</b></div>
        <div class="kv"><div><span>Jami to'laysiz</span><b>${money(res.paid)}</b></div>
          <div><span>Foizga ketadi</span><b class="c-orange">${money(res.paid - B0)}</b></div></div>
        ${faster && faster.months < res.months ? `<p class="tip">${ic('target')} Har oy 20% ko'proq — <b>${money(Math.round(M * 1.2))}</b> to'lasangiz,
          <b>${duration(res.months - faster.months)}</b> oldin qutulasiz${a > 0 ? ` va <b>${money(res.paid - faster.paid)}</b> tejaysiz` : ''}.</p>` : ''}`);
    });
  }

  // ------------------------------------------------------------ 4. Jamg'arma maqsadi
  function goalMonths(T, S, m, annual) {
    const r = mrate(annual);
    let bal = S; let months = 0; let put = S;
    while (bal < T && months < 1200) {
      bal = bal * (1 + r) + m;
      put += m;
      months += 1;
    }
    return months >= 1200 ? null : { months, bal: Math.round(bal), profit: Math.round(bal - put) };
  }

  function jamgarma(box) {
    const st = state.jamgarma || { mode: 'when' };
    box.innerHTML = `
      ${seg('mode', [['when', 'Qachon yig\'aman?'], ['how', 'Oyiga qancha?']])}
      ${moneyField('T', 'Maqsad (uy, mashina, to\'y, hajj…)')}
      ${moneyField('S', 'Hozir bor', 'mid')}
      <div class="form-grid">
        ${st.mode === 'how' ? monthsField('n', 'Necha oyda') : moneyField('m', 'Oyiga qo\'yaman', 'mid')}
        ${pctField('a', 'Depozit foizi (bo\'lsa)', '0')}</div>
      <div class="calc-out"></div>`;
    wire(box, 'jamgarma', { mode: 'when' }, (s, f) => {
      const T = Number(digits(f.T.value)) || 0;
      const S = Number(digits(f.S.value)) || 0;
      const a = pctOf(f.a);
      const r = mrate(a);
      if (!T) { out(box, emptyOut("Maqsad summasini kiriting — reja shu yerda chiqadi.")); return; }
      if (S >= T) { out(box, `<div class="big-result green"><span>Maqsad</span><b>Allaqachon yig'ilgan!</b></div>`); return; }
      if (s.mode === 'how') {
        const n = intOf(f.n);
        if (!n) { out(box, emptyOut('Necha oyda yig\'moqchisiz?')); return; }
        const grown = S * (1 + r) ** n;
        const m = Math.max(0, Math.ceil(r ? ((T - grown) * r) / ((1 + r) ** n - 1) : (T - S) / n));
        out(box, `
          <div class="big-result green"><span>Har oy qo'yish kerak</span><b>${money(m)}</b></div>
          <div class="kv"><div><span>Maqsadga yetasiz</span><b>${monthFrom(n)}</b></div>
            <div><span>O'zingiz qo'yasiz</span><b>${money(S + m * n)}</b></div>
            ${a ? `<div><span>Foizdan keladi</span><b class="c-green">${money(Math.max(0, T - S - m * n))}</b></div>` : ''}</div>
          <p class="tip">${ic('bulb')} Avval o'zingizga to'lang: oylik tushishi bilan shu summani darhol jamg'armaga ajrating.</p>`);
        return;
      }
      const m = Number(digits(f.m.value)) || 0;
      if (!m) { out(box, emptyOut("Oyiga qancha qo'ya olishingizni kiriting.")); return; }
      const res = goalMonths(T, S, m, a);
      if (!res) { out(box, emptyOut("Bu sur'atda 100 yildan ko'proq ketadi — oylik summani oshiring.")); return; }
      const faster = goalMonths(T, S, Math.round(m * 1.2), a);
      out(box, `
        <div class="big-result green"><span>Maqsadga yetasiz</span><b>${duration(res.months)} · ${monthFrom(res.months)}</b></div>
        <div class="progress mt"><i data-w="${Math.round((S * 100) / T)}"></i></div>
        <p class="muted small">Hozir: ${Math.round((S * 100) / T)}% yig'ilgan</p>
        ${a ? `<div class="kv"><div><span>Foizdan keladi</span><b class="c-green">${money(res.profit)}</b></div></div>` : ''}
        ${faster && faster.months < res.months ? `<p class="tip">${ic('target')} Oyiga <b>${money(Math.round(m * 1.2))}</b> qo'ysangiz — <b>${duration(faster.months)}</b> da yetasiz.</p>` : ''}`);
    });
  }

  // ------------------------------------------------------------ 5. Valyuta
  function valyuta(box) {
    box.innerHTML = `
      ${seg('dir', [['uzs', "so'm → $"], ['usd', "$ → so'm"]])}
      <label class="field"><span>Summa</span><div class="money" id="vx-wrap"><input class="input" data-k="x" inputmode="numeric" autocomplete="off" placeholder="1 000 000"></div></label>
      <div class="calc-out"></div>`;
    wire(box, 'valyuta', { dir: 'uzs' }, (s, f) => {
      box.querySelector('#vx-wrap').style.setProperty('--cur', s.dir === 'uzs' ? `"so'm"` : '"$"');
      f.x.placeholder = s.dir === 'uzs' ? '1 000 000' : '100';
      const x = Number(digits(f.x.value)) || 0;
      if (!rate) { out(box, emptyOut('Markaziy bank kursi yuklanmoqda…')); return; }
      const r = rate.rate;
      const usd = x / r;
      const usdText = usd < 10000 ? usd.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/\s/g, ' ') : num(usd);
      const res = s.dir === 'uzs' ? `$${usdText}` : `${num(Math.round(x * r))} so'm`;
      out(box, `
        ${x ? `<div class="big-result"><span>${s.dir === 'uzs' ? `${num(x)} so'm` : `$${num(x)}`} =</span><b>${res}</b></div>` : ''}
        ${B.rateLine(rate)}
        <div class="kv">${[1, 100, 1000].map((d) => `<div><span>$${num(d)}</span><b>${num(Math.round(d * r))} so'm</b></div>`).join('')}
          <div><span>1 mln so'm</span><b>$${num(Math.round(1e6 / r))}</b></div></div>`);
    });
  }

  const RENDER = { kredit, nasiya, qarz, jamgarma, valyuta };

  // ------------------------------------------------------------ sahifa
  function renderTab() {
    const body = document.getElementById('calc-body');
    body.style.setProperty('--cur', `"${SIGN[cur]}"`);
    document.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    document.getElementById('cur-seg').hidden = tab === 'valyuta';
    RENDER[tab](body);
  }

  async function main() {
    const hash = location.hash.slice(1);
    if (RENDER[hash]) tab = hash;
    render(`
      <h1 class="page-title">${ic('calc')} Kalkulyatorlar</h1>
      <p class="muted">Qarz yoki nasiya olishdan oldin hisoblang: qancha ortiqcha to'laysiz va qachon qutulasiz.</p>
      <div class="calc-tabs" role="tablist">${TABS.map(([k, i, l]) => `<button type="button" role="tab" data-tab="${k}">${ic(i)}${l}</button>`).join('')}</div>
      <section class="card calc-card">
        <div class="seg cur-mini" id="cur-seg">${Object.entries(SIGN).map(([c, sgn]) => `<button type="button" data-cur="${c}">${sgn}</button>`).join('')}</div>
        <div id="calc-body"></div>
      </section>
      ${B.token ? '' : `<section class="card cta-card"><b>Hisob-kitobni har kuni yuritmoqchimisiz?</b>
        <p class="muted small">Baraka Daftari xarajat, jamg'arma va qarzlaringizni kuzatib boradi — bepul.</p>
        <a class="btn block mt" href="/">Batafsil</a></section>`}`);

    const paintCur = () => document.querySelectorAll('[data-cur]').forEach((b) => b.classList.toggle('active', b.dataset.cur === cur));
    document.querySelectorAll('[data-cur]').forEach((b) => {
      b.onclick = () => { cur = b.dataset.cur; paintCur(); haptic('light'); renderTab(); };
    });
    paintCur();
    document.querySelectorAll('[data-tab]').forEach((b) => {
      b.onclick = () => {
        tab = b.dataset.tab;
        history.replaceState(null, '', `#${tab}`);
        haptic('light');
        renderTab();
      };
    });
    renderTab();

    try {
      rate = (await B.api('rates')).rate;
      if (tab === 'valyuta') renderTab();
    } catch (e) { /* kurs bo'lmasa ham boshqa kalkulyatorlar ishlaydi */ }
  }

  B.ready(main, { isPublic: true });
})();
