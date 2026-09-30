/* Loyiha haqida */
(() => {
  'use strict';
  const { ic, render } = B;
  const BOT = B.CFG.botUsername;

  function main() {
    const botLink = BOT ? `https://t.me/${BOT}` : '';
    render(`
      <section class="hero compact">
        <img src="/static/img/logo.svg" alt="" class="hero-logo">
        <h1>Elektron <span>Baraka</span> Daftari</h1>
      </section>
      ${B.disclaimerHtml()}
      <section class="card principles">
        <div><span class="h-ico orange">${ic('x')}</span>Bu loyiha tez boyish usuli emas</div>
        <div><span class="h-ico green">${ic('check')}</span>Bu loyiha — boylikning ilmi</div>
        <div><span class="h-ico orange">${ic('x')}</span>Bu loyiha diniy fatvo emas</div>
        <div><span class="h-ico green">${ic('check')}</span>Bu loyiha — ta'limiy asar</div>
      </section>
      <section class="card">
        <h3>Loyiha haqida</h3>
        <p class="mt">Bu — moliyaviy saboqlarni amaliyotga aylantiruvchi bepul raqamli daftar. Maqsad: avval o'zingizga
          to'lash, xarajatlarni nazorat qilish va qarzdan qutulish bosqichlarini haftalik saboqlar va kichik amaliy
          qadamlar bilan o'rgatish.</p>
        <ul class="about-list mt">
          <li><span class="h-ico blue">${ic('book')}</span><div><b>Saboqlar</b> — har haftalik video bo'yicha saboqlar va nima qilish kerakligi.</div></li>
          <li><span class="h-ico green">${ic('wallet')}</span><div><b>Hamyon</b> — xarajatlar, qolgan pul, Zarur · Kerak · Havas.</div></li>
          <li><span class="h-ico green">${ic('safe')}</span><div><b>Jamg'arma</b> — qo'riqchi pul va o'sadigan pul.</div></li>
          <li><span class="h-ico orange">${ic('snow')}</span><div><b>Qarzlar</b> — kredit kalkulyatori, 70/20/10 va «qor bo'lagi» rejasi.</div></li>
          <li><span class="h-ico purple">${ic('bell')}</span><div><b>Bot</b> — yangi saboq xabari, kechqurun xarajat eslatmasi.</div></li>
        </ul>
      </section>
      <section class="card">
        <a class="btn ghost block" href="/sozlamalar/">${ic('gear')} Sozlamalar</a>
        ${botLink ? `<a class="btn blue block mt" href="${botLink}" target="_blank" rel="noopener">${ic('send')} Botni ochish</a>` : ''}
      </section>`);
  }

  B.ready(main);
})();
