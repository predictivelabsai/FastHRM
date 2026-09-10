"""Lightweight bilingual (Estonian / English) copy for FastHRM public pages.

Estonian is the primary market and the default. Language is chosen from the
``?lang=`` query parameter, then the session, then falls back to Estonian.
"""
from __future__ import annotations

LANGS = ("et", "en")
DEFAULT_LANG = "et"


def resolve_lang(session=None, request=None) -> str:
    """Pick the active language and remember it on the session."""
    chosen = None
    if request is not None:
        try:
            chosen = request.query_params.get("lang")
        except Exception:
            chosen = None
    if not chosen and session is not None:
        chosen = session.get("lang")
    lang = chosen if chosen in LANGS else DEFAULT_LANG
    if session is not None:
        try:
            session["lang"] = lang
        except Exception:
            pass
    return lang


def t(lang: str) -> dict:
    """Return the copy dictionary for the active language."""
    return COPY.get(lang, COPY[DEFAULT_LANG])


COPY = {
    "et": {
        "html_lang": "et",
        "meta_title": "FastHR · Eesti personalitöö ja palgaarvestus",
        "meta_desc": "Töötajad, puudumised, Eesti palgaarvestus (TÖR, TSD) ja "
                     "värbamine ühes avatud lähtekoodiga platvormis. Majuta ise "
                     "tasuta või 1 € kuus inimese kohta.",
        "nav": [("Võimalused", "/features"), ("Võrdlus", "/compare"),
                ("Hinnad", "/#pricing"),
                ("Arendajatele", "/developers")],
        "menu": "Menüü",
        "signin": "Logi sisse",
        "auth_close": "Sulge sisselogimine",
        "auth_signin": "Logi sisse",
        "auth_register": "Registreeru",
        "auth_login_title": "Logi oma {app_name} kontole sisse",
        "auth_register_title": "Loo oma {app_name} konto",
        "auth_forgot_title": "Lähtesta parool",
        "auth_google": "Jätka Google'iga",
        "auth_or": "või",
        "auth_email_label": "E-posti aadress",
        "auth_email_placeholder": "E-posti aadress",
        "auth_name_label": "Nimi",
        "auth_name_placeholder": "Sinu nimi",
        "auth_password_label": "Parool",
        "auth_password_placeholder": "Parool (vähemalt 10 märki)",
        "auth_forgot": "Unustasid parooli?",
        "auth_send_reset": "Saada lähtestamislink",
        "auth_back_signin": "Tagasi sisselogimise juurde",
        "auth_verify_note": "Saadame sulle kinnitamislingi. Enne konto kinnitamist sisse logida ei saa.",
        "auth_error_login": "E-post, parool või konto kinnitus ei sobi. Kontrolli andmeid või kinnita konto e-kirjas.",
        "auth_error_email_password": "Sisesta kehtiv e-posti aadress ja vähemalt 10 märgi pikkune parool.",
        "auth_error_rate_limit": "Proovisid liiga palju kordi. Oota veidi ja proovi uuesti.",
        "auth_error_mail": "Kinnituskirja ei saanud saata. Kontrolli aadressi ja proovi mõne hetke pärast uuesti.",
        "auth_success_verify": "Vaata oma e-posti ja kinnita konto enne sisselogimist.",
        "auth_success_registered": "Kui selle aadressiga saab konto luua, saadetakse sulle kinnituskiri.",
        "auth_success_signed_in": "Oled sisse logitud.",
        "auth_success_reset": "Kui selle aadressiga konto on olemas, saadetakse lähtestamislink.",
        "auth_error_request": "Päring ebaõnnestus. Kontrolli ühendust ja proovi uuesti.",
        "auth_success_done": "Tehtud.",
        "hero_eyebrow": "Eesti HR-platvorm",
        "hero_h1_a": "Personal, palk ja värbamine",
        "hero_h1_hi": "ühel avatud platvormil.",
        "hero_sub": "FastHR haldab töötajaid, puudumisi, Eesti palgaarvestust "
                    "(TÖR, TSD) ja värbamist. Majuta ise tasuta või lase meil "
                    "majutada. Hind on 1 € kuus inimese kohta.",
        "hero_cta1": "Alusta tasuta",
        "hero_cta2": "Vaata demot",
        "hero_trust": "Avatud lähtekoodiga · MIT litsents · Krediitkaarti pole vaja",
        "logos_label": "Osa avatud FastSME tooteperekonnast, kus arendatakse kuni 47 toodet.",
        "feat_eyebrow": "Kõik ühes",
        "feat_h2": "Kõik, mida personalitööks vaja.",
        "feat_sub": "Värbamisest palgapäevani. Üks töölaud kogu meeskonnale, "
                    "ilma litsentsitasudeta.",
        "features": [
            ("Töötajad ja struktuur", "Töötajate andmed, osakonnad, ametikohad ja "
             "aruandlusliinid ühes kataloogis."),
            ("Puudumised ja tööaeg", "Puhkusejäägid, taotlused, kinnitused ja "
             "igapäevane tööajaarvestus."),
            ("Eesti palgaarvestus", "Palgapäevad ja palgalehed on kasutatavad. TÖR-i ja TSD "
             "sügavamad ekspordid ning puhkuse- ja töövõimetustasu arvestus on teekaardil."),
            ("Värbamine ja ATS", "Kuulutused, kandidaadid, hindamislehed ja "
             "AI-põhine CV-tuvastus."),
            ("Arengu- ja tulemusjuhtimine", "Eesmärgid, tagasiside, hindamisringid "
             "ja selgitatavad signaalid."),
            ("Töötaja elukaar", "Sisseelamine, muudatused, lahkumine, juhtumid ja "
             "organisatsiooni kaart."),
        ],
        "demo_h2": "Vaata, kuidas see töötab",
        "demo_sub": "See on päris rakenduse salvestus, mitte disainiillustratsioon.",
        "demo_alt": "FastHR-i päris rakenduse salvestus: töölaud, töötajate andmed, puudumised ja personalitöö töövood.",
        "stat_eyebrow": "Ehitatud Eestile",
        "stat_h2": "Kohalik vastavus, mis on tavaliselt lisatasu.",
        "stat_sub": "FastHR-i palgapäevad ja palgalehed on kasutatavad. TÖR-i ja TSD "
                    "sügavamad ekspordid ning puhkuse- ja töövõimetustasu arvestus on teekaardil.",
        "statutory": [
            ("TÖR", "Töötamise register: töösuhete registreerimine ja muudatused."),
            ("TSD", "Sügavamad maksudeklaratsiooni ja väljamaksete ekspordid on teekaardil."),
            ("Smart-ID & Mobiil-ID", "Sisselogimine ja dokumentide allkirjastamine "
             "Eesti e-identiteediga."),
            ("Puhkuse- ja haigushüvitis", "Puhkuse- ja töövõimetustasu automaatne "
             "arvestus on teekaardil."),
            ("Summeeritud tööaeg", "Normtundide arvestus, üle- ja alatunnid "
             "tööseaduse järgi."),
            ("EMTA maksumäärad", "Aastapõhiselt uuenevad maksuvaba miinimum ja määrad."),
        ],
        "price_eyebrow": "Hinnad",
        "price_h2": "Lihtne hind kõigile FastSME toodetele.",
        "price_sub": "Kaks võimalust igal Fast*-tootel: majuta ise tasuta või lase "
                     "meil majutada.",
        "price_cards": [
            ("BYOC", "Majuta ise", "Tasuta", "Oma serveris või pilves. Täielik "
             "kontroll andmete ja uuenduste üle. Platvormitasu puudub."),
            ("Majutatud", "Meie majutame", "1 € kuus inimese kohta", "Me haldame üht "
             "toodet sinu eest FastSME taristus."),
        ],
        "price_example": "30 inimese tiim maksab 30 € kuus. Kõik funktsioonid kaasas.",
        "cmp_eyebrow": "Võrdlus",
        "cmp_h2": "Vaata, kuidas me võrdleme.",
        "cmp_sub": "Aus kõrvutus Eesti ja rahvusvaheliste HR-lahendustega. "
                   "koos allikatega.",
        "cmp_cta": "Vaata võrdlust →",
        "cmp_names": ["Persona", "Wemply", "HRM4Baltics", "BambooHR", "Gusto", "Deel"],
        "cmp2_eyebrow": "Võrdlus",
        "cmp2_h2": "FastHR vs Eesti HR-tarkvara",
        "cmp2_sub": "Avatud ja tasuta HR-tööriistad: palgapäevad, tööaeg, kulud, "
                    "lähetused ja töötaja iseteenindus.",
        "cmp2_labels": {
            "core": "Personal ja struktuur", "leave": "Puudumised",
            "time": "Tööaeg ja kohalolek", "shifts": "Töögraafikud",
            "epayroll": "Eesti palk (TÖR, TSD)", "expenses": "Kulud ja lähetused",
            "selfservice": "Iseteenindus", "ats": "Värbamine (ATS)",
            "perf": "Tulemusjuhtimine", "ai": "AI (CV, assistent)",
            "api": "Avalik API", "oss": "Avatud lähtekoodiga", "selfhost": "Ise majutamine",
        },
        "cmp2_table_label": "Võrdlus",
        "cmp2_price_label": "Hind kuus",
        "cmp2_prices": ["Tasuta · 1 € kuus inimese kohta", "", "", "", "", ""],
        "cmp2_legend": [("yes", "Olemas"), ("soon", "Tulekul"), ("no", "Puudub")],
        "cmp2_note": "FastHR-i hind on näidatud viimases reas. Andmed pärinevad avalikest allikatest (sept 2026).",
        "cmp2_cta": "Vaata täielikku võrdlust →",
        "cmp_toggle_heading": "Eesti ja globaalne HR-tarkvara võrdlus",
        "cmp_toggle_label": "Vali võrdlus",
        "cmp_toggle_estonia": "Eesti",
        "cmp_toggle_global": "Rahvusvaheline",
        "cmp_global_sub": "Samas võrdlusvormingus rahvusvaheliste HR-platvormidega.",
        "cmp_global_labels": {
            "core": "Personal ja struktuur", "leave": "Puudumised",
            "time": "Tööaeg ja kohalolek", "payroll": "Palk ja palgaarvestus",
            "expenses": "Kulud ja hüvitised", "selfservice": "Iseteenindus",
            "ats": "Värbamine (ATS)", "perf": "Tulemusjuhtimine",
            "ai": "AI HR-i jaoks", "api": "Avalik API",
            "oss": "Avatud lähtekoodiga", "selfhost": "Ise majutamine",
        },
        "cmp_global_table_label": "Globaalsete HR-platvormide võrdlus",
        "cmp_global_legend": [("yes", "Olemas"), ("soon", "Tulekul"), ("no", "Puudub")],
        "cmp_global_note": "Võrdlus põhineb avalikest allikatest kogutud teabel (sept 2026). FastHR-i hind on näidatud viimases reas.",
        "feat_pg_meta_title": "FastHR võimalused ja hind · Tasuta",
        "feat_pg_meta_desc": "Tutvu kõigi FastHR-i võimalustega. Kõik saadaolevad ja "
                             "planeeritud moodulid on tasuta.",
        "feat_pg_eyebrow": "Võimalused ja hind",
        "feat_pg_h1": "Kõik personalifunktsioonid. Tasuta.",
        "feat_pg_lede": "Kasuta täna valmis mooduleid ja vaata, mis tuleb järgmisena. "
                        "Tasulisi tasemeid ega moodulite lisatasu pole.",
        "feat_pg_chip_avail": "saadaolevat funktsiooni",
        "feat_pg_chip_soon": "tulekul",
        "feat_pg_chip_free_s": "Tasuta",
        "feat_pg_chip_free": "kogu kataloogis",
        "feat_pg_cat_h": "Funktsioonide kataloog",
        "feat_pg_cat_p": "Saadavus peegeldab praegust FastHR-i teostust. „Tulekul“ "
                         "moodulid on nähtaval, et meeskonnad saaksid planeerida.",
        "feat_pg_status_avail": "Saadaval",
        "feat_pg_status_soon": "Tulekul",
        "feat_pg_free": "Tasuta",
        "feat_pg_open": "Ava →",
        "feat_pg_note_s": "Hind: BYOC tasuta · majutus 1 € kuus inimese kohta. ",
        "feat_pg_note": "Majuta ise tasuta või lase meil majutada 1 € kuus inimese kohta. "
                        "„Tulekul“ tähistab valmimist, mitte tulevast tasulist paketti.",
        "feat_payroll_workflow_name": "Palgalehed ja palgapäevad",
        "feat_payroll_workflow_desc": "Palgapäevad ja töötajate palgalehed koos rea-põhise jaotusega.",
        "feat_payroll_statutory_name": "Eesti seadusjärgne palk (TÖR, TSD)",
        "feat_payroll_statutory_desc": "TÖR-i ja TSD sügavamad ekspordid ning puhkuse- ja töövõimetustasu arvestus on teekaardil.",
        "cmp_pg_meta_title": "FastHR vs avatud ja proprietaarne HR-tarkvara",
        "cmp_pg_meta_desc": "Võrdle FastHR-i Gusto, BambooHR, Rippling, Deel, Zoho People "
                            "ja Odoo HR-iga litsentsimudeli, palga ja ulatuse osas.",
        "cmp_pg_eyebrow": "Kuidas me võrdleme",
        "cmp_pg_h1": "Vaikimisi vaba ja avatud.",
        "cmp_pg_lede": "Võrdlus põhineb avalikest allikatest kogutud teabel (sept 2026). "
                       "Avatus, palgakate ja ulatus on eraldi näidatud.",
        "cmp_pg_chips": [("Tasuta", "FastHR-i võimalused"), ("MIT", "avatud litsents"),
                         ("Pole", "tasulisi tasemeid")],
        "cmp_pg_headers": ["Platvorm", "Sobib", "Ideaalne tiim", "Alghind", "Tasuta variant",
                           "Avatud lähtekood", "Palk / globaalne", "Piirangud"],
        "cmp_pg_caption": "Avalik litsentsi ülevaade septembris 2026. FastHR-i hind on näidatud viimases reas.",
        "cmp_pg_table_label": "HR-platvormide võrdlus",
        "cmp_pg_estonia_heading": "Eesti HR-tarkvara",
        "cmp_pg_global_heading": "Globaalsed platvormid",
        "cmp_pg_legend": [("yes", "Avatud lähtekoodiga"),
                          ("soon", "Osaliselt avatud lähtekoodiga"),
                          ("no", "Suletud lähtekoodiga")],
        "cmp_pg_note": "Võrdlus põhineb avalikest allikatest kogutud teabel (sept 2026). "
                       "„Tasuta“ kirjeldab tarkvara või nimetatud plaani, mitte vältimatut taristu- või juurutusarvet.",
        "cmp_pg_faq_h": "Küsimused, mida küsitakse",
        "faq_eyebrow": "Korduma kippuvad küsimused",
        "faq_h2": "Küsimused, enne kui alustad.",
        "faqs": [
            ("Kas FastHR on tasuta?", "Jah. Kõik saadaolevad FastHR-i funktsioonid on tasuta, "
             "ja ka tulekul olev ulatus on märgitud tasuta, mitte tasulise paketi osaks."),
            ("Kas FastHR on avatud lähtekoodiga?", "Jah. FastHR on avaldatud MIT litsentsi all, "
             "selle koodi saab uurida ja muuta, ning see on mõeldud ise majutamiseks."),
            ("Kas võrreldud HR-süsteemidest mõni on avatud lähtekoodiga?", "FastHR on MIT-litsentsiga "
             "avatud lähtekoodiga. Odoo Community on LGPLv3 avatud lähtekoodiga, Odoo Enterprise aga "
             "suletud. BambooHR on suletud lähtekoodiga; Gusto, Rippling, Deel ja Zoho People ei avalda "
             "avatud lähtekoodiga väljaannet."),
            ("Kas tasuta tarkvara tähendab, et kasutamine on kuluta?", "Ei. Tarkvara võib olla tasuta, "
             "ent majutamine, juurutamine, tugi, andmete üleviimine ja kolmandate pakkujate kasutamine "
             "võivad ikkagi kulusid tuua. Võrdlus eraldab tarkvara hinna nendest kasutusvalikutest."),
            ("Kas FastHR-i tulekul olevad funktsioonid on juba kasutatavad?", "Ei. „Tulekul“ on "
             "saadavuse märge, mitte hinnatase. Võimaluste leht eristab valmis funktsioone teekaardi "
             "ulatusest."),
        ],
        "cta_h2": "Alusta täna. Tasuta.",
        "cta_sub": "Loo konto ja proovi FastHR-i oma meeskonnaga. Krediitkaarti pole vaja.",
        "cta_btn": "Loo tasuta konto",
        "cta_btn2": "Vaata GitHubis ↗",
        "foot_tagline": "FastHR on osa avatud lähtekoodiga FastSME tootepere.",
        "foot_cols": [
            ("Toode", [("Võimalused", "/features"), ("Hinnad", "/#pricing"),
                       ("Võrdlus", "/compare"), ("Arendajatele", "/developers")]),
            ("Ettevõte", [("FastSME tootepere", "https://fastsme.com/products"),
                          ("GitHub", "https://github.com/predictivelabsai/FastHRM")]),
            ("Õiguslik", [("Privaatsus", "/privacy"), ("Litsents (MIT)", "https://github.com/predictivelabsai/FastHRM")]),
        ],
        "foot_rights": "FastSME · Avatud lähtekoodiga",
        "comparison_estonia": [
            {"name": "FastHR", "highlight": True},
            {"name": "Persona", "highlight": False},
            {"name": "Wemply", "highlight": False},
            {"name": "HRM4Baltics", "highlight": False},
            {"name": "hours24", "highlight": False},
            {"name": "Yester", "highlight": False},
        ],
        "comparisons": [
            {"name": "FastHR", "highlight": True},
            {"name": "Gusto", "highlight": False},
            {"name": "BambooHR", "highlight": False},
            {"name": "Rippling", "highlight": False},
            {"name": "Deel", "highlight": False},
            {"name": "Zoho People", "highlight": False},
            {"name": "Odoo HR", "highlight": False},
        ],
        "comparison_faqs": [
            ("Kas FastHR on tasuta?", "Jah. Kõik saadaolevad FastHR-i funktsioonid on tasuta. Ka tulekul olevad võimalused on märgitud tasuta, mitte tasulise paketi osaks."),
            ("Kas FastHR on avatud lähtekoodiga?", "Jah. FastHR on MIT-litsentsiga, selle koodi saab uurida ja muuta ning tarkvara saab ise majutada."),
            ("Millised võrreldud HR-süsteemid on avatud lähtekoodiga?", "FastHR on MIT-litsentsiga avatud lähtekoodiga. Odoo Community on LGPLv3-litsentsiga, Odoo Enterprise on suletud. BambooHR on suletud ning Gusto, Rippling, Deel ja Zoho People ei avalda avatud lähtekoodiga väljaannet."),
            ("Kas tasuta tarkvara tähendab, et käitamine ei maksa midagi?", "Ei. Majutus, juurutus, tugi, andmete üleviimine ja kolmandate teenuste kasutamine võivad ikka maksta. Võrdlus hoiab tarkvara hinna nendest kuludest eraldi."),
            ("Kas FastHR-i tulekul olevad funktsioonid on juba kasutatavad?", "Ei. „Tulekul“ on saadavuse märge, mitte hinnatase. Võimaluste leht eristab valmis funktsioone teekaardi ulatusest."),
        ],
        "dashboard_mock": {
            "groups": (("ÜLEVAADE", (("📊", "Töölaud"), ("🤖", "AI-abiline"))),
                        ("INIMESED", (("👥", "Töötajad"), ("🏢", "Osakonnad"))),
                        ("AEG", (("🌴", "Puhkus"), ("🕒", "Kohalolek"))),
                        ("PALK", (("💰", "Palk"),)),
                        ("TALENT", (("📋", "Värbamine"), ("🧲", "Kandidaadid"), ("📈", "Analüütika"))),
                        ("TULEMUS", (("🎯", "Eesmärgid"), ("💬", "Tagasiside"))),
                        ("ELUKAAR", (("🧭", "Sisseelamine"), ("🔀", "Muudatused")))),
            "bars": (("Müük", 10, 100), ("Tehnika", 9, 90), ("Turundus", 9, 90),
                     ("Rahandus", 9, 90), ("Inimesed ja kultuur", 7, 70), ("Toode", 7, 70)),
            "leave": (("Kadri Tamm", "Haigusleht", "22.–26. mai", "sick"),
                      ("Mari Oja", "Haigusleht", "3. juuni", "sick"),
                      ("Jaan Kask", "Puhkus", "11. juuni", "annual")),
            "dashboard": "HR-töölaud", "dashboard_sub": "Inimesed, aeg ja palk ühes vaates.",
            "headcount": "TÖÖTAJATE ARV", "departments": "8 osakonda", "present": "TÄNA KOHAL",
            "on_leave": "3 puhkusel", "attendance": "KOHALOLEK (30 PÄEVA)", "pending": "KINNITAMIST OOTAV PUHKUS",
            "awaiting": "ootab kinnitamist", "headcount_chart": "Töötajate arv osakonniti",
            "leave_requests": "Puhkusetaotlused", "ai": "AI-abiline",
            "ai_prompt": "Küsi töötajate arvu, puhkuste või kohaloleku kohta.",
            "chip_leave": "Kes on täna puhkusel?", "chip_team": "Milline tiim on suurim?",
            "ask": "Küsi midagi", "send": "Saada", "logout": "Logi välja",
        },
    },
    "en": {
        "html_lang": "en",
        "meta_title": "FastHR · Estonian HR & payroll, open source",
        "meta_desc": "Employee records, leave, Estonian statutory payroll (TÖR, TSD) "
                     "and recruiting in one open-source platform. Self-host free or "
                     "host with us for €1 per person per month.",
        "nav": [("Features", "/features"), ("Compare", "/compare"),
                ("Pricing", "/#pricing"),
                ("Developers", "/developers")],
        "menu": "Menu",
        "signin": "Sign in",
        "auth_close": "Close sign in",
        "auth_signin": "Sign in",
        "auth_register": "Register",
        "auth_login_title": "Sign in to your {app_name} account",
        "auth_register_title": "Create your {app_name} account",
        "auth_forgot_title": "Reset your password",
        "auth_google": "Continue with Google",
        "auth_or": "or",
        "auth_email_label": "Email address",
        "auth_email_placeholder": "Email address",
        "auth_name_label": "Name",
        "auth_name_placeholder": "Your name",
        "auth_password_label": "Password",
        "auth_password_placeholder": "Password (minimum 10 characters)",
        "auth_forgot": "Forgot password?",
        "auth_send_reset": "Send reset link",
        "auth_back_signin": "Back to sign in",
        "auth_verify_note": "We will email you a verification link. You cannot sign in until the account is verified.",
        "auth_error_login": "Invalid email, password, or unverified account. Check your details or verify the account from your email.",
        "auth_error_email_password": "Enter a valid email address and a password of at least 10 characters.",
        "auth_error_rate_limit": "There have been too many attempts. Wait a little and try again.",
        "auth_error_mail": "We could not send the verification email. Check the address and try again shortly.",
        "auth_success_verify": "Check your email and verify the account before signing in.",
        "auth_success_registered": "If an account can be registered with this address, a verification email is on its way.",
        "auth_success_signed_in": "You are signed in.",
        "auth_success_reset": "If an account exists for this address, a reset link is on its way.",
        "auth_error_request": "The request failed. Check your connection and try again.",
        "auth_success_done": "Done.",
        "hero_eyebrow": "Estonian HR platform",
        "hero_h1_a": "HR, payroll and hiring",
        "hero_h1_hi": "on one open platform.",
        "hero_sub": "FastHR runs employee records, leave, Estonian statutory payroll "
                    "(TÖR, TSD) and recruiting. Self-host it for free, or let us host "
                    "it. Hosting costs €1 per person per month.",
        "hero_cta1": "Start free",
        "hero_cta2": "See the demo",
        "hero_trust": "Open source · MIT licence · No credit card",
        "logos_label": "Part of the open FastSME product family, growing toward 47 tools.",
        "feat_eyebrow": "Everything in one place",
        "feat_h2": "Everything you need for people ops.",
        "feat_sub": "From recruiting to payday. One workspace for the whole team, "
                    "with no licence fees.",
        "features": [
            ("People & structure", "Employee records, departments, roles and "
             "reporting lines in one directory."),
            ("Leave & attendance", "Balances, requests, approvals and daily "
             "attendance tracking."),
            ("Estonian payroll", "Pay runs and payslips are available. Deeper TÖR and TSD "
             "exports, holiday pay and incapacity pay calculations remain on the roadmap."),
            ("Recruiting & ATS", "Openings, candidates, scorecards and AI CV "
             "extraction."),
            ("Performance", "Goals, feedback, review cycles and explainable people "
             "signals."),
            ("Employee lifecycle", "Onboarding, changes, exits, cases and an org "
             "chart."),
        ],
        "demo_h2": "See how it works",
        "demo_sub": "This is the real app, not a mockup.",
        "demo_alt": "Recording of the real FastHR app showing the dashboard, employee records, leave and people-operations workflows.",
        "stat_eyebrow": "Built for Estonia",
        "stat_h2": "Local compliance that's usually an upsell.",
        "stat_sub": "FastHR's pay runs and payslips are available today. Deeper TÖR and TSD "
                    "exports, holiday pay and incapacity pay calculations remain on the roadmap.",
        "statutory": [
            ("TÖR", "Employment register: register and amend employment records."),
            ("TSD", "Deeper tax-declaration and payment-file exports remain on the roadmap."),
            ("Smart-ID & Mobile-ID", "Sign in and sign documents with Estonian "
             "e-identity."),
            ("Holiday & sick pay", "Automatic holiday-pay and incapacity-pay "
             "calculation remains on the roadmap."),
            ("Summated working time", "Norm-hour accounting, over- and under-time "
             "per labour law."),
            ("EMTA tax rates", "Tax-free minimum and rates that update each year."),
        ],
        "price_eyebrow": "Pricing",
        "price_h2": "Simple pricing for every FastSME product.",
        "price_sub": "Two options on every Fast* product: bring your own cloud for "
                     "free, or let us host it.",
        "price_cards": [
            ("BYOC", "Bring your own cloud", "Free", "Self-host on your own "
             "infrastructure. Full control of data and upgrades. No platform fee."),
            ("Hosted", "Host with us", "€1 per person per month", "We run one product "
             "for you on FastSME infrastructure."),
        ],
        "price_example": "A 30-person team pays €30 a month, all features included.",
        "cmp_eyebrow": "Compare",
        "cmp_h2": "See how we compare.",
        "cmp_sub": "An honest comparison against Estonian and international "
                   "HR tools.",
        "cmp_cta": "See the comparison →",
        "cmp_names": ["Persona", "Wemply", "HRM4Baltics", "BambooHR", "Gusto", "Deel"],
        "cmp2_eyebrow": "Compare",
        "cmp2_h2": "FastHR vs Estonian HR software",
        "cmp2_sub": "Open and free HR tools for pay runs, time, expenses, travel "
                     "and employee self-service.",
        "cmp2_labels": {
            "core": "People & structure", "leave": "Leave & absence",
            "time": "Time & attendance", "shifts": "Shift scheduling",
            "epayroll": "Estonian payroll (TÖR, TSD)", "expenses": "Expenses & travel",
            "selfservice": "Employee self-service", "ats": "Recruiting (ATS)",
            "perf": "Performance", "ai": "AI (CV, assistant)",
            "api": "Public API", "oss": "Open source", "selfhost": "Self-hosting",
        },
        "cmp2_table_label": "Compare",
        "cmp2_price_label": "Price / month",
        "cmp2_prices": ["Free · €1 per person per month", "", "", "", "", ""],
        "cmp2_legend": [("yes", "Included"), ("soon", "Coming soon"), ("no", "Not available")],
        "cmp2_note": "FastHR pricing appears in the final row. Competitor data comes from public sources (Sep 2026).",
        "cmp2_cta": "See the full comparison →",
        "cmp_toggle_heading": "FastHR vs Estonian and global HR software",
        "cmp_toggle_label": "Choose comparison",
        "cmp_toggle_estonia": "Estonian",
        "cmp_toggle_global": "Global",
        "cmp_global_sub": "A straightforward capability comparison with international HR platforms.",
        "cmp_global_labels": {
            "core": "People and structure", "leave": "Leave", "time": "Time and attendance",
            "payroll": "Payroll", "expenses": "Expenses and reimbursements",
            "selfservice": "Employee self-service", "ats": "Recruiting (ATS)",
            "perf": "Performance management", "ai": "AI for HR", "api": "Public API",
            "oss": "Open source", "selfhost": "Self-hosting",
        },
        "cmp_global_table_label": "Global HR platform comparison",
        "cmp_global_legend": [("yes", "Included"), ("soon", "Coming soon"), ("no", "Not available")],
        "cmp_global_note": "Comparison is based on information gathered from public sources (Sep 2026). FastHR pricing appears in the final row.",
        "feat_pg_meta_title": "FastHR Features & Pricing · Free",
        "feat_pg_meta_desc": "Explore every FastHR feature. All available and planned "
                             "modules are Free.",
        "feat_pg_eyebrow": "Features & pricing",
        "feat_pg_h1": "Every people feature. Free.",
        "feat_pg_lede": "Use the modules that are ready today and see what is coming next. "
                        "There are no paid tiers or per-module upgrades.",
        "feat_pg_chip_avail": "available features",
        "feat_pg_chip_soon": "coming soon",
        "feat_pg_chip_free_s": "Free",
        "feat_pg_chip_free": "across the catalogue",
        "feat_pg_cat_h": "Feature catalogue",
        "feat_pg_cat_p": "Availability reflects the current FastHR implementation. "
                         "Coming-soon modules are visible so teams can plan without "
                         "mistaking roadmap scope for shipped software.",
        "feat_pg_status_avail": "Available",
        "feat_pg_status_soon": "Coming soon",
        "feat_pg_free": "Free",
        "feat_pg_open": "Open →",
        "feat_pg_note_s": "Pricing: BYOC Free · €1 per person per month. ",
        "feat_pg_note": "Self-host for free, or host with us for €1 per person per month. "
                        "“Coming soon” describes delivery status only, not a future paid plan.",
        "feat_payroll_workflow_name": "Payslips and pay runs",
        "feat_payroll_workflow_desc": "Pay runs and employee payslips with line-item breakdowns.",
        "feat_payroll_statutory_name": "Estonian statutory payroll (TÖR, TSD)",
        "feat_payroll_statutory_desc": "Deeper TÖR and TSD exports, holiday pay and incapacity pay calculations remain on the roadmap.",
        "cmp_pg_meta_title": "FastHR vs Open-Source and Proprietary HRM Software",
        "cmp_pg_meta_desc": "Compare FastHR with Gusto, BambooHR, Rippling, Deel, Zoho "
                            "People, and Odoo HR across licensing model, payroll, and scope.",
        "cmp_pg_eyebrow": "How we compare",
        "cmp_pg_h1": "Free and open by default.",
        "cmp_pg_lede": "A comparison based on information gathered from public sources (Sep 2026). "
                       "Source availability, payroll coverage and scope are shown separately.",
        "cmp_pg_chips": [("Free", "FastHR features"), ("MIT", "open-source licence"),
                         ("No", "paid tiers")],
        "cmp_pg_headers": ["Platform", "Best for", "Ideal team", "Starting price", "Free option",
                           "Open source", "Payroll / global", "Limitations"],
        "cmp_pg_caption": "Public licensing observed in Sep 2026. FastHR pricing appears in the final row.",
        "cmp_pg_table_label": "HR platform comparison",
        "cmp_pg_estonia_heading": "Estonian HR software",
        "cmp_pg_global_heading": "Global platforms",
        "cmp_pg_legend": [("yes", "Open source"),
                          ("soon", "Partly open source"),
                          ("no", "Closed source")],
        "cmp_pg_note": "Comparison is based on information gathered from public sources (Sep 2026). "
                       "“Free” describes the software or named plan, not unavoidable infrastructure or implementation costs.",
        "cmp_pg_faq_h": "Questions people ask",
        "faq_eyebrow": "Frequently asked",
        "faq_h2": "Questions before you start.",
        "faqs": [
            ("Is FastHR free?", "Yes. Every available FastHR feature is free, and coming-soon "
             "scope is also labelled free rather than reserved for a paid tier."),
            ("Is FastHR open source?", "Yes. FastHR is published under the MIT licence, can be "
             "inspected and modified, and is designed to be self-hosted."),
            ("Which compared HR systems are open source?", "FastHR is MIT-licensed open source. "
             "Odoo Community is LGPLv3 open source, while Odoo Enterprise is proprietary. BambooHR "
             "is proprietary; Gusto, Rippling, Deel and Zoho People do not publish open-source editions."),
            ("Does free software mean zero operating cost?", "No. Software can be free while hosting, "
             "implementation, support, migration and third-party provider usage still incur costs. The "
             "comparison separates software price from those operating choices."),
            ("Are coming-soon FastHR features available today?", "No. Coming soon is an availability "
             "label, not a pricing tier. The Features page distinguishes shipped functionality from "
             "roadmap scope."),
        ],
        "cta_h2": "Start today. For free.",
        "cta_sub": "Create an account and try FastHR with your team. No credit card "
                   "required.",
        "cta_btn": "Create a free account",
        "cta_btn2": "View on GitHub ↗",
        "foot_tagline": "FastHR is part of the open-source FastSME suite.",
        "foot_cols": [
            ("Product", [("Features", "/features"), ("Pricing", "/#pricing"),
                         ("Compare", "/compare"), ("Developers", "/developers")]),
            ("Company", [("FastSME suite", "https://fastsme.com/products"),
                         ("GitHub", "https://github.com/predictivelabsai/FastHRM")]),
            ("Legal", [("Privacy", "/privacy"), ("Licence (MIT)", "https://github.com/predictivelabsai/FastHRM")]),
        ],
        "foot_rights": "FastSME · Open source",
        "comparison_estonia": [
            {"name": "FastHR", "highlight": True},
            {"name": "Persona", "highlight": False},
            {"name": "Wemply", "highlight": False},
            {"name": "HRM4Baltics", "highlight": False},
            {"name": "hours24", "highlight": False},
            {"name": "Yester", "highlight": False},
        ],
        "comparisons": [
            {"name": "FastHR", "highlight": True},
            {"name": "Gusto", "highlight": False},
            {"name": "BambooHR", "highlight": False},
            {"name": "Rippling", "highlight": False},
            {"name": "Deel", "highlight": False},
            {"name": "Zoho People", "highlight": False},
            {"name": "Odoo HR", "highlight": False},
        ],
        "comparison_faqs": [
            ("Is FastHR free?", "Yes. Every available FastHR feature is free. Coming-soon scope is also labelled free, not reserved for a paid tier."),
            ("Is FastHR open source?", "Yes. FastHR is published under the MIT licence, can be inspected and modified, and is designed to be self-hosted."),
            ("Which compared HR systems are open source?", "FastHR is MIT-licensed open source. Odoo Community is LGPLv3 open source, while Odoo Enterprise is proprietary. BambooHR is proprietary; Gusto, Rippling, Deel and Zoho People do not publish open-source editions."),
            ("Does free software mean zero operating cost?", "No. Hosting, implementation, support, migration and third-party provider usage can still incur costs. The comparison separates software price from those operating choices."),
            ("Are coming-soon FastHR features available today?", "No. Coming soon is an availability label, not a pricing tier. The Features page distinguishes shipped functionality from roadmap scope."),
        ],
        "dashboard_mock": {
            "groups": (("OVERVIEW", (("📊", "Dashboard"), ("🤖", "AI Assistant"))),
                        ("PEOPLE", (("👥", "Employees"), ("🏢", "Departments"))),
                        ("TIME", (("🌴", "Leave"), ("🕒", "Attendance"))),
                        ("PAY", (("💰", "Payroll"),)),
                        ("TALENT", (("📋", "Recruiting platform"), ("🧲", "Candidates"), ("📈", "Analytics"))),
                        ("PERFORMANCE", (("🎯", "Goals & OKRs"), ("💬", "Feedback"))),
                        ("LIFECYCLE", (("🧭", "Onboarding"), ("🔀", "Changes")))),
            "bars": (("Sales", 10, 100), ("Engineering", 9, 90), ("Marketing", 9, 90),
                     ("Finance", 9, 90), ("People & Culture", 7, 70), ("Product", 7, 70)),
            "leave": (("Nina Novak", "Sick Leave", "22–26 May", "sick"),
                      ("Lena Fischer", "Sick Leave", "3 Jun", "sick"),
                      ("Priya Silva", "Annual Leave", "11 Jun", "annual")),
            "dashboard": "HR Dashboard", "dashboard_sub": "People, time and pay at a glance.",
            "headcount": "HEADCOUNT", "departments": "8 departments", "present": "PRESENT TODAY",
            "on_leave": "3 on leave", "attendance": "ATTENDANCE (30D)", "pending": "PENDING LEAVE",
            "awaiting": "awaiting approval", "headcount_chart": "Headcount by department",
            "leave_requests": "Pending leave requests", "ai": "AI Assistant",
            "ai_prompt": "Ask about headcount, leave or attendance.",
            "chip_leave": "Who's on leave today?", "chip_team": "Which team is biggest?",
            "ask": "Ask a question", "send": "Send", "logout": "Logout",
        },
    },
}
