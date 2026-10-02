/* Kalkulyatorlar: kredit, qarzdan chiqish va narxlar (pul qadrsizlanishi).
   Barcha hisob brauzerning o'zida — tez ishlaydi va kirmagan mehmonlarga ham ochiq.
   Kredit formulasi credit.js (serverdagi core/services.py bilan bir xil) dan olinadi. */
(() => {
  'use strict';
  const { num, ic, esc, haptic, bindMoney, render, digits, MONTHS } = B;

  const TABS = [
    ['kredit', 'bank', 'Kredit'],
    ['qarz', 'card', 'Qarzdan chiqish'],
    ['narx', 'up', "Narx o'sishi"],
  ];
  // Har bir kalkulyator qaysi savolga javob beradi (foydalanuvchi to'g'ri bo'limni tanlashi uchun)
  const QUESTIONS = {
    kredit: "Kredit olsam, oyiga qancha to'layman va bankka qancha ortiqcha beraman?",
    qarz: "Qarzimdan qachon qutulaman yoki belgilangan muddatda yopish uchun oyiga qancha to'lashim kerak?",
    narx: "Narxlar oshgani uchun pulim qanchalik qadrsizlandi?",
  };
  // Ulashilgan havoladan qiymatlarni qayta tiklash uchun ruxsat etilgan maydonlar
  const SHARE_KEYS = {
    kredit: { type: ['ann', 'diff'], P: 'money', a: 'pct', n: 'months' },
    qarz: { mode: ['when', 'how'], B: 'money', a: 'pct', M: 'money', n: 'months' },
    narx: { item: 'text', y: 'year', old: 'money', now: 'money', S: 'money' },
  };
  const SIGN = { UZS: "so'm", USD: '$' };
  const PH = { UZS: { big: '50 000 000', mid: '2 000 000', small: '80 000' }, USD: { big: '5 000', mid: '300', small: '7' } };
  const THIS_YEAR = new Date().getFullYear();

  let cur = B.currency || 'UZS';
  let tab = 'kredit';
  const state = {}; // har bir kalkulyatorning kiritilgan qiymatlari (tablar almashganda yo'qolmasin)

  // ------------------------------------------------------------ yordamchilar
  const money = (n) => {
    const v = num(Math.abs(n));
    const s = n < 0 ? '−' : '';
    return cur === 'USD' ? `${s}$${v}` : `${s}${v} so'm`;
  };
  const amountOf = (input) => Number(digits(input.value)) || 0;
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
  const dec = (n) => (Math.round(n * 10) / 10).toString().replace('.', ',');

  // Maydon turlari (data-t): money — summa (1 000 000 ko'rinishida), pct — foiz, months — oy, year — yil, text — matn
  const moneyField = (key, label, size = 'big', hint = '') => `
    <label class="field"><span>${label}</span>
      <div class="money"><input class="input" data-k="${key}" data-t="money" inputmode="numeric" autocomplete="off" placeholder="${PH[cur][size]}"></div>
      ${hint ? `<small class="muted small">${hint}</small>` : ''}</label>`;
  const pctField = (key, label, ph = '24') => `
    <label class="field"><span>${label}</span>
      <div class="money pct-input"><input class="input" data-k="${key}" data-t="pct" inputmode="decimal" autocomplete="off" placeholder="${ph}" maxlength="6"></div></label>`;
  const monthsField = (key, label) => `
    <label class="field"><span>${label}</span>
      <div class="money months-input"><input class="input" data-k="${key}" data-t="months" inputmode="numeric" autocomplete="off" placeholder="36" maxlength="3"></div></label>`;
  const chips = (key, values, label) => `<div class="quick">${values.map((v) => `<button type="button" data-fill="${key}" data-v="${v}">${label(v)}</button>`).join('')}</div>`;
  const seg = (key, options) => `<div class="seg" data-seg="${key}">${options.map(([v, l]) => `<button type="button" data-v="${v}">${l}</button>`).join('')}</div>`;

  const CLEAN = {
    pct: (v) => v.replace(/[^\d.,]/g, '').slice(0, 6),
    months: (v) => digits(v).slice(0, 3),
    year: (v) => digits(v).slice(0, 4),
    text: (v) => v.slice(0, 40),
  };

  /** Kalkulyator formasini ulaydi: qiymatlar state'da saqlanadi, har o'zgarishda compute() */
  function wire(box, name, defaults, compute) {
    const s = (state[name] = { ...defaults, ...state[name] });
    const inputs = {};
    let ready = false; // bindMoney darhol onChange chaqiradi — hamma maydon ulanmaguncha hisoblamaymiz
    box.querySelectorAll('[data-k]').forEach((input) => {
      const k = input.dataset.k;
      const type = input.dataset.t;
      inputs[k] = input;
      if (s[k] !== undefined && s[k] !== '') input.value = s[k];
      const save = () => { s[k] = input.value; if (ready) compute(s, inputs); };
      if (type === 'money') {
        bindMoney(input, save);
      } else {
        input.addEventListener('input', () => {
          const clean = CLEAN[type](input.value);
          if (clean !== input.value) input.value = clean;
          save();
        });
      }
    });
    box.querySelectorAll('[data-seg]').forEach((el) => {
      const k = el.dataset.seg;
      const paint = () => el.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.v === s[k]));
      el.querySelectorAll('button').forEach((b) => {
        b.onclick = () => { s[k] = b.dataset.v; paint(); haptic('light'); renderTab(); };
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
  }

  /** Natijani chiqaradi. `share` — {text, params}: «Natijani ulashish» tugmasi uchun */
  const out = (box, html, share) => {
    box.querySelector('.calc-out').innerHTML = html
      + (share ? `<button class="btn ghost block mt" id="share-btn">${ic('send')} Natijani ulashish</button>` : '');
    B.animateBars(box);
    if (share) box.querySelector('#share-btn').onclick = () => shareResult(share);
  };
  const emptyOut = (text) => `<p class="calc-empty">${ic('bulb')} ${text}</p>`;
  const summary = (text) => `<p class="calc-summary">${text}</p>`;
  const question = (key) => `<p class="calc-q">${ic('info')} ${QUESTIONS[key]}</p>`;

  /** Havola ochilganda kalkulyator shu qiymatlar bilan to'lgan holda chiqadi */
  function shareResult({ text, params }) {
    const q = new URLSearchParams({ h: tab, cur });
    Object.entries(params).forEach(([k, v]) => { if (v !== '' && v != null) q.set(k, v); });
    B.share(`${location.origin}/kalkulyator/?${q}`, `${text}\n\nO'zingiz ham hisoblab ko'ring:`);
    haptic('light');
  }

  function prefillFromUrl() {
    const q = new URLSearchParams(location.search);
    const t = q.get('h');
    if (!SHARE_KEYS[t]) return;
    tab = t;
    if (SIGN[q.get('cur')]) cur = q.get('cur');
    const s = {};
    Object.entries(SHARE_KEYS[t]).forEach(([k, type]) => {
      const v = q.get(k);
      if (v == null) return;
      if (Array.isArray(type)) { if (type.includes(v)) s[k] = v; return; }
      if (type === 'money') { const d = digits(v).slice(0, 15); if (d) s[k] = num(d); return; }
      s[k] = (CLEAN[type] || CLEAN.text)(v);
    });
    state[t] = s;
  }

  // ------------------------------------------------------------ 1. Kredit
  const TYPE_NAME = { ann: "har oy bir xil to'lov", diff: "kamayib boradigan to'lov" };

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
      ${question('kredit')}
      ${moneyField('P', '1. Qancha kredit olmoqchisiz?')}
      <div class="form-grid">${pctField('a', '2. Bank foizi (yillik)')}${monthsField('n', '3. Necha oyga?')}</div>
      ${chips('n', [12, 24, 36, 60], duration)}
      <p class="field-hint">${ic('info')} Foiz shartnomada «yillik foiz stavkasi» deb yoziladi. Muddatni oyda kiriting: 3 yil = 36 oy.</p>
      <div>
        <span class="field-label">4. To'lov turi</span>
        ${seg('type', [['ann', "Har oy bir xil"], ['diff', "Kamayib boradi"]])}
        <p class="field-hint" id="type-hint"></p>
      </div>
      <div class="calc-out"></div>`;
    wire(box, 'kredit', { type: 'ann', extra: '0' }, (s, f) => {
      box.querySelector('#type-hint').textContent = s.type === 'diff'
        ? "Bankda «differensial» deyiladi: boshida ko'proq, keyin har oy kamroq to'laysiz. Umumiy foiz kamroq chiqadi."
        : "Bankda «annuitet» deyiladi: oxirigacha har oy bir xil summa to'laysiz. Ko'p banklar shu turni beradi.";
      const P = amountOf(f.P);
      const a = pctOf(f.a);
      const n = intOf(f.n);
      if (!P || !n) { out(box, emptyOut("Summa, foiz va muddatni kiriting — oylik to'lov va ortiqcha pul darhol chiqadi.")); return; }
      const rows = schedule(P, a, n, s.type);
      const total = rows.reduce((t, x) => t + x.pay, 0);
      const over = total - P;
      const other = schedule(P, a, n, s.type === 'diff' ? 'ann' : 'diff').reduce((t, x) => t + x.pay, 0) - P;
      const principalShare = Math.round((P * 100) / total);
      const main = s.type === 'diff'
        ? `<div class="big-result"><span>Birinchi oy → oxirgi oy</span><b>${money(rows[0].pay)} → ${money(rows[rows.length - 1].pay)}</b></div>`
        : `<div class="big-result"><span>Har oy to'laysiz</span><b>${money(rows[0].pay)}</b></div>`;
      let extraHtml = '';
      if (s.type === 'ann' && a > 0) {
        const ex = Number(s.extra) || 0;
        const c = window.Credit.calc(P, a, n, 0, ex);
        extraHtml = `
          <div class="extra-box">
            <b>${ic('target')} Har oy ozgina ko'proq to'lasam-chi?</b>
            <div class="quick">${[0, 10, 20, 30, 50].map((p) => `<button type="button" data-extra="${p}" class="${p === ex ? 'active' : ''}">${p ? `+${p}%` : "Yo'q"}</button>`).join('')}</div>
            ${ex && c.monthsSaved > 0 ? `<p>Har oy <b>${money(c.extraPayment)}</b> to'lasangiz, kredit <b>${duration(c.monthsExtra)}</b> da yopiladi —
              <b class="c-green">${duration(c.monthsSaved)} oldin</b> va <b class="c-green">${money(c.saved)} tejaysiz</b>.</p>`
              : `<p class="muted small">Oylik to'lovga ozgina qo'shsangiz, foiz kamayadi va kredit ertaroq yopiladi.</p>`}
          </div>`;
      }
      const payText = s.type === 'diff' ? `${money(rows[0].pay)} dan ${money(rows[rows.length - 1].pay)} gacha` : money(rows[0].pay);
      out(box, `
        ${summary(`<b>${money(P)}</b> kreditni ${duration(n)}ga olsangiz, bankka jami <b>${money(total)}</b> qaytarasiz —
          shundan <b class="c-orange">${money(over)}</b> bankning foizi.`)}
        ${main}
        <div class="kv">
          <div><span>Jami qaytarasiz</span><b>${money(total)}</b></div>
          <div><span>Ortiqcha (foizga)</span><b class="c-orange">${money(over)}</b></div>
          <div><span>Ortiqcha ulushi</span><b>${Math.round((over * 100) / P)}%</b></div>
          <div><span>Tugash vaqti</span><b>${monthFrom(n)}</b></div>
        </div>
        <div class="split-bar"><i style="width:${principalShare}%"></i></div>
        <p class="muted small">${ic('safe')} Olgan pulingiz ${principalShare}% · ${ic('down')} foiz ${100 - principalShare}%</p>
        ${a > 0 ? `<p class="tip">${ic('bulb')} «${TYPE_NAME[s.type === 'ann' ? 'diff' : 'ann']}» usulida ortiqcha to'lov <b>${money(other)}</b> —
          ${s.type === 'ann'
            ? `<b>${money(over - other)}</b> kam, lekin birinchi oylari to'lov kattaroq bo'ladi.`
            : `<b>${money(other - over)}</b> ko'p, lekin har oy bir xil to'laysiz.`}</p>` : ''}
        ${extraHtml}
        <button class="btn ghost block mt" id="sch-btn">${ic('calendar')} Oyma-oy to'lov jadvali (${rows.length} oy)</button>
        <div id="sch" hidden></div>`, {
        text: `Kredit: ${money(P)}, yillik ${f.a.value || 0}%, ${duration(n)}.\nOyiga: ${payText}.\nJami qaytariladi: ${money(total)} — bankka ortiqcha ${money(over)} (${Math.round((over * 100) / P)}%).`,
        params: { type: s.type, P, a: f.a.value, n },
      });
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

  // ------------------------------------------------------------ 2. Qarzdan chiqish
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
      ${question('qarz')}
      <div>
        <span class="field-label">Nimani bilmoqchisiz?</span>
        ${seg('mode', [['when', 'Qachon tugaydi?'], ['how', 'Oyiga qancha?']])}
      </div>
      ${moneyField('B', "1. Qancha qarzingiz qoldi?")}
      ${st.mode === 'how'
        ? `<div class="form-grid">${pctField('a', '2. Yillik foiz', '0')}${monthsField('n', '3. Necha oyda yopasiz?')}</div>`
        : `${moneyField('M', "2. Oyiga qancha to'lay olasiz?", 'mid')}${pctField('a', '3. Yillik foiz', '0')}`}
      <p class="field-hint">${ic('info')} Tanishdan olingan yoki nasiya qarzda foiz bo'lmaydi — 0 qoldiring.</p>
      <div class="calc-out"></div>`;
    wire(box, 'qarz', { mode: 'when' }, (s, f) => {
      const B0 = amountOf(f.B);
      const a = pctOf(f.a);
      if (s.mode === 'how') {
        const n = intOf(f.n);
        if (!B0 || !n) { out(box, emptyOut("Qarz va muddatni kiriting — har oy qancha to'lash kerakligini ko'rasiz.")); return; }
        const M = window.Credit.annuity(B0, a, n);
        out(box, `
          ${summary(`<b>${money(B0)}</b> qarzni ${duration(n)}da yopish uchun har oy <b>${money(M)}</b> to'lashingiz kerak.`)}
          <div class="big-result"><span>Har oy to'lash kerak</span><b>${money(M)}</b></div>
          <div class="kv"><div><span>Jami to'laysiz</span><b>${money(M * n)}</b></div>
            <div><span>Foizga ketadi</span><b class="c-orange">${money(M * n - B0)}</b></div>
            <div><span>Qarzdan qutulasiz</span><b>${monthFrom(n)}</b></div></div>
          <p class="tip">${ic('target')} Bir nechta qarzingiz bo'lsa, ularni <a class="link" href="/qarzlar/">Qarzlar</a> bo'limiga kiriting — qaysi birini birinchi yopishni ko'rsatamiz.</p>`, {
          text: `Qarz: ${money(B0)}${a ? `, yillik ${f.a.value}%` : ''}.\n${duration(n)}da yopish uchun oyiga ${money(M)} to'lash kerak (jami ${money(M * n)}).`,
          params: { mode: 'how', B: B0, a: f.a.value, n },
        });
        return;
      }
      const M = amountOf(f.M);
      if (!B0 || !M) { out(box, emptyOut("Qarz va oyiga qancha to'lay olishingizni kiriting.")); return; }
      const res = payoff(B0, a, M);
      if (!res) {
        out(box, `<div class="big-result red"><span>Bu to'lov bilan</span><b>Qarz tugamaydi</b></div>
          <p class="tip">${ic('alert')} Oylik to'lov foizni ham qoplamayapti. Kamida <b>${money(Math.ceil(B0 * mrate(a)) + 1)}</b> dan ko'proq to'lash kerak.</p>`);
        return;
      }
      const faster = payoff(B0, a, Math.round(M * 1.2));
      out(box, `
        ${summary(`Oyiga <b>${money(M)}</b> to'lasangiz, <b>${money(B0)}</b> qarz <b>${duration(res.months)}</b>da —
          ${monthFrom(res.months)} gacha yopiladi.${res.paid > B0 ? ` Foizga <b class="c-orange">${money(res.paid - B0)}</b> ketadi.` : ''}`)}
        <div class="big-result green"><span>Qarzdan qutulasiz</span><b>${duration(res.months)} · ${monthFrom(res.months)}</b></div>
        <div class="kv"><div><span>Jami to'laysiz</span><b>${money(res.paid)}</b></div>
          <div><span>Foizga ketadi</span><b class="c-orange">${money(res.paid - B0)}</b></div></div>
        ${faster && faster.months < res.months ? `<p class="tip">${ic('target')} Har oy 20% ko'proq — <b>${money(Math.round(M * 1.2))}</b> to'lasangiz,
          <b>${duration(res.months - faster.months)}</b> oldin qutulasiz${a > 0 ? ` va <b>${money(res.paid - faster.paid)}</b> tejaysiz` : ''}.</p>` : ''}`, {
        text: `Qarz: ${money(B0)}${a ? `, yillik ${f.a.value}%` : ''}, oyiga ${money(M)} to'lanadi.\nQarz ${duration(res.months)}da (${monthFrom(res.months)}) yopiladi.`,
        params: { mode: 'when', B: B0, a: f.a.value, M },
      });
    });
  }

  // ------------------------------------------------------------ 3. Narxlar va pul qadri
  function narx(box) {
    box.innerHTML = `
      ${question('narx')}
      <p class="field-hint">${ic('info')} Yaxshi eslab qolgan biror narsani oling — go'sht, non, benzin. Uning o'sha yildagi va bugungi narxini yozing.</p>
      <label class="field"><span>1. Qaysi narsa? (ixtiyoriy)</span>
        <input class="input" data-k="item" data-t="text" maxlength="40" autocomplete="off" placeholder="Masalan: 1 kg go'sht"></label>
      <label class="field"><span>2. Qaysi yil?</span>
        <input class="input" data-k="y" data-t="year" inputmode="numeric" autocomplete="off" placeholder="${THIS_YEAR - 5}" maxlength="4"></label>
      ${chips('y', [1, 3, 5, 10].map((d) => THIS_YEAR - d), (y) => `${THIS_YEAR - y} yil oldin`)}
      <div class="form-grid">${moneyField('old', "3. O'sha yildagi narxi", 'small')}${moneyField('now', '4. Bugungi narxi', 'small')}</div>
      ${moneyField('S', "5. O'shanda qancha pulingiz bor edi? (ixtiyoriy)", 'mid', "Masalan, oylik maoshingiz yoki jamg'armangiz")}
      <div class="calc-out"></div>`;
    wire(box, 'narx', {}, (s, f) => {
      const item = (f.item.value || '').trim();
      const what = item ? `«${esc(item)}»` : 'bu narsa';
      const year = Number(digits(f.y.value)) || 0;
      const oldP = amountOf(f.old);
      const nowP = amountOf(f.now);
      const S = amountOf(f.S) || (cur === 'USD' ? 1000 : 1000000);
      const years = year >= 1950 && year < THIS_YEAR ? THIS_YEAR - year : 0;
      if (!oldP || !nowP) { out(box, emptyOut("O'shandagi va bugungi narxni kiriting.")); return; }
      if (f.y.value && !years) { out(box, emptyOut(`Yilni to'g'ri kiriting (masalan, ${THIS_YEAR - 5}).`)); return; }

      const growth = (nowP / oldP - 1) * 100;
      const yearly = years ? ((nowP / oldP) ** (1 / years) - 1) * 100 : 0;
      const worth = Math.round((S * oldP) / nowP);           // o'sha pul bugun qancha narsaga yetadi (o'sha paytdagi o'lchovda)
      const lostPct = Math.round((1 - oldP / nowP) * 100);    // xarid quvvati yo'qotilishi
      const needToday = Math.round((S * nowP) / oldP);        // o'sha xaridni bugun qilish uchun kerak
      const qThen = S / oldP;
      const qNow = S / nowP;
      const when = years ? `${years} yil oldin` : "O'shanda";

      if (nowP <= oldP) {
        out(box, `<div class="big-result green"><span>${what} narxi</span><b>${growth < 0 ? `${dec(-growth)}% arzonlashgan` : "O'zgarmagan"}</b></div>
          <p class="tip">${ic('check')} Bu narsa bo'yicha pulingiz qadrini yo'qotmagan.</p>`);
        return;
      }
      const shareText = `${item || 'Narx'}: ${years ? `${years} yil oldin` : "o'shanda"} ${money(oldP)}, bugun ${money(nowP)} (+${dec(growth)}%).\n`
        + `${when} ${money(S)} bugun faqat ${money(worth)}lik narsaga yetadi — pul qadri ${lostPct}% ga tushgan.`;
      out(box, `
        ${summary(`${when}gi <b>${money(S)}</b> bugun faqat <b>${money(worth)}</b>lik narsaga yetadi —
          pulingiz qadri <b class="c-red">${lostPct}%</b> ga tushgan.`)}
        <div class="big-result red"><span>${what} narxi${years ? ` ${years} yilda` : ''}</span>
          <b>+${dec(growth)}% · ${dec(nowP / oldP)} barobar</b></div>
        <div class="kv">
          ${years ? `<div><span>Yiliga o'rtacha</span><b class="c-orange">+${dec(yearly)}%</b></div>` : ''}
          <div><span>Pulingiz qadri tushdi</span><b class="c-red">−${lostPct}%</b></div>
        </div>
        <div class="worth">
          <p><b>${when} ${money(S)}</b> bilan:</p>
          <div class="worth-row"><span>${when}</span><div class="worth-bar"><i style="width:100%"></i></div><b>${dec(qThen)} ta</b></div>
          <div class="worth-row"><span>Bugun</span><div class="worth-bar now"><i style="width:${Math.max(3, Math.round((qNow / qThen) * 100))}%"></i></div><b>${dec(qNow)} ta</b></div>
          <p class="muted small">${item ? esc(item) : 'shu narsa'}dan oladi</p>
        </div>
        <p class="tip">${ic('alert')} Yo'qolgan qadr: <b>${money(S - worth)}</b>. ${when} ${money(S)}ga qilingan xaridni bugun qilish uchun <b>${money(needToday)}</b> kerak.</p>
        <p class="tip green-tip">${ic('sprout')} Shuning uchun jamg'armaning <a class="link" href="/jamgarma/">o'sadigan qismi</a>
          shunchaki uyda yotmasligi kerak: narxlar yiliga ${years ? `~${dec(yearly)}%` : ''} o'ssa, pul ham kamida shuncha o'sadigan joyda tursin.</p>`, {
        text: shareText,
        params: { item, y: years ? year : '', old: oldP, now: nowP, S: amountOf(f.S) || '' },
      });
    });
  }

  const RENDER = { kredit, qarz, narx };

  // ------------------------------------------------------------ sahifa
  function renderTab() {
    const body = document.getElementById('calc-body');
    body.style.setProperty('--cur', `"${SIGN[cur]}"`);
    document.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    RENDER[tab](body);
  }

  async function main() {
    const hash = location.hash.slice(1);
    if (RENDER[hash]) tab = hash;
    prefillFromUrl();
    render(`
      <h1 class="page-title">${ic('calc')} Kalkulyatorlar</h1>
      <p class="muted">Muhim moliyaviy qarordan oldin hisoblab ko'ring. Hisob shu qurilmada bajariladi — hech qayerga yuborilmaydi.</p>
      <div class="calc-tabs" role="tablist">${TABS.map(([k, i, l]) => `<button type="button" role="tab" data-tab="${k}">${ic(i)}${l}</button>`).join('')}</div>
      <section class="card calc-card">
        <div class="seg cur-mini" id="cur-seg">${Object.entries(SIGN).map(([c, sgn]) => `<button type="button" data-pick-cur="${c}">${sgn}</button>`).join('')}</div>
        <div id="calc-body"></div>
      </section>
      ${B.token ? '' : `<section class="card cta-card"><b>Hisob-kitobni har kuni yuritmoqchimisiz?</b>
        <p class="muted small">Baraka Daftari xarajat, jamg'arma va qarzlaringizni kuzatib boradi — bepul.</p>
        <a class="btn block mt" href="/">Batafsil</a></section>`}`);

    // Diqqat: <html> ning o'zida data-cur atributi bor (common.js), shuning uchun bu yerda data-pick-cur
    const curBtns = document.querySelectorAll('#cur-seg [data-pick-cur]');
    const paintCur = () => curBtns.forEach((b) => b.classList.toggle('active', b.dataset.pickCur === cur));
    curBtns.forEach((b) => {
      b.onclick = () => { cur = b.dataset.pickCur; paintCur(); haptic('light'); renderTab(); };
    });
    paintCur();
    document.querySelectorAll('[data-tab]').forEach((b) => {
      b.onclick = () => {
        tab = b.dataset.tab;
        history.replaceState(null, '', `${location.pathname}#${tab}`);
        haptic('light');
        renderTab();
      };
    });
    renderTab();
  }

  B.ready(main, { isPublic: true });
})();
