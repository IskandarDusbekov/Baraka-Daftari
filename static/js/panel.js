/* Boshqaruv paneli: tasdiqlash oynasi, belgi hisoblagichlar, YouTube ko'rinishi, saqlanmagan o'zgarishlar. */
(function () {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------ tasdiqlash oynasi (modal)
  function confirmModal({ title, text, ok = 'Ha', danger = false }) {
    return new Promise((resolve) => {
      const root = document.createElement('div');
      root.className = 'p-modal-root';
      root.innerHTML = `
        <div class="p-modal-backdrop" data-no></div>
        <div class="p-modal" role="alertdialog" aria-modal="true" aria-labelledby="pm-title">
          <div class="p-modal-ico ${danger ? 'danger' : ''}"><svg class="ic"><use href="#i-${danger ? 'alert' : 'check-circle'}"/></svg></div>
          <h3 id="pm-title">${esc(title || 'Tasdiqlang')}</h3>
          <p>${esc(text)}</p>
          <div class="p-modal-actions">
            <button type="button" class="p-btn ghost" data-no>Bekor qilish</button>
            <button type="button" class="p-btn ${danger ? 'danger' : ''}" data-yes>${esc(ok)}</button>
          </div>
        </div>`;
      document.body.appendChild(root);
      const prevFocus = document.activeElement;
      const close = (value) => {
        root.classList.remove('open');
        document.removeEventListener('keydown', onKey);
        setTimeout(() => root.remove(), 180);
        if (prevFocus && prevFocus.focus) prevFocus.focus();
        resolve(value);
      };
      const onKey = (e) => { if (e.key === 'Escape') close(false); };
      document.addEventListener('keydown', onKey);
      $$('[data-no]', root).forEach((el) => el.addEventListener('click', () => close(false)));
      $('[data-yes]', root).addEventListener('click', () => close(true));
      requestAnimationFrame(() => { root.classList.add('open'); $('[data-yes]', root).focus(); });
    });
  }
  window.PanelConfirm = confirmModal;

  document.addEventListener('submit', async (e) => {
    const form = e.target;
    if (form.dataset.confirmed === '1') { form.dataset.confirmed = ''; return; }
    const submitter = e.submitter;
    // Tugmaning o'z data-confirm'i ustun (masalan, "Saqlash va e'lon qilish")
    const source = submitter && submitter.dataset.confirm ? submitter : (form.dataset.confirm ? form : null);
    if (!source) return;
    e.preventDefault();
    const ok = await confirmModal({
      title: source.dataset.confirmTitle, text: source.dataset.confirm,
      ok: source.dataset.confirmOk, danger: source.hasAttribute('data-danger'),
    });
    if (!ok) { form.dataset.submitting = ''; return; }
    form.dataset.confirmed = '1';
    form.dataset.submitting = '1';
    if (form.requestSubmit) form.requestSubmit(submitter || undefined);
    else form.submit();
  });

  // ------------------------------------------------------------ jadval qatori — havola
  $$('tr[data-href]').forEach((tr) => {
    tr.addEventListener('click', (e) => { if (!e.target.closest('a, button, form')) location.href = tr.dataset.href; });
  });

  // ------------------------------------------------------------ belgi va qator hisoblagichlari
  $$('[data-count]').forEach((input) => {
    const limit = Number(input.dataset.count);
    const badge = document.createElement('small');
    badge.className = 'counter';
    input.insertAdjacentElement('afterend', badge);
    const update = () => {
      const n = input.value.length;
      badge.textContent = `${n} / ${limit}`;
      badge.classList.toggle('over', n > limit);
    };
    input.addEventListener('input', update);
    update();
  });
  $$('[data-lines]').forEach((badge) => {
    const area = document.getElementById(badge.dataset.lines);
    if (!area) return;
    const update = () => {
      const n = area.value.split('\n').filter((l) => l.replace(/^[\s\-•]+/, '').trim()).length;
      badge.textContent = n ? `· ${n} ta` : '';
    };
    area.addEventListener('input', update);
    update();
  });

  // ------------------------------------------------------------ saboq formasi
  const yt = $('#id_youtube_id');
  const ytBox = $('#yt-preview');
  if (yt && ytBox) {
    const idOf = (v) => {
      v = (v || '').trim();
      for (const m of ['v=', 'youtu.be/', '/embed/', '/shorts/', '/live/']) {
        if (v.includes(m)) { v = v.split(m)[1]; break; }
      }
      v = v.split(/[&?#/]/)[0];
      return /^[A-Za-z0-9_-]{11}$/.test(v) ? v : '';
    };
    const update = () => {
      const id = idOf(yt.value);
      ytBox.innerHTML = id
        ? `<a href="https://youtu.be/${id}" target="_blank" rel="noopener noreferrer"><img src="https://i.ytimg.com/vi/${id}/mqdefault.jpg" alt="Video"><span>${id}</span></a>`
        : (yt.value.trim() ? '<p class="err">Havola noto\'g\'ri</p>' : `<p class="p-muted">${esc(ytBox.dataset.empty)}</p>`);
    };
    yt.addEventListener('input', update);
    update();
  }
  const taskType = $('#id_task_type');
  const noteRow = $('#note-prompt-row');
  if (taskType && noteRow) {
    const update = () => { noteRow.style.opacity = taskType.value === 'note' ? '1' : '.45'; };
    taskType.addEventListener('change', update);
    update();
  }

  // ------------------------------------------------------------ SEO: Google natijasi ko'rinishi
  const seoTitle = $('#id_seo-title');
  const seoDesc = $('#id_seo-description');
  if (seoTitle && seoDesc && $('#serp')) {
    const cut = (s, n) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
    const update = () => {
      $('#serp-title').textContent = cut(seoTitle.value || 'Baraka Daftari — pulingiz qayerga ketayotganini yozib boring', 60);
      $('#serp-desc').textContent = cut(seoDesc.value || 'Tavsif yozilmagan — Google sahifadan o\'zi parcha oladi.', 160);
    };
    seoTitle.addEventListener('input', update);
    seoDesc.addEventListener('input', update);
    update();
  }

  // ------------------------------------------------------------ saqlanmagan o'zgarishlar
  $$('form[data-dirty-guard]').forEach((form) => {
    const snapshot = () => new URLSearchParams(new FormData(form)).toString();
    const initial = snapshot();
    form.addEventListener('submit', () => { form.dataset.submitting = '1'; });
    window.addEventListener('beforeunload', (e) => {
      if (form.dataset.submitting === '1' || snapshot() === initial) return;
      e.preventDefault();
      e.returnValue = '';
    });
  });
})();
