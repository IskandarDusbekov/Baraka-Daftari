/* Bitta saboq: video, qisqacha mazmun, saboqlar va "nima qilish kerak" ro'yxati */
(() => {
  'use strict';
  const { api, esc, ic, haptic, withBusy, render } = B;
  const number = B.CFG.number;
  const CHECK_KEY = `baraka_saboq_${number}_checks`;

  // Ilovadagi amal -> [sahifa, tugma matni, ikonka]
  const ACTIONS = {
    income: ['/hamyon/', 'Oylik daromadni kiritish', 'wallet'],
    expense: ['/hamyon/', 'Xarajat kiritish', 'receipt'],
    save: ['/hamyon/', "Zaxiraga o'tkazish", 'safe'],
    debt_list: ['/qarzlar/', 'Qarzlarni kiritish', 'card'],
    debt_plan: ['/qarzlar/', "Qarz rejasini ko'rish", 'snow'],
    debt_pay: ['/qarzlar/', "To'lov kiritish", 'coins'],
  };
  const NEED_PAGES = { hamyon: '/hamyon/', qarzlar: '/qarzlar/' };

  const loadChecks = () => { try { return JSON.parse(localStorage.getItem(CHECK_KEY)) || []; } catch (e) { return []; } };
  const saveChecks = (v) => { try { localStorage.setItem(CHECK_KEY, JSON.stringify(v)); } catch (e) { /* private */ } };

  async function main() {
    let l;
    try {
      ({ lesson: l } = await api(`lessons/${number}`));
    } catch (e) {
      if (e.status !== 403 && e.status !== 404) throw e;
      render(`<div class="card empty"><span class="e-ico">${ic(e.status === 403 ? 'lock' : 'alert')}</span>
        <p>${esc(e.message)}</p><a class="btn mt" href="/saboqlar/">Saboqlar yo'lkasi</a></div>`);
      return;
    }
    const isDone = l.state === 'done';
    const checks = isDone ? l.tasks.map(() => true) : loadChecks();

    const video = l.youtube_id
      ? `<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(l.youtube_id)}?rel=0&modestbranding=1"
           title="${esc(l.title)}" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowfullscreen loading="lazy"
           referrerpolicy="strict-origin-when-cross-origin"></iframe></div>
         <a class="link small" href="${esc(l.video_url)}" target="_blank" rel="noopener">${ic('play')} YouTube'da ochish</a>`
      : `<a class="video-ph" href="${esc(l.video_url)}" target="_blank" rel="noopener"><span class="play">${ic('play')}</span>
           Abdukarim Mirzayevning «Baraka Daftari» videolarini YouTube'da ko'rish</a>`;

    const action = ACTIONS[l.task_type];
    const page = render(`
      <a class="back-link" href="/saboqlar/">${ic('left')} Saboqlar yo'lkasi</a>

      <section class="card stack">
        <span class="chip gold">${ic('book')} ${l.number}-saboq</span>
        <h2 class="lesson-title">${esc(l.title)}</h2>
        ${video}
        <div><h3 class="sub-title">${ic('note')} Qisqacha mazmun</h3><p class="pre">${esc(l.summary)}</p></div>
      </section>

      ${l.key_points.length ? `
      <section class="card">
        <h3 class="sub-title">${ic('sparkles')} Saboqlar</h3>
        <ol class="points">${l.key_points.map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
      </section>` : ''}

      <section class="card stack">
        <h3 class="sub-title">${ic('target')} Nima qilish kerak</h3>
        ${l.tasks.length ? `<ul class="todo">${l.tasks.map((t, i) => `
          <li><label class="${checks[i] ? 'on' : ''}"><input type="checkbox" data-i="${i}" ${checks[i] ? 'checked' : ''} ${isDone ? 'disabled' : ''}>
            <span class="box">${ic('check')}</span><span>${esc(t)}</span></label></li>`).join('')}</ul>`
          : '<p class="muted">Videoni ko\'ring va saboqlarni o\'qib chiqing.</p>'}
        ${isDone
          ? `<div class="done-box">${ic('check-circle')} Bu saboq bajarilgan. Barakalla!${l.note ? `<p class="mt" style="font-weight:600">«${esc(l.note)}»</p>` : ''}</div>`
          : `${l.task_type === 'note' || l.note_prompt ? `<label class="field"><span>${esc(l.note_prompt || 'Javobingiz')}${l.task_type === 'note' ? '' : ' (ixtiyoriy)'}</span><textarea class="input" id="l-note" maxlength="2000" placeholder="Shu yerga yozing…"></textarea></label>` : ''}
             ${l.task_type === 'debt_list' ? `<label class="check"><input type="checkbox" id="l-nodebt"> Alhamdulillah, qarzim yo'q</label>` : ''}
             <div id="l-err"></div>
             ${action ? `<a class="btn ghost block" href="${action[0]}">${ic(action[2])} ${action[1]}</a>` : ''}
             <button class="btn big" id="l-done">${ic('check')} Saboqni yakunladim</button>`}
      </section>`);

    if (isDone) return;
    const doneBtn = page.querySelector('#l-done');
    const boxes = [...page.querySelectorAll('.todo input')];
    const sync = () => {
      const all = boxes.every((b) => b.checked);
      doneBtn.disabled = !all;
      doneBtn.title = all ? '' : "Avval barcha vazifalarni belgilang";
    };
    boxes.forEach((b) => {
      b.onchange = () => {
        b.closest('label').classList.toggle('on', b.checked);
        saveChecks(boxes.map((x) => x.checked));
        haptic('light');
        sync();
      };
    });
    sync();

    doneBtn.onclick = (ev) => withBusy(ev.currentTarget, async () => {
      const note = page.querySelector('#l-note');
      const noDebt = page.querySelector('#l-nodebt');
      try {
        const r = await api(`lessons/${l.number}/complete`, { method: 'POST', body: {
          note: note ? note.value : '', no_debt: noDebt ? noDebt.checked : false,
        } });
        B.confetti();
        B.openSheet(B.celebrate('sparkles', 'Barakalla! +10 yulduz',
          `${l.number}-saboq yakunlandi. ${r.total} ta saboqdan ${r.done} tasi ortda qoldi.`,
          `<div class="progress"><i data-w="${Math.round((r.done * 100) / r.total)}"></i></div>
           <a class="btn big" href="/saboqlar/">Saboqlar yo'lkasi</a>`), () => main());
        B.animateBars(document.getElementById('sheet-root'));
      } catch (e) {
        const box = page.querySelector('#l-err');
        const need = e.data && NEED_PAGES[e.data.need];
        box.innerHTML = `<div class="error-box">${ic('alert')} ${esc(e.message)}
          ${need ? `<p class="mt"><a class="link" href="${need}">Hozir bajarish ${ic('arrow')}</a></p>` : ''}</div>`;
        haptic('error');
      }
    });
  }

  B.ready(main);
})();
