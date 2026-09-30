/* Landing: 70/20/10 kalkulyatori */
(() => {
  'use strict';
  const input = document.getElementById('lc-income');
  if (!input) return;
  const num = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const fmt = (n) => `${num(n)} so'm`;
  const short = (n) => (n >= 1e6 ? `${+(n / 1e6).toFixed(1)} mln` : `${num(n)}`);

  function update() {
    const digits = input.value.replace(/\D/g, '').slice(0, 12);
    input.value = digits ? num(Number(digits)) : '';
    const v = Number(digits) || 0;
    document.getElementById('lc-70').textContent = fmt(v * 0.7);
    document.getElementById('lc-20').textContent = fmt(v * 0.2);
    document.getElementById('lc-10').textContent = fmt(v * 0.1);
    document.getElementById('lc-year').textContent = v
      ? `Har oy ${short(v * 0.1)} so'mdan — bir yilda ${short(v * 1.2)} so'm o'zingizniki bo'ladi.`
      : 'Oyligingizni yozing — bir yilda qancha yig\'ishingizni ko\'rasiz.';
  }
  input.addEventListener('input', update);
  update();
})();
