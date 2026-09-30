/* Bank krediti hisob-kitobi (annuitet). Serverdagi core/services.py bilan bir xil formula —
   formada jonli ko'rsatish uchun. Saqlanganda server qayta hisoblaydi. */
(() => {
  'use strict';

  const mrate = (annual) => annual / 100 / 12;

  function annuity(principal, annual, months) {
    if (months <= 0 || principal <= 0) return 0;
    const r = mrate(annual);
    if (!r) return Math.ceil(principal / months);
    return Math.ceil((principal * r) / (1 - (1 + r) ** -months));
  }

  /** [oylar, jami to'lov] yoki to'lov foizni ham yopmasa [null, null] */
  function simulate(balance, annual, payment) {
    const r = mrate(annual);
    let months = 0; let total = 0;
    while (balance > 0.5 && months < 1200) {
      const interest = balance * r;
      if (payment <= interest) return [null, null];
      const pay = Math.min(payment, balance + interest);
      balance = balance + interest - pay;
      total += pay;
      months += 1;
    }
    return [months, Math.round(total)];
  }

  function applyPayment(balance, annual, standard, amount) {
    const share = standard ? Math.min(1, amount / standard) : 1;
    return Math.max(0, Math.round(balance + balance * mrate(annual) * share - amount));
  }

  function balanceAfterPaid(principal, annual, payment, paid) {
    let balance = principal; let left = paid;
    while (left > 0 && balance > 0) {
      const pay = Math.min(payment, left);
      balance = applyPayment(balance, annual, payment, pay);
      left -= pay;
    }
    return balance;
  }

  function calc(principal, annual, months, paid = 0, extraPercent = 0) {
    const payment = annuity(principal, annual, months);
    const balance = balanceAfterPaid(principal, annual, payment, paid);
    const [monthsLeft, remaining] = simulate(balance, annual, payment);
    const extraAmount = Math.floor((payment * extraPercent) / 100);
    const [monthsExtra, remainingExtra] = simulate(balance, annual, payment + extraAmount);
    return {
      payment,
      total: payment * months,
      overpay: payment * months - principal,
      paid,
      balance,
      monthsLeft: monthsLeft || 0,
      remaining: remaining || 0,
      extraAmount,
      extraPayment: payment + extraAmount,
      monthsExtra: monthsExtra || 0,
      remainingExtra: remainingExtra || 0,
      monthsSaved: (monthsLeft || 0) - (monthsExtra || 0),
      saved: (remaining || 0) - (remainingExtra || 0),
    };
  }

  const payoff = (balance, annual) => Math.round(balance * (1 + mrate(annual)));

  window.Credit = { annuity, calc, payoff };
})();
