"""Abdukarim Mirzayevning «Baraka Daftari» saboqlari.

Har hafta yangi video chiqqanda shu ro'yxatga yangi saboq qo'shiladi va
`python manage.py load_saboqlar` ishga tushiriladi (yoki /admin/ → Saboqlar).

Maydonlar:
    number        — saboq raqami (1, 2, 3 ...)
    title         — mavzu
    published_on  — video chiqqan sana, "YYYY-MM-DD" (ixtiyoriy)
    youtube_id    — https://youtu.be/<ID> dagi ID (ixtiyoriy)
    summary       — qisqacha mazmun
    key_points    — saboqlar ro'yxati
    tasks         — nima qilish kerak (vazifalar ro'yxati)
    task_type     — ilovadagi amal: read, note, income, expense, save, debt_list, debt_plan, debt_pay
    note_prompt   — task_type="note" bo'lsa, foydalanuvchiga beriladigan savol

Namuna:
    dict(
        number=1,
        title="...",
        published_on="2026-09-07",
        youtube_id="",
        summary="...",
        key_points=["...", "..."],
        tasks=["...", "..."],
        task_type="income",
    ),
"""

SABOQLAR = [
    dict(
        number=1,
        title="Avval o'zingga to'la",
        youtube_id="ndVua0UiOSs",
        summary=(
            "«Baraka daftari» — hayotimizdagi iqtisodiy qiyinchiliklarga halol yechim izlash yo'lidagi urinish. "
            "Bu tez boyish usuli emas, boylikning ilmi. Bu diniy fatvo emas, ta'limiy asar.\n\n"
            "Taksichi Anvarning hayoti misolida ko'pchiligimizni qiynaydigan savolga javob izlaymiz: nega oylab "
            "tinmay mehnat qilamiz, lekin cho'ntagimizda baraka yo'q? Sobir hojining hikmati va Anvarning "
            "«Baraka daftari»dagi ilk yozuvi sizning ham hayotingizni o'zgartirishi mumkin."
        ),
        key_points=[
            "Halol boyishning 1-qonuni: avval o'zingga to'la.",
            "Har oy ijara, oziq-ovqat va boshqalarga to'laysiz. O'zingizga-chi — sizga nima qoladi?",
            "Daromadingizning o'ndan birini (10%) birinchi bo'lib o'zingizga ajrating.",
            "Oilaviy hisob-kitob muhim: pul qayerga ketayotganini oila bilan birga ko'ring.",
        ],
        tasks=[
            "Har oy nimalarga to'lashingizni yozing: ijara, oziq-ovqat, kommunal va boshqalar",
            "O'tgan oy pulingiz qayerga ketganini oilangiz bilan birga yozing va hisoblang",
            "Zaxira uchun alohida hamyon yoki karta oching",
            "Daromadingizning o'ndan birini (10%) shu hamyonga o'tkazing",
        ],
        task_type="save",
    ),
    dict(
        number=2,
        title="Xurjunning teshigini yama",
        youtube_id="__K51uPvsms",
        summary=(
            "Isrof, baxillik va iqtisod orasidagi farq nimada? Xarajatni «Zarur — Kerak — Havas» tarzida "
            "saralashni o'rganamiz.\n\n"
            "Boy bo'lishning 2-qonuni: xurjunning teshigini yama. Xarajatni yozmaguningizcha uni boshqara olmaysiz. "
            "Shu hafta har bir xarajatingizni yozib boring — ehtimol, sizda ham kamida bitta «unutilgan tuynuk» topiladi!"
        ),
        key_points=[
            "Boy bo'lishning 2-qonuni: xurjunning teshigini yama.",
            "Xarajatni yozmaguningizcha uni boshqara olmaysiz.",
            "Isrof, baxillik va iqtisod — uch xil narsa. Maqsad baxillik emas, iqtisod.",
            "Har bir xarajat uch turga bo'linadi: Zarur, Kerak, Havas.",
            "Havasga chek qo'ying, lekin havasni o'ldirmang.",
        ],
        tasks=[
            "Bir hafta davomida har bir xarajatingizni Hamyonga yozib boring",
            "Har bir xarajatni «Zarur», «Kerak» yoki «Havas» deb belgilang",
            "Hafta oxirida «teshik»dan qancha pul chiqib ketganini aniqlang",
        ],
        task_type="expense",
        note_prompt="Qaysi «unutilgan tuynuk»ni topdingiz? Bir haftada havasga qancha ketdi?",
    ),
    dict(
        number=3,
        title="Ko'rinmas o'g'ri: narx-navo va ishlayotgan pul",
        youtube_id="JCmvlnR4RIc",
        summary=(
            "Narx-navo — inflyatsiya — jamg'armani sezdirmasdan kemiradigan «sichqon». Pul ikki xil yashaydi: "
            "yotgan pul va ishlayotgan pul. Yotgan pulni narx-navo yeydi, ishlayotgan pul esa ko'payadi.\n\n"
            "Pul puldan tug'ilmaydi — pul mehnatdan, savdodan, sheriklikdan tug'ilsin. Ter, mol, tavakkal — "
            "shu uchtasidan biri bor joyda foyda baraka bo'ladi."
        ),
        key_points=[
            "Boy bo'lishning 3-qonuni: ko'rinmas o'g'ridan — narx-navodan — jamg'armangizni asrang.",
            "Narx-navo (inflyatsiya) — jamg'armani kemiradigan «sichqon».",
            "Pul ikki xil yashaydi: yotgan pul va ishlayotgan pul.",
            "Yotgan pulni narx-navo yeydi, ishlayotgan pul o'zi ko'payadi.",
            "Pul puldan tug'ilmaydi: mehnatdan, savdodan, sheriklikdan tug'ilsin.",
            "Ter, mol, tavakkal — shu uchtasidan biri bor joyda foyda baraka bo'ladi.",
            "Jamg'armani ikkiga bo'ling: qo'riqchi pul (3–6 oylik xarajatga yetadigan, og'ir kun uchun) va o'sadigan pul.",
            "Yelkada qarz turib teshikni yamab bo'lmaydi. Yaraning kattaligini bilmagan uni davolay olmaydi.",
        ],
        tasks=[
            "O'zingiz bilgan 3–4 ta mahsulot narxini uch yil avvalgisi bilan solishtiring (masalan, un)",
            "Jamg'armangizni ikkiga ajrating: qo'riqchi pul va o'sadigan pul",
            "Barcha qarzlaringiz ro'yxatini tuzing: kimga, qancha, qachongacha",
        ],
        task_type="debt_list",
        note_prompt="Qaysi mahsulotning narxi sizni eng ko'p hayratga soldi? Uch yil oldin qancha edi, bugun qancha?",
    ),
    dict(
        number=4,
        title="Ribodan qoch, qarzga tushsang reja bilan chiq",
        youtube_id="mz7VJYEja6A",
        summary=(
            "To'rtinchi qonun: ribodan qoch, qarzga tushsang reja bilan chiq. To'y elda uch kunlik gap, qarz esa "
            "olti yillik kishan.\n\n"
            "Sobir hojining qoidasi oddiy: topganingizning 70 foizi ro'zg'orga, 20 foizi qarz ustiga qo'shimcha "
            "to'lovga, 10 foizi — qarzdor bo'lsangiz ham — o'zingizga. Qarz — o'tmishga to'lov, jamg'arma esa "
            "kelajakka to'lov."
        ),
        key_points=[
            "Halol boyishning 4-qonuni: ribodan qoch, qarzga tushsang reja bilan chiq.",
            "Qarzni foizga olmang.",
            "Qarz — o'tmishga to'lov, jamg'arma — kelajakka to'lov.",
            "Qarzga botgan odamning yo'li uch bo'lak: 70% ro'zg'orga, 20% kechiktirmay qarzga qo'shib to'lanadi, 10% o'zingizga.",
            "To'y elda uch kunlik gap, qarz esa olti yillik kishan. To'g'ri ishga odamlar har doim ergashadi.",
        ],
        tasks=[
            "Qarzlar ro'yxatingizni hisoblang va har biriga qo'shimcha to'lovni belgilang (daromadning 20%)",
            "Qarzlar bo'limida 70/20/10 qoidasi bo'yicha rejangizni ko'ring",
            "Uyingizdagi ishlatilmaydigan va sotsa bo'ladigan biror narsani sotib, pulini qarzga ishlating",
        ],
        task_type="debt_plan",
        note_prompt="Mahallangizda qarzsiz, sodda to'y qilgan odam bormi?",
    ),
]


def load_saboqlar(Lesson, items=None):
    """Saboqlarni yaratadi yoki yangilaydi. YouTube ID bo'sh bo'lsa, admin kiritgan ID saqlanib qoladi."""
    count = 0
    for data in items if items is not None else SABOQLAR:
        data = dict(data)
        number = data.pop("number")
        data["key_points"] = "\n".join(data.get("key_points") or [])
        data["tasks"] = "\n".join(data.get("tasks") or [])
        if not data.get("youtube_id"):
            data.pop("youtube_id", None)
        Lesson.objects.update_or_create(number=number, defaults=data)
        count += 1
    return count
