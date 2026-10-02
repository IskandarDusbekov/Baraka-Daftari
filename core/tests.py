import datetime as dt
import hashlib
import hmac
import io
import json
import time
from unittest import mock
from urllib.parse import urlencode

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from bot import handlers, reminders
from core import services
from core.auth import make_api_token, verify_webapp_init_data
from core.models import Debt, DebtLink, DebtPayment, Lesson, LessonProgress, LoginCode, TgUser
from core.saboq_data import load_saboqlar


TEST_RATE = {"rate": 12000.0, "diff": 5.0, "date": "30.09.2026", "source": "MB"}


class BaseTestCase(TestCase):
    def setUp(self):
        cache.clear()  # saboqlar keshi va rate limit testlar orasida qolmasin
        # Testlar cbu.uz ga chiqmaydi
        patcher = mock.patch("core.rates.fetch_usd", return_value=dict(TEST_RATE))
        self.fetch_rate = patcher.start()
        self.addCleanup(patcher.stop)

BOT_TOKEN = "123456:TEST-TOKEN"


def signed_init_data(user, bot_token=BOT_TOKEN, auth_date=None):
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAE",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class InitDataTests(BaseTestCase):
    def test_valid(self):
        data = signed_init_data({"id": 42, "first_name": "Ali"})
        self.assertEqual(verify_webapp_init_data(data, BOT_TOKEN)["id"], 42)

    def test_wrong_token_rejected(self):
        data = signed_init_data({"id": 42})
        self.assertIsNone(verify_webapp_init_data(data, "999:OTHER"))

    def test_tampered_rejected(self):
        data = signed_init_data({"id": 42}).replace("42", "43")
        self.assertIsNone(verify_webapp_init_data(data, BOT_TOKEN))

    def test_expired_rejected(self):
        data = signed_init_data({"id": 42}, auth_date=int(time.time()) - 3 * 86400)
        self.assertIsNone(verify_webapp_init_data(data, BOT_TOKEN))


class ApiTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = TgUser.objects.create(tg_id=1001, first_name="Ali")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {make_api_token(self.user)}"}

    def post(self, url, data=None):
        return self.client.post(url, json.dumps(data or {}), content_type="application/json", **self.auth)

    def get(self, url):
        return self.client.get(url, **self.auth)


@override_settings(BOT_TOKEN=BOT_TOKEN, BOT_USERNAME="baraka_test_bot")
class AuthApiTests(ApiTestCase):
    def test_telegram_login(self):
        r = self.client.post("/api/auth/telegram", json.dumps({"init_data": signed_init_data({"id": 77, "first_name": "Vali"})}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(TgUser.objects.filter(tg_id=77, first_name="Vali").exists())
        r2 = self.client.get("/api/me", HTTP_AUTHORIZATION=f"Bearer {r.json()['token']}")
        self.assertEqual(r2.json()["user"]["tg_id"], 77)

    def test_requires_token(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(self.client.get("/api/me", HTTP_AUTHORIZATION="Bearer junk").status_code, 401)

    def test_web_login_via_bot(self):
        r = self.client.post("/api/auth/login-code")
        code = r.json()["code"]
        self.assertIn("t.me/baraka_test_bot?start=login_", r.json()["bot_link"])
        self.assertEqual(self.client.get(f"/api/auth/login-status?code={code}").json()["status"], "pending")

        api = mock.Mock()
        handlers.handle_update(api, {"message": {"chat": {"type": "private", "id": 5},
                                                 "from": {"id": 5, "first_name": "Sardor"},
                                                 "text": f"/start login_{code}"}})
        callback = api.send.call_args[0][2][0][0]["callback_data"]
        handlers.handle_update(api, {"callback_query": {"id": "q", "data": callback,
                                                        "from": {"id": 5, "first_name": "Sardor"}}})

        st = self.client.get(f"/api/auth/login-status?code={code}").json()
        self.assertEqual(st["status"], "ok")
        self.assertEqual(st["user"]["tg_id"], 5)
        # kod bir martalik
        self.assertEqual(self.client.get(f"/api/auth/login-status?code={code}").json()["status"], "invalid")
        sardor = TgUser.objects.get(tg_id=5)
        actions = set(sardor.activity.values_list("action", flat=True))
        self.assertTrue({"register", "bot_start", "login"} <= actions)

    def test_register_and_login_logged(self):
        data = json.dumps({"init_data": signed_init_data({"id": 88, "first_name": "Olim"})})
        self.client.post("/api/auth/telegram", data, content_type="application/json")
        self.client.post("/api/auth/telegram", data, content_type="application/json")
        user = TgUser.objects.get(tg_id=88)
        self.assertEqual(user.activity.filter(action="register").count(), 1)
        self.assertEqual(user.activity.filter(action="login").count(), 2)

    def test_disabled_user_cannot_use_app(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.get("/api/me").status_code, 401)
        TgUser.objects.create(tg_id=99, is_active=False)
        data = json.dumps({"init_data": signed_init_data({"id": 99, "first_name": "X"})})
        self.assertEqual(self.client.post("/api/auth/telegram", data, content_type="application/json").status_code, 403)

    def test_login_code_rate_limited(self):
        codes = [self.client.post("/api/auth/login-code").status_code for _ in range(22)]
        self.assertEqual(codes[0], 200)
        self.assertEqual(codes[-1], 429)


class DevLoginTests(BaseTestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        super().setUp()
        User.objects.create_user("dev", password="secret-pass-123", is_staff=True)
        User.objects.create_user("plain", password="secret-pass-123")

    def login(self, username, password):
        return self.client.post("/api/auth/dev-login", json.dumps({"username": username, "password": password}),
                                content_type="application/json")

    @override_settings(DEV_LOGIN=True)
    def test_staff_can_login(self):
        r = self.login("dev", "secret-pass-123")
        self.assertEqual(r.status_code, 200)
        self.assertLess(r.json()["user"]["tg_id"], 0)
        me = self.client.get("/api/me", HTTP_AUTHORIZATION=f"Bearer {r.json()['token']}")
        self.assertEqual(me.status_code, 200)
        self.assertContains(self.client.get("/kirish/"), "dev-form")

    @override_settings(DEV_LOGIN=True)
    def test_rejects_wrong_password_and_non_staff(self):
        self.assertEqual(self.login("dev", "wrong").status_code, 403)
        self.assertEqual(self.login("plain", "secret-pass-123").status_code, 403)

    @override_settings(DEV_LOGIN=True)
    def test_throttled(self):
        for _ in range(10):
            self.login("dev", "wrong")
        self.assertEqual(self.login("dev", "secret-pass-123").status_code, 429)

    @override_settings(DEV_LOGIN=False)
    def test_disabled_in_production(self):
        self.assertEqual(self.login("dev", "secret-pass-123").status_code, 404)
        self.assertNotContains(self.client.get("/kirish/"), "dev-form")


class WalletTests(ApiTestCase):
    def test_income_suggests_ten_percent_and_saving(self):
        r = self.post("/api/incomes", {"amount": "5 000 000"})
        self.assertEqual(r.json()["suggested_saving"], 500_000)
        r = self.post("/api/savings", {"amount": 500_000, "income_id": r.json()["income"]["id"]})
        self.assertEqual(r.json()["reserve_total"], 500_000)
        me = self.get("/api/me").json()
        self.assertEqual(me["reserve_total"], 500_000)
        self.assertEqual(me["month"]["should_save"], 500_000)

    def test_expenses_by_category(self):
        self.post("/api/expenses", {"amount": 100, "category": "food"})
        self.post("/api/expenses", {"amount": 50, "category": "food"})
        self.post("/api/expenses", {"amount": 30, "category": "transport"})
        cats = {c["key"]: c["amount"] for c in self.get("/api/wallet").json()["categories"]}
        self.assertEqual(cats["food"], 150)
        self.assertEqual(cats["transport"], 30)

    def test_edit_entries(self):
        e = self.post("/api/expenses", {"amount": 100, "category": "food"}).json()["expense"]
        r = self.post(f"/api/entries/expense/{e['id']}", {"amount": "250", "category": "clothes", "need": "havas", "note": "ko'ylak"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["expense"]["amount"], r.json()["expense"]["category"], r.json()["expense"]["need"]),
                         (250, "clothes", "havas"))
        i = self.post("/api/incomes", {"amount": 1000}).json()["income"]
        r = self.post(f"/api/entries/income/{i['id']}", {"amount": 2000, "source": "business"}).json()["income"]
        self.assertEqual((r["amount"], r["source"]), (2000, "business"))
        self.assertEqual(self.post(f"/api/entries/expense/{e['id']}", {"amount": 0}).status_code, 400)
        actions = list(self.user.activity.values_list("action", flat=True))
        self.assertIn("expense_edit", actions)
        self.assertIn("income_edit", actions)

    def test_cannot_edit_foreign_entry(self):
        other = TgUser.objects.create(tg_id=3)
        e = other.expenses.create(amount=10)
        self.assertEqual(self.post(f"/api/entries/expense/{e.id}", {"amount": 5}).status_code, 404)

    def test_zarur_kerak_havas(self):
        self.post("/api/expenses", {"amount": 100, "need": "zarur"})
        self.post("/api/expenses", {"amount": 40, "need": "havas"})
        self.post("/api/expenses", {"amount": 7})
        w = self.get("/api/wallet").json()
        self.assertEqual(w["needs"], {"zarur": 100, "kerak": 0, "havas": 40, "unmarked": 7})
        self.assertEqual(self.post("/api/expenses", {"amount": 5, "need": "xyz"}).status_code, 400)

    def test_validation(self):
        self.assertEqual(self.post("/api/expenses", {"amount": 0}).status_code, 400)
        self.assertEqual(self.post("/api/expenses", {"amount": 10, "category": "hack"}).status_code, 400)

    def test_cannot_delete_foreign_entry(self):
        other = TgUser.objects.create(tg_id=2)
        e = other.expenses.create(amount=10)
        r = self.client.delete(f"/api/entries/expense/{e.id}", **self.auth)
        self.assertEqual(r.status_code, 404)


class CurrencyTests(ApiTestCase):
    def test_choose_currency_without_data(self):
        r = self.post("/api/me/currency", {"currency": "USD"}).json()
        self.assertEqual((r["user"]["currency"], r["user"]["currency_chosen"], r["converted"]), ("USD", True, False))
        self.assertEqual(self.post("/api/me/currency", {"currency": "EUR"}).status_code, 400)

    def test_switch_converts_everything_at_cbu_rate(self):
        self.post("/api/me", {"income_type": "salary", "monthly_income": 12_000_000})
        self.post("/api/incomes", {"amount": 12_000_000})
        self.post("/api/expenses", {"amount": 1_200_000})
        self.post("/api/savings", {"amount": 1_200_000, "bucket": "guard"})
        self.post("/api/recurring", {"name": "Ijara", "amount": 3_600_000, "day": 28})
        d = self.post("/api/debts", {"name": "Nasiya", "kind": "nasiya", "total": 24_000_000,
                                     "paid": 12_000_000, "monthly_payment": 2_400_000}).json()["debt"]

        r = self.post("/api/me/currency", {"currency": "USD"}).json()
        self.assertTrue(r["converted"])
        self.assertEqual(r["user"]["monthly_income"], 1000)
        month = self.get("/api/me").json()["month"]
        self.assertEqual((month["income"], month["saved"]), (1000, 100))
        debt = self.get("/api/debts").json()["debts"][0]
        self.assertEqual((debt["total"], debt["paid"], debt["monthly_payment"]), (2000, 1000, 200))
        self.assertEqual(self.get("/api/recurring").json()["total"], 300)

        # Orqaga: yana so'mga
        self.post("/api/me/currency", {"currency": "UZS"})
        self.assertEqual(self.get("/api/me").json()["user"]["monthly_income"], 12_000_000)
        self.assertEqual(d["id"], self.get("/api/debts").json()["debts"][0]["id"])

    def test_no_rate_blocks_conversion_but_not_first_choice(self):
        import requests

        self.fetch_rate.side_effect = requests.RequestException("cbu down")
        self.assertEqual(self.post("/api/me/currency", {"currency": "USD"}).status_code, 200)  # ma'lumot yo'q
        self.post("/api/expenses", {"amount": 5})
        self.assertEqual(self.post("/api/me/currency", {"currency": "UZS"}).status_code, 503)
        self.assertEqual(self.get("/api/me").json()["user"]["currency"], "USD")

    def test_rate_cached(self):
        self.get("/api/rates")
        r = self.get("/api/rates").json()["rate"]
        self.assertEqual(r["rate"], 12000.0)
        self.assertEqual(self.fetch_rate.call_count, 1)

    def test_onboarding_steps(self):
        o = self.get("/api/me").json()["onboarding"]
        self.assertEqual((o["total"], o["done"], o["next"]), (6, 0, "currency"))
        self.post("/api/me/currency", {"currency": "UZS"})
        self.post("/api/expenses", {"amount": 5})
        o = self.get("/api/me").json()["onboarding"]
        self.assertEqual((o["done"], o["next"]), (2, "income"))
        self.post("/api/me", {"onboarding_hidden": True})
        self.assertTrue(self.get("/api/me").json()["onboarding"]["hidden"])


class JamgarmaTests(ApiTestCase):
    def test_auto_bucket_fills_guard_first(self):
        # oylik ro'zg'or = majburiy xarajat 1 mln, maqsad 3 oy = 3 mln
        self.post("/api/recurring", {"name": "Ijara", "amount": 1_000_000, "day": 28})
        r = self.post("/api/savings", {"amount": 2_000_000, "bucket": "auto"}).json()
        self.assertEqual(r["saving"]["bucket"], "guard")
        self.assertEqual(r["savings"]["guard_target"], 3_000_000)
        self.post("/api/savings", {"amount": 1_500_000, "bucket": "auto"})
        r = self.post("/api/savings", {"amount": 700_000, "bucket": "auto"}).json()
        self.assertEqual(r["saving"]["bucket"], "grow")  # qo'riqchi pul to'ldi
        self.assertEqual(r["savings"]["guard"], 3_500_000)

    def test_transfer_and_withdraw(self):
        self.post("/api/savings", {"amount": 1_000_000, "bucket": "guard"})
        r = self.post("/api/savings/transfer", {"from": "guard", "amount": 400_000}).json()
        self.assertEqual((r["savings"]["guard"], r["savings"]["grow"]), (600_000, 400_000))
        self.assertEqual(r["reserve_total"], 1_000_000)
        self.assertEqual(self.post("/api/savings/transfer", {"from": "grow", "amount": 999_999}).status_code, 400)

        r = self.post("/api/savings/withdraw", {"bucket": "grow", "amount": 100_000, "note": "davolanish"}).json()
        self.assertEqual(r["reserve_total"], 900_000)
        month = self.get("/api/me").json()["month"]
        self.assertEqual(month["saved"], 1_000_000)
        self.assertEqual(month["withdrawn"], 100_000)

        # O'tkazmaning bir qismi o'chirilsa, ikkinchisi ham o'chadi
        items = self.get("/api/jamgarma").json()["history"]["entries"]
        transfer = next(e for e in items if e["kind"] == "transfer")
        self.client.delete(f"/api/entries/saving/{transfer['id']}", **self.auth)
        self.assertEqual(self.get("/api/jamgarma").json()["savings"]["guard"], 1_000_000)

    def test_guard_months_setting(self):
        self.assertEqual(self.post("/api/me", {"guard_months": 6}).json()["user"]["guard_months"], 6)
        self.assertEqual(self.post("/api/me", {"guard_months": 0}).status_code, 400)


class RecurringTests(ApiTestCase):
    def test_created_once_when_day_comes(self):
        today = timezone.localdate()
        r = self.post("/api/recurring", {"name": "Ijara", "amount": 3_000_000, "category": "rent", "day": 1}).json()
        self.assertTrue(r["item"]["done_this_month"])
        self.get("/api/me")
        self.get("/api/wallet")
        rent = TgUser.objects.get(pk=self.user.pk).expenses.filter(category="rent")
        self.assertEqual(rent.count(), 1)
        self.assertEqual(rent.first().date, today.replace(day=1))
        self.assertEqual(rent.first().need, "zarur")

    def test_pending_reduces_free_money(self):
        tenth = timezone.localdate().replace(day=10)  # to'lov kuni (28) hali kelmagan
        with mock.patch("django.utils.timezone.localdate", return_value=tenth):
            self.post("/api/me", {"income_type": "salary", "monthly_income": 8_000_000})
            self.post("/api/recurring", {"name": "Kredit", "amount": 2_000_000, "day": 28})
            month = self.get("/api/me").json()["month"]
        self.assertEqual(month["planned_pending"], 2_000_000)
        self.assertEqual(month["free_after_planned"], 6_000_000)

    def test_validation_and_delete(self):
        self.assertEqual(self.post("/api/recurring", {"name": "X", "amount": 5, "day": 31}).status_code, 400)
        item = self.post("/api/recurring", {"name": "Net", "amount": 100_000, "day": 28}).json()["item"]
        self.assertEqual(self.post(f"/api/recurring/{item['id']}", {"active": False}).json()["item"]["active"], False)
        self.assertEqual(self.client.delete(f"/api/recurring/{item['id']}", **self.auth).status_code, 200)


class HistoryTests(ApiTestCase):
    def test_pagination_and_filter(self):
        for i in range(25):
            self.post("/api/expenses", {"amount": 1000 + i, "category": "clothes"})
        self.post("/api/incomes", {"amount": 5_000_000})
        first = self.get("/api/wallet").json()["history"]
        self.assertEqual(len(first["entries"]), 20)
        self.assertTrue(first["has_more"])
        self.assertEqual(first["count"], 26)
        rest = self.get("/api/entries?offset=20").json()
        self.assertEqual(len(rest["entries"]), 6)
        self.assertFalse(rest["has_more"])
        only_income = self.get("/api/entries?type=income").json()
        self.assertEqual(only_income["count"], 1)
        self.assertEqual(self.get("/api/entries?type=hack").status_code, 400)


class DebtTests(ApiTestCase):
    def test_pay_and_close(self):
        d = self.post("/api/debts", {"name": "Nasiya", "total": 1000, "monthly_payment": 400}).json()["debt"]
        r = self.post(f"/api/debts/{d['id']}/pay", {"amount": 450}).json()
        self.assertEqual(r["debt"]["percent"], 45)
        r = self.post(f"/api/debts/{d['id']}/pay", {"amount": 9999}).json()
        self.assertTrue(r["just_closed"])
        self.assertEqual(r["paid_now"], 550)

    def test_snowball_smallest_first(self):
        self.post("/api/debts", {"name": "Katta", "total": 30_000_000, "monthly_payment": 1_500_000})
        self.post("/api/debts", {"name": "Kichik", "total": 2_000_000, "monthly_payment": 500_000})
        plan = self.get("/api/debts/plan?extra=1000000").json()
        self.assertEqual(plan["order"][0]["name"], "Kichik")
        self.assertTrue(plan["order"][0]["target"])
        self.assertLess(plan["months"], plan["months_min_only"])

    def test_credit_example_50m_25pct_3y(self):
        """Foydalanuvchi misoli: 50 mln, yillik 25%, 3 yil, har oy +20%."""
        c = services.credit_calc(50_000_000, 25, 36, 0, 20)
        self.assertAlmostEqual(c["monthly_payment"], 1_988_000, delta=100)
        self.assertAlmostEqual(c["total_with_interest"], 71_570_000, delta=10_000)
        self.assertEqual(c["months_left"], 36)
        self.assertEqual(c["months_with_extra"], 28)
        self.assertEqual(c["months_saved"], 8)
        self.assertAlmostEqual(c["saved"], 5_170_000, delta=20_000)

    def test_zero_interest_credit(self):
        c = services.credit_calc(12_000_000, 0, 12, 0, 0)
        self.assertEqual(c["monthly_payment"], 1_000_000)
        self.assertEqual(c["overpay"], 0)
        self.assertEqual(c["months_left"], 12)

    def test_create_credit_with_paid_months_and_pay(self):
        r = self.post("/api/debts", {"name": "Avtokredit", "kind": "credit", "principal": "50 000 000",
                                     "interest_rate": 25, "term_months": 36, "paid_months": 5, "extra_percent": 20})
        debt = r.json()["debt"]
        c = debt["credit"]
        self.assertEqual(debt["paid"], 5 * c["monthly_payment"])
        self.assertEqual(c["months_left"], 31)
        self.assertEqual(debt["remaining"], c["remaining"])
        self.assertGreater(c["saved"], 0)

        # Qo'shimcha to'lov bank foizini kamaytiradi: qoldiq to'lovdan ko'proq kamayadi
        before = debt["remaining"]
        r = self.post(f"/api/debts/{debt['id']}/pay", {"amount": c["extra_payment"]}).json()
        self.assertGreater(before - r["debt"]["remaining"], c["extra_payment"])

        # Hammasini yopish
        r = self.post(f"/api/debts/{debt['id']}/pay", {"amount": 999_000_000}).json()
        self.assertTrue(r["just_closed"])
        self.assertEqual(r["debt"]["remaining"], 0)

    def test_credit_validation(self):
        base = {"name": "K", "kind": "credit", "principal": 1_000_000, "interest_rate": 20, "term_months": 12}
        self.assertEqual(self.post("/api/debts", {**base, "term_months": 0}).status_code, 400)
        self.assertEqual(self.post("/api/debts", {**base, "interest_rate": 500}).status_code, 400)
        self.assertEqual(self.post("/api/debts", base).status_code, 200)

    def test_update_credit_extra_percent(self):
        d = self.post("/api/debts", {"name": "K", "kind": "credit", "principal": 10_000_000,
                                     "interest_rate": 20, "term_months": 24}).json()["debt"]
        self.assertEqual(d["credit"]["saved"], 0)
        d = self.post(f"/api/debts/{d['id']}", {"extra_percent": 30}).json()["debt"]
        self.assertEqual(d["credit"]["extra_percent"], 30)
        self.assertGreater(d["credit"]["saved"], 0)

    def test_simulation(self):
        months, payoff = services.simulate_snowball([100, 300], [50, 50], 0)
        self.assertEqual(payoff[0], 2)
        self.assertEqual(months, 4)
        self.assertEqual(services.simulate_snowball([100], [0], 0)[0], None)


def make_saboqlar():
    load_saboqlar(Lesson, [
        dict(number=1, title="Niyat", summary="Mazmun", key_points=["Birinchi saboq", "Ikkinchi saboq"],
             tasks=["Maqsadni yozing"], task_type="note"),
        dict(number=2, title="Daromad", summary="Mazmun", tasks=["Oylikni kiriting"], task_type="income"),
        dict(number=3, title="Qarzlar", summary="Mazmun", task_type="debt_list"),
        dict(number=4, title="Hali chiqmagan", summary="Mazmun", is_published=False),
    ])


class LessonTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        make_saboqlar()

    def test_empty_when_no_saboqlar(self):
        Lesson.objects.all().delete()
        self.assertEqual(self.get("/api/lessons").json()["lessons"], [])
        self.assertIsNone(self.get("/api/me").json()["lessons"]["current"])

    def test_next_saboq_opens_after_task_done(self):
        lessons = self.get("/api/lessons").json()["lessons"]
        self.assertEqual(len(lessons), 3)  # nashr qilinmagani ko'rinmaydi
        self.assertEqual(lessons[0]["state"], "open")
        self.assertEqual(lessons[1]["state"], "locked")
        self.assertEqual(self.get("/api/lessons/2").status_code, 403)  # vazifa bajarilmaguncha yopiq

        detail = self.get("/api/lessons/1").json()["lesson"]
        self.assertEqual(detail["key_points"], ["Birinchi saboq", "Ikkinchi saboq"])
        self.assertEqual(detail["tasks"], ["Maqsadni yozing"])

        # 1-saboq: fikr yozish kerak
        self.assertEqual(self.post("/api/lessons/1/complete", {"note": ""}).status_code, 400)
        r = self.post("/api/lessons/1/complete", {"note": "Qarzsiz yashash"})
        self.assertEqual(r.json(), {"ok": True, "done": 1, "total": 3})

        # vazifa bajarilishi bilan keyingisi darhol ochiladi (kutish yo'q), undan keyingisi hali yopiq
        lessons = self.get("/api/lessons").json()["lessons"]
        self.assertEqual(lessons[1]["state"], "open")
        self.assertEqual(lessons[2]["state"], "locked")
        self.assertEqual(self.get("/api/lessons/2").status_code, 200)

        # 2-saboq: oylik daromad kiritilmaguncha bajarilmaydi
        r = self.post("/api/lessons/2/complete")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["need"], "hamyon")
        self.post("/api/me", {"monthly_income": 8_000_000})
        self.assertEqual(self.post("/api/lessons/2/complete").status_code, 200)

    def test_locked_and_unpublished_hidden(self):
        self.assertEqual(self.get("/api/lessons/3").status_code, 403)
        self.assertEqual(self.get("/api/lessons/4").status_code, 404)


class MonthlyIncomeTests(ApiTestCase):
    def test_ten_percent_from_monthly_income_without_entries(self):
        self.post("/api/me", {"monthly_income": "8 000 000"})
        month = self.get("/api/me").json()["month"]
        self.assertEqual(month["base_income"], 8_000_000)
        self.assertEqual(month["should_save"], 800_000)
        self.assertTrue(month["income_is_planned"])

    def test_real_income_takes_priority(self):
        self.post("/api/me", {"monthly_income": 8_000_000})
        self.post("/api/incomes", {"amount": 9_000_000})
        month = self.get("/api/wallet").json()["totals"]
        self.assertEqual(month["should_save"], 900_000)
        self.assertFalse(month["income_is_planned"])

    def test_custom_percent(self):
        self.post("/api/me", {"income_type": "salary", "monthly_income": 8_000_000, "save_percent": 15})
        month = self.get("/api/me").json()["month"]
        self.assertEqual(month["save_percent"], 15)
        self.assertEqual(month["should_save"], 1_200_000)
        r = self.post("/api/incomes", {"amount": 2_000_000}).json()
        self.assertEqual(r["suggested_saving"], 300_000)
        self.assertEqual(self.post("/api/me", {"save_percent": 0}).status_code, 400)
        self.assertEqual(self.post("/api/me", {"save_percent": 51}).status_code, 400)

    def test_no_salary(self):
        self.post("/api/me", {"income_type": "salary", "monthly_income": 8_000_000})
        self.post("/api/me", {"income_type": "irregular", "save_percent": 5})
        me = self.get("/api/me").json()
        self.assertEqual(me["user"]["monthly_income"], 0)
        self.assertEqual(me["month"]["should_save"], 0)
        self.post("/api/incomes", {"amount": 3_000_000})
        self.assertEqual(self.get("/api/me").json()["month"]["should_save"], 150_000)

    def test_money_left(self):
        self.post("/api/me", {"income_type": "salary", "monthly_income": 8_000_000})
        self.post("/api/expenses", {"amount": 2_000_000})
        self.post("/api/savings", {"amount": 800_000})
        month = self.get("/api/me").json()["month"]
        self.assertEqual(month["left"], 5_200_000)
        self.assertEqual(month["spent_percent"], 25)

    def test_rule_70_20_10(self):
        self.post("/api/me", {"income_type": "salary", "monthly_income": 10_000_000})
        self.post("/api/debts", {"name": "Nasiya", "kind": "nasiya", "total": 3_000_000, "monthly_payment": 500_000})
        rule = self.get("/api/debts/plan").json()["rule_70_20_10"]
        self.assertEqual(rule, {"home": 7_000_000, "debt": 2_000_000, "self": 1_000_000})

    def test_saboq_data_loads(self):
        from core.saboq_data import SABOQLAR

        Lesson.objects.all().delete()
        load_saboqlar(Lesson)
        self.assertEqual(Lesson.objects.count(), len(SABOQLAR))
        first = Lesson.objects.get(number=1)
        self.assertTrue(first.key_points_list and first.tasks_list)

    def test_plan_uses_monthly_income(self):
        self.post("/api/me", {"monthly_income": 8_000_000})
        self.post("/api/debts", {"name": "Kredit", "total": 5_000_000, "monthly_payment": 1_000_000})
        plan = self.get("/api/debts/plan").json()
        self.assertEqual(plan["income"], 8_000_000)
        self.assertEqual(plan["suggested_extra"], 8_000_000 - 800_000 - 1_000_000)


class PanelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        self.staff = User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True)
        self.plain = User.objects.create_user("oddiy", password="Kuchli-parol-2026")
        self.member = TgUser.objects.create(tg_id=4242, first_name="Karim", bot_started=True)
        self.member.expenses.create(amount=1000)
        from core import activity
        activity.log(self.member, "register", source="bot")
        make_saboqlar()

    def test_requires_staff(self):
        self.assertEqual(self.client.get("/boshqaruv/").status_code, 302)
        self.client.login(username="oddiy", password="Kuchli-parol-2026")
        self.assertEqual(self.client.get("/boshqaruv/").status_code, 302)

    def test_all_pages_render(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        lesson = Lesson.objects.get(number=1)
        for url in ["/boshqaruv/", "/boshqaruv/voronka/?period=all", "/boshqaruv/foydalanuvchilar/?q=Karim",
                    f"/boshqaruv/foydalanuvchilar/{self.member.uid}/", "/boshqaruv/amallar/", "/boshqaruv/kirishlar/",
                    "/boshqaruv/saboqlar/", f"/boshqaruv/saboqlar/{lesson.pk}/", "/boshqaruv/saboqlar/yangi/",
                    f"/boshqaruv/saboqlar/{lesson.pk}/korinish/", "/boshqaruv/xabarlar/", "/boshqaruv/baholar/",
                    "/boshqaruv/seo/", "/boshqaruv/foydalanuvchilar/?status=rated&sort=visits"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/boshqaruv/foydalanuvchilar/?q=4242"), "Karim")
        self.assertContains(self.client.get(f"/boshqaruv/foydalanuvchilar/?q={self.member.uid}"), "Karim")
        # ketma-ket raqamli havola endi ishlamaydi (taxmin qilib bo'lmaydi)
        self.assertEqual(self.client.get(f"/boshqaruv/foydalanuvchilar/{self.member.pk}/").status_code, 404)

    def test_user_actions_and_broadcast(self):
        from core.models import Broadcast

        self.client.login(username="boss", password="Kuchli-parol-2026")
        url = f"/boshqaruv/foydalanuvchilar/{self.member.uid}/amal/"
        self.client.post(url, {"action": "toggle_active"})
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.client.post(url, {"action": "note", "admin_note": "VIP"})
        self.member.refresh_from_db()
        self.assertEqual(self.member.admin_note, "VIP")

        self.client.post("/boshqaruv/xabarlar/", {"text": "Yangi imkoniyat!", "audience": "all"})
        self.assertEqual(Broadcast.objects.filter(text="Yangi imkoniyat!").count(), 1)
        lesson = Lesson.objects.get(number=1)
        self.client.post(f"/boshqaruv/saboqlar/{lesson.pk}/elon/")
        self.assertTrue(Broadcast.objects.filter(lesson=lesson).exists())

    def test_lesson_form_extracts_youtube_id(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        r = self.client.post("/boshqaruv/saboqlar/yangi/", {
            "number": 9, "title": "Sinov", "summary": "Mazmun", "task_type": "read", "is_published": "on",
            "tasks": "Videoni ko'ring",
            "youtube_id": "https://www.youtube.com/watch?v=ndVua0UiOSs&t=5s",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Lesson.objects.get(number=9).youtube_id, "ndVua0UiOSs")
        # yangi saboq darhol ko'rinadi (kesh tozalangan)
        self.assertIn(9, [l.number for l in __import__("core.services", fromlist=["x"]).published_lessons()])

    def test_funnel_counts(self):
        from panel.views import _funnel

        # Xarajat yozgan, lekin shartlarni qabul qilmagan — ketma-ket voronkada 2-bosqichda to'xtaydi
        TgUser.objects.create(tg_id=4343).expenses.create(amount=5)
        TgUser.objects.filter(pk=self.member.pk).update(accepted_disclaimer=True, income_type="salary")
        rows = _funnel("all")["rows"]
        self.assertEqual([r["count"] for r in rows[:5]], [2, 1, 1, 1, 0])
        self.assertTrue(all(r["of_prev"] <= 100 for r in rows))


class ReminderTests(BaseTestCase):
    def test_new_saboq_announcement(self):
        make_saboqlar()
        TgUser.objects.create(tg_id=11, bot_started=True)
        TgUser.objects.create(tg_id=12, bot_started=True, notify=False)
        api = mock.Mock()
        self.assertEqual(reminders.announce_lesson(api, Lesson.objects.get(number=2)), 1)
        self.assertIn("2-saboq", api.send.call_args[0][1])

    def test_morning_and_evening(self):
        make_saboqlar()
        user = TgUser.objects.create(tg_id=9, bot_started=True)
        api = mock.Mock()
        self.assertEqual(reminders.send_morning(api), 1)
        text = api.send.call_args[0][1]
        self.assertIn("1-saboqi", text)
        # qayta yuborilmaydi
        self.assertEqual(reminders.send_morning(api), 0)

        self.assertEqual(reminders.send_evening(api), 1)
        user.refresh_from_db()
        user.last_evening_date = None
        user.save()
        user.expenses.create(amount=5)
        self.assertEqual(reminders.send_evening(api), 0)  # bugun kiritgan — bezovta qilinmaydi

    def test_blocked_user_marked(self):
        from bot.telegram import TelegramError

        make_saboqlar()
        user = TgUser.objects.create(tg_id=10, bot_started=True)
        api = mock.Mock()
        api.send.side_effect = TelegramError("Forbidden", 403)
        reminders.send_morning(api)
        user.refresh_from_db()
        self.assertTrue(user.bot_blocked)

    def test_broadcast_queue_resumable(self):
        from core.models import Broadcast

        for i in range(5):
            TgUser.objects.create(tg_id=500 + i, bot_started=True)
        TgUser.objects.create(tg_id=600, bot_started=True, bot_blocked=True)  # yuborilmaydi
        b = Broadcast.objects.create(text="Salom <b>hammaga</b>")
        api = mock.Mock()
        with mock.patch("bot.reminders.SEND_DELAY", 0):
            # Juda kichik vaqt: 1 ta yuborib to'xtaydi, keyingi chaqiruvda davom etadi
            with mock.patch("bot.reminders.time.monotonic", side_effect=[0, 100, 100, 100]):
                reminders.process_broadcasts(api, time_budget=1)
            b.refresh_from_db()
            self.assertEqual((b.status, b.sent, b.total), ("sending", 1, 5))
            reminders.process_broadcasts(api)
        b.refresh_from_db()
        self.assertEqual((b.status, b.sent), ("done", 5))
        self.assertEqual(api.send.call_count, 5)
        self.assertIn("&lt;b&gt;", api.send.call_args[0][1])  # matn HTML sifatida emas, xavfsiz yuboriladi


class PageTests(BaseTestCase):
    def test_landing_public(self):
        make_saboqlar()
        r = self.client.get("/")
        self.assertContains(r, "landing.js")
        self.assertNotContains(r, "Niyat")  # saboqlar mazmuni faqat ro'yxatdan o'tganlarga
        self.assertContains(r, 'id="aloqa"')
        self.assertContains(r, "/kalkulyator/")
        self.assertContains(r, "ko'rsatuvidan ilhomlangan holda")
        self.assertNotContains(r, "Barcha huquqlar")

    def test_pages_render_separately(self):
        pages = {
            "/asosiy/": "home.js", "/hamyon/": "wallet.js", "/qarzlar/": "debts.js", "/saboqlar/": "lessons.js",
            "/saboqlar/4/": "lesson.js", "/haqida/": "about.js", "/kirish/": "login.js",
            "/jamgarma/": "savings.js", "/sozlamalar/": "settings.js",
        }
        for url, script in pages.items():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertNotIn("X-Frame-Options", r.headers)  # Telegram Web iframe
            self.assertContains(r, script)
            self.assertContains(r, 'id="i-safe"')  # SVG sprite

    def test_login_has_disclaimer(self):
        r = self.client.get("/kirish/")
        self.assertContains(r, "ko'rsatuvidan ilhomlangan holda")
        self.assertNotContains(r, "Barcha huquqlar")

    @override_settings(WEBAPP_URL="https://baraka.example.uz/")
    def test_bot_links_point_to_pages(self):
        from bot.telegram import webapp_url

        self.assertEqual(webapp_url("saboqlar/4/"), "https://baraka.example.uz/saboqlar/4/")
        self.assertEqual(webapp_url(), "https://baraka.example.uz/")


@override_settings(WEBAPP_URL="http://localhost:8000/")
class BotMenuTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = TgUser.objects.create(tg_id=3131, first_name="Aziz", bot_started=True, currency="USD",
                                          income_type="salary", monthly_income=1500, save_percent=10)
        self.api = mock.Mock()

    def tap(self, text):
        self.api.reset_mock()
        handlers.handle_update(self.api, {"message": {"chat": {"type": "private", "id": 3131},
                                                      "from": {"id": 3131, "first_name": "Aziz"}, "text": text}})
        return self.api.send.call_args[0][1]

    def test_start_shows_menu_keyboard(self):
        self.tap("/start")
        keyboard = self.api.send.call_args.kwargs["keyboard"]
        labels = [b["text"] for row in keyboard["keyboard"] for b in row]
        self.assertIn("💰 Qancha qoldi", labels)
        self.assertIn("📅 Shu hafta", labels)

    def test_left_and_week_reports(self):
        today = timezone.localdate()
        self.user.expenses.create(amount=405, category="food", date=today)
        self.user.savings.create(amount=150, bucket="guard", kind="deposit", date=today)
        text = self.tap("💰 Qancha qoldi")
        self.assertIn("$945", text)
        self.assertIn("≈ 11 340 000 so'm", text)
        week = self.tap("📅 Shu hafta")
        self.assertIn("$405", week)
        self.assertIn("Oziq-ovqat", week)
        self.assertTrue(self.user.activity.filter(action="bot_report").exists())

    def test_all_reports_and_commands(self):
        for text in ("📈 Daromadim", "🏦 Jamg'armam", "💳 Qarzlarim", "💱 Dollar kursi", "/qoldi", "/kurs"):
            self.assertTrue(self.tap(text))
        self.assertIn("12 000,00 so'm", self.tap("/kurs"))

    def test_left_asks_income_when_missing(self):
        self.user.income_type, self.user.monthly_income = "", 0
        self.user.save()
        self.assertIn("daromadingizni", self.tap("/qoldi"))

    def test_refresh_edits_message(self):
        handlers.handle_update(self.api, {"callback_query": {
            "id": "q", "data": "r:left", "from": {"id": 3131, "first_name": "Aziz"},
            "message": {"message_id": 9, "chat": {"id": 3131}}}})
        self.assertIn("$1 500", self.api.edit.call_args[0][2])


@override_settings(WEBAPP_URL="http://localhost:8000/")
class BotEntryTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = TgUser.objects.create(tg_id=3232, first_name="Nodir", bot_started=True,
                                          income_type="salary", monthly_income=8_000_000, save_percent=10)
        self.api = mock.Mock()

    def msg(self, text):
        self.api.reset_mock()
        handlers.handle_update(self.api, {"message": {"chat": {"type": "private", "id": 3232},
                                                      "from": {"id": 3232, "first_name": "Nodir"}, "text": text}})
        return self.api.send.call_args[0]

    def press(self, data):
        self.api.reset_mock()
        handlers.handle_update(self.api, {"callback_query": {
            "id": "q", "data": data, "from": {"id": 3232, "first_name": "Nodir"},
            "message": {"message_id": 7, "chat": {"id": 3232}}}})
        call = self.api.edit.call_args or self.api.send.call_args
        return call[0][2] if self.api.edit.called else call[0][1]

    def test_parse_amount(self):
        from bot.entries import parse_amount
        self.assertEqual(parse_amount("45000 non"), (45000, "non"))
        self.assertEqual(parse_amount("45 000"), (45000, ""))
        self.assertEqual(parse_amount("45.000 taksi"), (45000, "taksi"))
        self.assertEqual(parse_amount("1.5 mln"), (1_500_000, ""))
        self.assertEqual(parse_amount("8mln oylik"), (8_000_000, "oylik"))
        self.assertEqual(parse_amount("50k"), (50000, ""))
        self.assertEqual(parse_amount("salom"), (None, ""))
        self.assertEqual(parse_amount("0"), (None, ""))

    def test_menu_has_entry_buttons_without_lesson_and_notify(self):
        from bot.messages import main_keyboard
        labels = [b["text"] for row in main_keyboard()["keyboard"] for b in row]
        self.assertIn("➖ Xarajat", labels)
        self.assertIn("➕ Daromad", labels)
        self.assertNotIn("📚 Bugungi saboq", labels)
        self.assertNotIn("🔔 Eslatmalar", labels)

    def test_expense_flow_and_undo(self):
        self.msg("➖ Xarajat")
        _, text, buttons = self.msg("45 000 non")
        self.assertIn("Qaysi toifaga", text)
        self.assertIn("c:food", [b["callback_data"] for row in buttons for b in row])
        self.assertIn("Xarajat yozildi", self.press("c:food"))
        expense = self.user.expenses.get()
        self.assertEqual((expense.amount, expense.category, expense.note), (45000, "food", "non"))
        self.press(f"u:e:{expense.pk}")
        self.assertFalse(self.user.expenses.exists())

    def test_bare_amount_then_income_and_pay_yourself(self):
        _, text, _ = self.msg("8000000")
        self.assertIn("Bu nima edi", text)
        self.press("k:income")
        self.assertIn("o'zingizga to'lang", self.press("i:salary"))
        income = self.user.incomes.get()
        self.press(f"s:{income.pk}")
        self.assertEqual(self.user.savings.get().amount, 800_000)
        self.assertIn("allaqachon", self.press(f"s:{income.pk}"))

    def test_bad_amount_and_cancel(self):
        self.msg("➕ Daromad")
        self.assertIn("tushunmadim", self.msg("ko'p")[1])
        self.press("x")
        self.assertIn("eskirgan", self.press("i:salary"))
        self.assertFalse(self.user.incomes.exists())

    def test_foreign_entry_cannot_be_undone(self):
        other = TgUser.objects.create(tg_id=9999)
        e = other.expenses.create(amount=100)
        self.press(f"u:e:{e.pk}")
        self.assertTrue(other.expenses.exists())


class SecurityTests(ApiTestCase):
    def test_token_uses_uuid_and_logout_all_revokes(self):
        from django.core import signing
        from core.auth import TOKEN_SALT
        token = self.auth["HTTP_AUTHORIZATION"][7:]
        payload = signing.loads(token, salt=TOKEN_SALT)
        self.assertEqual(payload["u"], str(self.user.uid))
        self.assertNotIn("uid", payload)  # ketma-ket raqam tokenda yo'q
        self.assertEqual(self.post("/api/me/logout-all").status_code, 200)
        self.assertEqual(self.get("/api/me").status_code, 401)  # eski token bekor

    def test_disabled_user_token_revoked(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.get("/api/me").status_code, 401)

    def test_forged_token_rejected(self):
        from django.core import signing
        from core.auth import TOKEN_SALT
        other = TgUser.objects.create(tg_id=5555)
        forged = signing.dumps({"u": str(other.uid), "v": 1}, salt="boshqa-tuz")
        self.assertEqual(self.client.get("/api/me", HTTP_AUTHORIZATION=f"Bearer {forged}").status_code, 401)
        # eski formatdagi (raqamli) token ham ishlamaydi
        old = signing.dumps({"uid": other.pk}, salt=TOKEN_SALT, compress=True)
        self.assertEqual(self.client.get("/api/me", HTTP_AUTHORIZATION=f"Bearer {old}").status_code, 401)

    def test_rate_limit_and_body_size(self):
        with mock.patch("core.api.activity.allow", return_value=False):
            self.assertEqual(self.get("/api/me").status_code, 429)
        big = {"amount": 1000, "note": "x" * 40000}
        self.assertEqual(self.post("/api/expenses", big).status_code, 413)

    def test_text_is_cleaned_and_html_escaped_in_panel(self):
        self.post("/api/expenses", {"amount": 500, "note": "<script>alert(1)</script>‮\x00non"})
        note = self.user.expenses.get().note
        self.assertNotIn("\x00", note)
        self.assertNotIn("‮", note)
        from django.contrib.auth.models import User
        User.objects.create_user("boss2", password="Kuchli-parol-2026", is_staff=True)
        self.client.login(username="boss2", password="Kuchli-parol-2026")
        html = self.client.get(f"/boshqaruv/foydalanuvchilar/{self.user.uid}/").content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sql_injection_in_search_is_harmless(self):
        from django.contrib.auth.models import User
        User.objects.create_user("boss3", password="Kuchli-parol-2026", is_staff=True)
        self.client.login(username="boss3", password="Kuchli-parol-2026")
        r = self.client.get("/boshqaruv/foydalanuvchilar/", {"q": "' OR 1=1; DROP TABLE core_tguser; --"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Hech kim topilmadi")
        self.assertTrue(TgUser.objects.exists())

    def test_spoofed_forwarded_for_is_ignored(self):
        from django.test import RequestFactory
        from core.activity import client_ip
        req = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="9.9.9.9")
        self.assertEqual(client_ip(req), "9.9.9.9")
        req = RequestFactory().get("/", HTTP_X_REAL_IP="5.5.5.5", HTTP_X_FORWARDED_FOR="1.2.3.4")
        self.assertEqual(client_ip(req), "5.5.5.5")

    def test_security_headers(self):
        app = self.client.get("/asosiy/")
        self.assertIn("frame-ancestors 'self' https://web.telegram.org", app["Content-Security-Policy"])
        self.assertIn("object-src 'none'", app["Content-Security-Policy"])
        self.assertEqual(app["X-Content-Type-Options"], "nosniff")
        api = self.get("/api/me")
        self.assertEqual(api["Cache-Control"], "no-store")


class RatingTests(ApiTestCase):
    def test_asked_after_third_visit_then_not_again(self):
        self.assertFalse(self.get("/api/me").json()["ask_rating"])
        TgUser.objects.filter(pk=self.user.pk).update(visits=3)
        self.assertTrue(self.get("/api/me").json()["ask_rating"])
        self.post("/api/feedback/shown")
        self.assertFalse(self.get("/api/me").json()["ask_rating"])  # bir hafta so'ralmaydi

    def test_asked_after_few_days(self):
        TgUser.objects.filter(pk=self.user.pk).update(created_at=timezone.now() - dt.timedelta(days=4))
        self.assertTrue(self.get("/api/me").json()["ask_rating"])

    def test_feedback_saved_and_validated(self):
        TgUser.objects.filter(pk=self.user.pk).update(visits=5)
        self.assertEqual(self.post("/api/feedback", {"rating": 7}).status_code, 400)
        self.assertEqual(self.post("/api/feedback", {"rating": 5, "comment": "Zo'r ilova"}).status_code, 200)
        self.assertEqual(self.user.feedback.get().comment, "Zo'r ilova")
        self.assertFalse(self.get("/api/me").json()["ask_rating"])

    def test_visits_counted_after_long_break(self):
        TgUser.objects.filter(pk=self.user.pk).update(last_seen=timezone.now() - dt.timedelta(hours=2))
        TgUser.upsert_from_telegram({"id": self.user.tg_id, "first_name": "Ali"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.visits, 2)
        TgUser.upsert_from_telegram({"id": self.user.tg_id, "first_name": "Ali"})  # darhol qayta — yangi tashrif emas
        self.user.refresh_from_db()
        self.assertEqual(self.user.visits, 2)


class SeoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True, is_superuser=True)
        self.client.login(username="boss", password="Kuchli-parol-2026")

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /api/", robots)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", robots)
        self.assertContains(self.client.get("/sitemap.xml"), "<loc>http://testserver/</loc>")

    def test_settings_change_meta_tags(self):
        r = self.client.post("/boshqaruv/seo/", {
            "seo-site_url": "https://baraka.uz", "seo-title": "Baraka Daftari — moliyaviy daftar",
            "seo-description": "Tavsif", "seo-google_verification": '<meta name="google-site-verification" content="AbC123xyz_-Q" />',
            "seo-allow_indexing": "on",
        })
        self.assertEqual(r.status_code, 302)
        landing = self.client.get("/").content.decode()
        self.assertIn("<title>Baraka Daftari — moliyaviy daftar</title>", landing)
        self.assertIn('content="AbC123xyz_-Q"', landing)
        self.assertIn('<link rel="canonical" href="https://baraka.uz/">', landing)

    def test_google_verification_file_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("google1a2b3c4d5e6f7a8b.html", b"google-site-verification: google1a2b3c4d5e6f7a8b.html")
        self.client.post("/boshqaruv/seo/", {"section": "file", "vf-file": f})
        r = self.client.get("/google1a2b3c4d5e6f7a8b.html")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "google-site-verification")
        self.assertEqual(self.client.get("/google0000aaaa1111.html").status_code, 404)

    def test_bad_verification_files_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.models import VerificationFile
        self.client.post("/boshqaruv/seo/", {"section": "file", "vf-file": SimpleUploadedFile("../../settings.py", b"x")})
        self.client.post("/boshqaruv/seo/", {"section": "file", "vf-file": SimpleUploadedFile("google12345678ab.html", b"<script>steal()</script>")})
        self.assertFalse(VerificationFile.objects.exists())


class PanelSecurityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        self.boss = User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True)
        self.member = TgUser.objects.create(tg_id=4242, first_name="=cmd|' /C calc'!A0")

    def test_login_locked_after_failures(self):
        for _ in range(5):
            self.client.post("/boshqaruv/kirish/", {"username": "boss", "password": "notogri"})
        r = self.client.post("/boshqaruv/kirish/", {"username": "boss", "password": "Kuchli-parol-2026"})
        self.assertEqual(r.status_code, 403)  # to'g'ri parol bilan ham 15 daqiqa kutish kerak

    def test_django_admin_uses_panel_login(self):
        r = self.client.get("/admin/login/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/boshqaruv/kirish/", r["Location"])

    def test_csv_export_superuser_only_and_injection_safe(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        self.assertEqual(self.client.get("/boshqaruv/foydalanuvchilar/?export=csv").status_code, 403)
        self.boss.is_superuser = True
        self.boss.save()
        body = self.client.get("/boshqaruv/foydalanuvchilar/?export=csv").content.decode("utf-8-sig")
        self.assertIn("'=cmd", body)  # formula sifatida bajarilmaydi

    def test_lesson_delete_requires_number_when_completed(self):
        make_saboqlar()
        self.client.login(username="boss", password="Kuchli-parol-2026")
        lesson = Lesson.objects.get(number=1)
        LessonProgress.objects.create(user=self.member, lesson=lesson)
        self.client.post(f"/boshqaruv/saboqlar/{lesson.pk}/amal/", {"action": "delete"})
        self.assertTrue(Lesson.objects.filter(pk=lesson.pk).exists())
        self.client.post(f"/boshqaruv/saboqlar/{lesson.pk}/amal/", {"action": "delete", "confirm": "1"})
        self.assertFalse(Lesson.objects.filter(pk=lesson.pk).exists())

    def test_invalid_youtube_link_rejected(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        r = self.client.post("/boshqaruv/saboqlar/yangi/", {
            "number": 20, "title": "X", "summary": "Y", "task_type": "read", "tasks": "Z",
            "youtube_id": "javascript:alert(1)",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Lesson.objects.filter(number=20).exists())


class CalculatorPageTests(BaseTestCase):
    def test_public_and_indexable(self):
        r = self.client.get("/kalkulyator/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'content="index, follow"')
        self.assertContains(r, "js/calc.js")
        self.assertContains(self.client.get("/sitemap.xml"), "/kalkulyator/")
        self.assertIn("Allow: /kalkulyator/", self.client.get("/robots.txt").content.decode())
        # ilova sahifalari esa indekslanmaydi
        self.assertContains(self.client.get("/hamyon/"), 'content="noindex, nofollow"')


class SiteSettingsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True)
        self.client.login(username="boss", password="Kuchli-parol-2026")

    def test_links_saved_and_public(self):
        self.assertEqual(self.client.get("/boshqaruv/sozlamalar/").status_code, 200)
        r = self.client.post("/boshqaruv/sozlamalar/", {
            "author_youtube": "https://www.youtube.com/@kanal", "contact_telegram": "https://t.me/baraka_admin",
            "contact_phone": "+998 90 123 45 67", "contact_email": "info@barakadaftari.uz",
        })
        self.assertEqual(r.status_code, 302)
        data = self.client.get("/api/site").json()
        self.assertEqual(data["author"], {"youtube": "https://www.youtube.com/@kanal"})
        self.assertEqual(data["contact"]["telegram"], "https://t.me/baraka_admin")
        self.assertEqual(data["contact"]["telegram_name"], "@baraka_admin")
        self.assertEqual(data["contact"]["phone"], "+998901234567")

    def test_unsafe_links_rejected(self):
        from core.models import SiteSettings
        r = self.client.post("/boshqaruv/sozlamalar/", {"author_instagram": "http://instagram.com/x", "contact_telegram": "<script>"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SiteSettings.load().author_instagram, "")

    def test_about_and_calculator_public(self):
        self.client.logout()
        self.assertEqual(self.client.get("/haqida/").status_code, 200)
        self.assertEqual(self.client.get("/api/site").status_code, 200)


class ReportTests(ApiTestCase):
    def test_week_and_month_report(self):
        today = timezone.localdate()
        self.user.incomes.create(amount=1_000_000, date=today)
        self.user.expenses.create(amount=200_000, category="food", need="zarur", date=today)
        self.user.expenses.create(amount=50_000, category="events", need="havas", date=today - dt.timedelta(days=2))
        self.user.expenses.create(amount=100_000, category="food", date=today - dt.timedelta(days=9))  # oldingi 7 kun
        self.user.savings.create(amount=100_000, bucket="guard", kind="deposit", date=today)
        r = self.get("/api/report?period=7").json()
        self.assertEqual((r["days"], r["income"], r["expense"], r["saved"]), (7, 1_000_000, 250_000, 100_000))
        self.assertEqual(r["net"], 650_000)
        self.assertEqual(r["by_category"][0]["key"], "food")
        self.assertEqual(r["by_need"]["havas"], 50_000)
        self.assertEqual(r["prev_expense"], 100_000)
        self.assertEqual(r["change_pct"], 150)
        self.assertEqual(len(r["daily"]), 7)
        self.assertEqual(r["top"][0]["amount"], 200_000)
        self.assertEqual(self.get("/api/report?period=10").json()["expense"], 350_000)
        month = self.get(f"/api/report?period=month&month={today:%Y-%m}").json()
        self.assertIn("month", month)
        self.assertEqual(self.get("/api/report?period=999").status_code, 400)

    def test_pages(self):
        self.assertContains(self.client.get("/hisobot/"), "report.js")
        self.assertContains(self.client.get("/aloqa/"), "contact.js")


class AdminsAndBackupTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        import tempfile
        from django.contrib.auth.models import User
        self.boss = User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True, is_superuser=True)
        self.helper = User.objects.create_user("yordamchi", password="Kuchli-parol-2026", is_staff=True)
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(BACKUP_DIR=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_only_superuser(self):
        self.client.login(username="yordamchi", password="Kuchli-parol-2026")
        for url in ("/boshqaruv/adminlar/", "/boshqaruv/zaxira/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_create_admin_block_and_rules(self):
        from django.contrib.auth.models import User
        self.client.login(username="boss", password="Kuchli-parol-2026")
        self.assertEqual(self.client.get("/boshqaruv/adminlar/").status_code, 200)
        r = self.client.post("/boshqaruv/adminlar/", {"username": "yangi_admin", "role": "staff",
                                                      "password1": "Juda-Kuchli-77", "password2": "Juda-Kuchli-77"})
        self.assertEqual(r.status_code, 302)
        new = User.objects.get(username="yangi_admin")
        self.assertTrue(new.is_staff and not new.is_superuser and new.check_password("Juda-Kuchli-77"))
        # zaif parol qabul qilinmaydi
        self.client.post("/boshqaruv/adminlar/", {"username": "zaif", "role": "staff", "password1": "12345", "password2": "12345"})
        self.assertFalse(User.objects.filter(username="zaif").exists())
        # bloklash
        self.client.post(f"/boshqaruv/adminlar/{new.pk}/amal/", {"action": "toggle_active"})
        new.refresh_from_db()
        self.assertFalse(new.is_active)
        # o'zini bloklay olmaydi
        self.client.post(f"/boshqaruv/adminlar/{self.boss.pk}/amal/", {"action": "toggle_active"})
        self.boss.refresh_from_db()
        self.assertTrue(self.boss.is_active)

    def test_backup_create_download_delete(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        self.client.post("/boshqaruv/zaxira/", {"action": "create"})
        from core import backup
        items = backup.list_backups()
        self.assertEqual(len(items), 1)
        name = items[0]["name"]
        r = self.client.get(f"/boshqaruv/zaxira/yuklab-olish/{name}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        r.close()
        # begona fayl nomi ruxsat etilmaydi
        self.assertEqual(self.client.get("/boshqaruv/zaxira/yuklab-olish/..%2F.env").status_code, 404)
        self.client.post("/boshqaruv/zaxira/", {"action": "delete", "name": name})
        self.assertEqual(backup.list_backups(), [])

    @override_settings(BACKUP_CHAT_IDS=[111, 222], BOT_TOKEN="test-token")
    def test_backup_sent_to_telegram(self):
        from django.core.management import call_command

        from core import backup
        with mock.patch("bot.telegram.BotAPI.send_document") as send:
            call_command("send_backup", stdout=io.StringIO())
        self.assertEqual([c.args[0] for c in send.call_args_list], [111, 222])
        self.assertEqual(len(backup.list_backups()), 1)
        # panel tugmasi ham yuboradi; begona nom o'tmaydi
        self.client.login(username="boss", password="Kuchli-parol-2026")
        self.assertContains(self.client.get("/boshqaruv/zaxira/"), 'value="telegram"')
        name = backup.list_backups()[0]["name"]
        with mock.patch("bot.telegram.BotAPI.send_document") as send:
            self.client.post("/boshqaruv/zaxira/", {"action": "telegram", "name": name})
            self.client.post("/boshqaruv/zaxira/", {"action": "telegram", "name": "../.env"})
        self.assertEqual(send.call_count, 2)

    @override_settings(BACKUP_CHAT_IDS=[111], BOT_TOKEN="test-token")
    def test_backup_failure_alerts_admin(self):
        from django.core.management import CommandError, call_command

        from bot.telegram import TelegramError
        with mock.patch("bot.telegram.BotAPI.send_document", side_effect=TelegramError("chat not found")), \
                mock.patch("bot.telegram.BotAPI.send") as alert:
            with self.assertRaises(CommandError):
                call_command("send_backup", stdout=io.StringIO())
        self.assertIn("chat not found", alert.call_args[0][1])

    def test_send_backup_requires_config(self):
        from django.core.management import CommandError, call_command
        with override_settings(BACKUP_CHAT_IDS=[]), self.assertRaises(CommandError):
            call_command("send_backup", stdout=io.StringIO())

    def test_blocked_user_cannot_use_bot(self):
        api = mock.Mock()
        TgUser.objects.create(tg_id=777, first_name="X", is_active=False, bot_started=True)
        handlers.handle_update(api, {"message": {"chat": {"type": "private", "id": 777},
                                                 "from": {"id": 777, "first_name": "X"}, "text": "50000 non"}})
        self.assertIn("bloklangan", api.send.call_args[0][1])
        self.assertFalse(TgUser.objects.get(tg_id=777).expenses.exists())

    def test_django_admin_pages(self):
        self.client.login(username="boss", password="Kuchli-parol-2026")
        TgUser.objects.create(tg_id=888, first_name="Y")
        for url in ("/admin/", "/admin/core/tguser/", "/admin/core/expense/", "/admin/core/feedback/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)


class TelegramProfileTests(BaseTestCase):
    def test_photo_and_premium(self):
        # Mini App initData: rasm + Premium
        u, _ = TgUser.upsert_from_telegram({"id": 55, "first_name": "Ali", "is_premium": True,
                                            "photo_url": "https://t.me/i/userpic/320/ali.svg"})
        self.assertTrue(u.is_premium)
        self.assertEqual(u.photo_url, "https://t.me/i/userpic/320/ali.svg")
        # Bot xabari: `from` da photo_url yo'q — rasm o'chmasligi kerak; is_premium yo'q = Premium emas
        u, _ = TgUser.upsert_from_telegram({"id": 55, "first_name": "Ali"})
        self.assertEqual(u.photo_url, "https://t.me/i/userpic/320/ali.svg")
        self.assertFalse(u.is_premium)
        # Faqat https havola saqlanadi
        u, _ = TgUser.upsert_from_telegram({"id": 55, "first_name": "Ali", "photo_url": "javascript:alert(1)"})
        self.assertEqual(u.photo_url, "")

    def test_panel_shows_avatar(self):
        from django.contrib.auth.models import User
        User.objects.create_user("boss", password="Kuchli-parol-2026", is_staff=True, is_superuser=True)
        u = TgUser.objects.create(tg_id=56, first_name="Vali", is_premium=True, photo_url="https://t.me/i/userpic/320/v.svg")
        self.client.login(username="boss", password="Kuchli-parol-2026")
        r = self.client.get(f"/boshqaruv/foydalanuvchilar/{u.uid}/")
        self.assertContains(r, 'src="https://t.me/i/userpic/320/v.svg"')
        self.assertContains(r, "Telegram Premium")
        self.assertContains(self.client.get("/boshqaruv/foydalanuvchilar/?status=premium"), "Vali")
        self.assertEqual(self.client.get("/boshqaruv/").status_code, 200)


@override_settings(BOT_TOKEN=BOT_TOKEN, BOT_USERNAME="baraka_test_bot")
class DebtLinkTests(ApiTestCase):
    """Qarzni bog'lash: havola → botda tasdiq → to'lov tasdig'i → uzish."""

    def setUp(self):
        super().setUp()
        self.user.bot_started = True
        self.user.save()
        self.vali = TgUser.objects.create(tg_id=2002, first_name="Vali", bot_started=True)
        self.vali_auth = {"HTTP_AUTHORIZATION": f"Bearer {make_api_token(self.vali)}"}
        notify = mock.patch("core.debtlink.notify", return_value=True)
        self.notify = notify.start()
        self.addCleanup(notify.stop)

    def bot(self, tg_from, text=None, data=None):
        api = mock.Mock()
        if text is not None:
            update = {"message": {"chat": {"type": "private", "id": tg_from["id"]}, "from": tg_from, "text": text}}
        else:
            update = {"callback_query": {"id": "1", "from": tg_from, "data": data}}
        handlers.handle_update(api, update)
        return api

    def token_of(self, url):
        return url.split("start=q_")[1]

    def test_borrower_links_debt_and_lender_reviews_payment(self):
        debt = self.post("/api/debts", {"name": "Validan", "kind": "personal", "total": 1_000_000}).json()["debt"]
        self.assertTrue(debt["linkable"])
        r = self.post(f"/api/debts/{debt['id']}/invite").json()
        self.assertTrue(r["url"].startswith("https://t.me/baraka_test_bot?start=q_"))
        token = self.token_of(r["url"])

        # O'zi bosolmaydi; Vali botda ochadi va tasdiqlaydi
        self.assertIn("o'zingiz", self.bot({"id": 1001, "first_name": "Ali"}, data=f"dl:{token}:y").send.call_args[0][1])
        api = self.bot({"id": 2002, "first_name": "Vali"}, text=f"/start q_{token}")
        self.assertIn("1 000 000", api.send.call_args[0][1])
        self.bot({"id": 2002, "first_name": "Vali"}, data=f"dl:{token}:y")
        self.assertEqual(Debt.objects.get(pk=debt["id"]).lender, self.vali)
        # Havola ikkinchi marta ishlamaydi
        api = self.bot({"id": 3003, "first_name": "Begona"}, text=f"/start q_{token}")
        self.assertIn("eskirgan", api.send.call_args[0][1])

        # Bog'langan qarz: o'chirib ham, summasini o'zgartirib ham bo'lmaydi
        self.assertEqual(self.client.delete(f"/api/debts/{debt['id']}", **self.auth).status_code, 400)
        self.assertEqual(self.post(f"/api/debts/{debt['id']}", {"total": 10}).status_code, 400)

        # To'lov → Vali'ga so'rov; Vali'ning ro'yxatida ko'rinadi
        self.post(f"/api/debts/{debt['id']}/pay", {"amount": 300_000})
        lent = self.client.get("/api/debts", **self.vali_auth).json()["lent"]
        self.assertEqual(lent[0]["borrower"], "Ali")
        self.assertEqual(lent[0]["paid"], 300_000)
        pay_id = lent[0]["pending"][0]["id"]
        # Ali o'z to'lovini o'zi tasdiqlay olmaydi
        self.assertEqual(self.post(f"/api/debts/payments/{pay_id}/review", {"ok": True}).status_code, 400)
        # Vali rad etadi → summa qarzga qaytadi
        self.bot({"id": 2002, "first_name": "Vali"}, data=f"dp:{pay_id}:n")
        self.assertEqual(Debt.objects.get(pk=debt["id"]).paid, 0)
        self.assertEqual(DebtPayment.objects.get(pk=pay_id).status, "rejected")

        # Uzish: endi o'chirsa bo'ladi
        r = self.client.post(f"/api/debts/{debt['id']}/unlink", "{}", content_type="application/json", **self.vali_auth)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(Debt.objects.get(pk=debt["id"]).lender)
        self.assertEqual(self.client.delete(f"/api/debts/{debt['id']}", **self.auth).status_code, 200)

    def test_lender_invite_creates_debt_for_borrower(self):
        r = self.client.post("/api/debts/lend", json.dumps({"note": "Ali, telefon uchun", "amount": 500_000}),
                             content_type="application/json", **self.vali_auth).json()
        self.assertEqual(len(self.client.get("/api/debts", **self.vali_auth).json()["invites"]), 1)
        token = self.token_of(r["url"])
        # Yangi odam (hali ro'yxatdan o'tmagan) ham havola orqali kirib tasdiqlay oladi
        self.bot({"id": 4004, "first_name": "Yangi"}, text=f"/start q_{token}")
        self.bot({"id": 4004, "first_name": "Yangi"}, data=f"dl:{token}:y")
        newbie = TgUser.objects.get(tg_id=4004)
        debt = newbie.debts.get()
        self.assertEqual((debt.total, debt.lender), (500_000, self.vali))
        data = self.client.get("/api/debts", **self.vali_auth).json()
        self.assertEqual((len(data["lent"]), data["invites"]), (1, []))

    def test_decline_and_rules(self):
        credit = Debt.objects.create(user=self.user, name="Bank", kind="credit", total=100)
        self.assertEqual(self.post(f"/api/debts/{credit.pk}/invite").status_code, 400)
        r = self.client.post("/api/debts/lend", json.dumps({"note": "Ali", "amount": 1000}),
                             content_type="application/json", **self.vali_auth).json()
        token = self.token_of(r["url"])
        self.bot({"id": 1001, "first_name": "Ali"}, data=f"dl:{token}:n")
        self.assertEqual(DebtLink.objects.get(token=token).status, "declined")
        self.assertFalse(self.user.debts.filter(lender=self.vali).exists())
        # Begona odam boshqa qarzni bog'lay olmaydi / ko'ra olmaydi
        other = Debt.objects.create(user=self.vali, name="X", kind="personal", total=100)
        self.assertEqual(self.post(f"/api/debts/{other.pk}/invite").status_code, 404)
        self.assertEqual(self.post(f"/api/debts/{other.pk}/unlink").status_code, 404)
