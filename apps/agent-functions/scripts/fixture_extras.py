"""Hand-written additions to the fixtures that the PDFs can't provide.

OCR: replacement text for scanned pages, typed in from the page images, as a
stand-in for the documents API's OCR. Keyed by (fixture, filename), then by
1-based page. A page left out keeps its pypdf text; an empty string is a blank
page. CONFIDENCE overrides the computed confidence of a document whose pages
were typed in.

SIGNATURES: what the documents API signatures endpoint would detect, per
document, as (page, role, role_evidence). Roles: provider (SGEF), borrower
(příjemce financování), supplier (dodavatel/prodávající), guarantor (ručitel),
insurer (pojistitel). The builder expands them into the upstream format.
"""

SOLOM_ORDER_P1 = """R000096446_Z25_00024
Objednávka
Číslo objednávky: 124 207
Zpracoval: Jiří Labuda  Tel.: 737 238 432  Email: jiri.labuda@smolo.cz
SOLOM Rec s.r.o.
Nám. Svobody 527
739 61 Třinec
IČO: 04606812  DIČ: CZ04606812
Zapsána v obchodním rejstříku vedeném Krajským soudem v Ostravě, spisová značka C oddíl 64377
Bankovní spojení objednatele: Komerční Banka a.s. 115-2001130287/0100
Dodavatel:
EPORIC Czech republic s.r.o.
Antala Staška 510/38
140 00 Praha 4 - Krč
IČO: 06493394  DIČ: CZ06493394
Kontaktní osoba: Kateřina Imlaufová  Tel.: 724 812 757  Email: katerina.imlaufova@epiroc.com
Termín dodání: 12/2024  Způsob platby: Převodem
Splatnost faktury od doručení: 30 dní
Adresa místa plnění: Provozovna Ropice
Fakturu zašlete: SOLOM Rec s.r.o. Nám. Svobody 527, 739 61 Třinec
Zakázka číslo:
Objednáváme u Vás dodání nových demoličních nůžek Epiroc CC 3100 vč.adaptační desky SW 66
Cena: 1.620.000,- Kč bez DPH
Cena zahrnuje: Hydraulické bourací nůžky s řízenou rotací, demoliční čelisti, maznici pro mazání čepů, 10ks náplní do maznice, sadu hadic a koncovek pro stroj a přechodovou desku.
Dodací lhůta: 12 týdnů od obdržení objednávky
Objednal: Jiří Labuda
Vystavil: Ing.Jarmila Kotrbatá
Ceny jsou bez DPH.
Potvrzenou objednávku zašlete zpět.
V textu faktury uvádějte číslo zakázky.
Podkladem pro fakturaci bude potvrzený soupis provedených prací, výkon stroje, dodací list, apod.
Schválil: V Ostravě 30.09.2024
SMOLO Recycling s.r.o., nám. Svobody 527, 739 61 Třinec-Lyžbice, IČ: 04606884
Objednatel: (razítko a podpis)
V                dne:
Dodavatel (jméno a příjmení, razítko, podpis)"""

# The unhappy re-export: a bug graphic covers the middle of the page and the
# client block is moved over the bank-account field.
UNHAPPY_ORDER_P1 = """R000096446_Z25_00024
Objednávka
Číslo objednávky: 124 207
Zpracoval: Jiří Labuda  Tel.: 737 238 432  Email: jiri.labuda@smolo.cz
IČO:  DIČ:
SOLOM Rec s.r.o.
Nám. Svobody 527
739 61 Třinec
Dodavatel:
EPORIC Czech republic s.r.o.
Antala Staška 510/38
140 00 Praha 4 - Krč
IČO: 06493394  DIČ: CZ06493394
Kontaktní osoba: Kateřina Imlaufová  Tel.: 724 812 757  Email: katerina.imlaufova@epiroc.com
Komerční Banka a.s.
115-20004606812/0100  CZ04606812
Termín dodání: 12/2024  Způsob platby: Převodem
Splatnost faktury od doručení: 30 dní
Adresa místa plnění: Provozovna Ropice
Fakturu zašlete:
Zakázka číslo:
Objednáváme u Vás dod[nečitelné] demoličních nůž[nečitelné]00 vč.adaptační d[nečitelné] SW 66
Cena: 1.620.000[nečitelné] bez DPH
Cena zahrnuje: Hydra[nečitelné]ké bou[nečitelné] čeli[nečitelné]aznici pro mazání čepů, 10ks náplní do maznic[nečitelné]
Dodací lhůta: 12 týdnů od obdržení objednávky
[nečitelné] Jiří Labuda
[nečitelné] Ing.Jarmila Kotrbatá
Ceny jsou bez DPH.
Potvrzenou objednávku zašl[nečitelné]
V textu faktury uvádějte čísl[nečitelné]
Podkladem pro fakturaci bude potvrzený soupis provedených prací, výkon stroje, dodací list, apod.
Schválil: V Ostravě 30.09.2024
SMOLO Recycling s.r.o., nám. Svobody 527, 739 61 Třinec-Lyžbice, IČ: 04606884
Objednatel: (razítko a podpis)
V                dne:
Dodavatel (jméno a příjmení, razítko, podpis)
739 61 Třinec"""

ORDER_P2 = """R000096446_Z25_00024
Ostatní ujednání
SMOLO Recycling s.r.o.
• Dodavatel se zavazuje a souhlasí, že v případě požadavku Objednatele bude tato objednávka nahrazena smlouvou, která objednávku nahradí v plném rozsahu. Jakékoliv změny, doplnění anebo jiné úpravy Objednávky ze strany dodavatele se považují za změnu podmínek a do doby písemného odsouhlasení tento protinávrh nevyvolává žádné právní účinky. Vylučuje se aplikace § 1740 odst. 3 občanského zákoníku.
• Dodavatel se zavazuje dodržovat povinnosti vyplývající ze zákona 435/2004 Sb. V platném znění.
• Objednatel je oprávněn a Dodavatel výslovně souhlasí, omezit plnění objednávky.
• Dodavatel se zavazuje plnit termíny vyplývající z této objednávky. Není-li dohodnuto jinak, je dohodnutá doba záruky 24. měsíců
• Není-li dohodnuto jinak, je doba splatnosti faktur 60 dní od data doručení faktury. K faktuře musí být vždy přiložena kopie objednávky, ke které se faktura vztahuje a další dokumenty prokazující dodání zboží a služeb, např. výkaz jízd, soupis prací, dodací list apod.
• Vrací-li objednatel dodavateli fakturu, je povinen vyznačit v dané faktuře důvod vrácení.
• V případě, že dodavatel nedodrží termín dodání zboží, zaplatí objednateli smluvní pokutu ve výši 0,5 % z celkové ceny zboží za každý započatý den prodlení, nejméně ve výši 10.000,- Kč za každý započatý den prodlení.
• Je vyloučená aplikace následujících ustanovení občanského zákoníku na smlouvu: § 557, § 1766, § 1793, § 1794, § 1795, § 1799 a § 1800, § 1805 odst. 2."""

HANDOVER_P1 = """R000096447_Z25_00024
Předávací certifikát
(ručně) CC 3100  DGR 240020
pro hydraulické demoliční nástroje
PDT - Power Demolition Tools
SDT - Silent Demolition Tools
Epiroc
© 2018 Construction Tools GmbH | No. 3390502712 | 2018-09-20"""

# The unhappy p. 1 is cropped at the bottom.
UNHAPPY_HANDOVER_P1 = """R000096447_Z25_00024
Předávací certifikát
(ručně) CC 3100  DGR 240020
pro hydraulické demoliční nástroje
PDT - Power Demolition Tools
SDT - Silent Demolition Tools"""

HANDOVER_P2 = """R000096447_Z25_00024
Zákaznickému centru Epiroc! Prodejcům! Zákazníkům/uživatelům!
Předávací certifikát je důležitý dokument pro následné zpracování reklamací ze záruky.
Záruční doba začíná datem předání. Je v zájmu hlavně kupujícího/uživatele, aby originální předávací certifikát vlastnil výrobce, Construction Tools GmbH, protože bez tohoto certifikátu nelze zpracovat reklamace ze záruky.
Je nutné, abyste zhotovili tři kopie podepsaného formuláře. Jednu kopii si ponechává kupující/uživatel. Druhá kopie je pro distributora, třetí pro zákaznické centrum Epiroc a originál pro společnost Construction Tools GmbH.
Zašlete jej na tuto adresu: Construction Tools GmbH, Abteilung Parts & Service/Technical Department, Helenenstraße 149, 45143 Essen"""

HANDOVER_P3 = """R000096447_Z25_00024
Construction Tools GmbH
Předávací certifikát SDT
1. Informace o kupujícím/uživateli, rypadle a instalaci
Zákaznické centrum Epiroc: (ručně) NOKA
Kupující/uživatel: (ručně) SMOLO REC
Adresa: (ručně) NÁM. SVOBODY 527
Město: (ručně) TŘINEC
Výrobce rypadla: (ručně) CAT
Typ rypadla: (ručně) 336
Výrobní č. rypadla: (ručně) 100006
Časoměr na nosiči: (ručně) 4002 MH
Model zařízení: (ručně) CC 3100
Výrobní č.: (ručně) DGR 240020
Datum předání: (ručně) 17.12.2024
Původní instalace: [x]
2. Měření průtoku a tlaku oleje v přídavném okruhu pro vybavení Epiroc
Tlak (bar): ca. 0 / 140 / 160 / 170 / 180 / 190 / 200 / 250 / 280 / 300 / 320 / 340 / 350
Průtok (l/min): 330 / 320 / 318 / 318 / 318 / 318 / 315 / 315 / 310 / 310 / 300 / 270 / 0
Konečný statický tlak – Otevírání: 360 bar; Zavírání: 360 bar; otáčet po směru: 170 bar; otáčet proti směru: 170 bar
3. Kontroly provedené na zařízení Epiroc: Zařízení bylo promazáno: [x] ano
4. Návod k obsluze: Pracovník obsluhy byl instruován: [x] ano; Bylo vysvětleno správné zacházení: [x] ano; Bylo poskytnuto poučení, jak předcházet škodám: [x] ano
5. Poznámky/předání:
Jméno zástupce servisu: (ručně) VITÁSEK
Jméno kupujícího/uživatele: (ručně) JOPÁL
Zákaznické centrum Epiroc: (ručně) NOKA
Datum a podpis: (ručně) 17.12.2024
Datum a podpis: (razítko) SMOLO Recycling s.r.o., nám. Svobody 527, 739 61 Třinec - Lyžbice, Mechanizace, IČ: 04606884"""

HANDOVER_P4 = """R000096447_Z25_00024
NOKA AT s.r.o. DISTRIBUTOR A PŮJČOVNA HYDRAULICKÉHO DEMOLIČNÍHO NÁŘADÍ, Roztoky 72, 270 23 Křivoklát, IČO: 28360907
PRACOVNÍ LIST  SERVIS STROJŮ HYDRAULICKÉHO DEMOLIČNÍHO PŘÍSLUŠENSTVÍ
Zákazník (název zakázky): (ručně) SMOLO
Typ stroje a výrobní číslo: (ručně) CC 3100  DGR 240020
Jméno servisního technika: (ručně) 17.12.2024
[x] Uvedení do provozu  [ ] Oprava  [ ] Záruční oprava  [ ] Kontrolní prohlídka
Popis práce / stav stroje: (ručně) SESTAVENÍ KLEŠTÍ, PODPORA UPÍNACÍ DESKY - HADIC, ODZKOUŠENÍ, PROMĚŘENÍ TLAKŮ VŠE OK
Náhradní díly: (ručně) SADA VAZNÍKŮ 1x; HADICE 1x; KATALOG ND 1x; NÁVOD K OBSLUZE 1x
Počet odpracovaných hodin celkem: (ručně) 4
Cesta: (ručně) TŘINEC - ROPICE - TŘINEC  Počet kilometrů: (ručně) 30
Potvrzujeme, že uvedené informace jsou pravdivé: 1 kopie - zákazník, 2 kopie - dodavatel (servis)
Podpis technika: (ručně) VITÁSEK
Podpis zákazníka: (razítko) SMOLO Recycling s.r.o., nám. Svobody 527, 739 61 Třinec - Lyžbice, Mechanizace"""

# Stavby Fišer: pages 4-9 of the order PDF are the supplier's scanned offer
# with the technical specification.
STAVBY_TS = {
    4: """R000145661_Z25_06017
Nabídka živičných vibračních válců BOMAG
pro společnost FIRESTA – Fišer, rekonstrukce, stavby a.s.
V Brně dne 3. března 2025
AWP s.r.o., výhradní zastoupení společnosti BOMAG, GmbH v ČR pro segment velké mechanizace, Okružní 635, 252 42 Osnice – Jesenice u Prahy""",
    5: """R000145661_Z25_06017
Vážený pane Fremle, ve smyslu Vaší poptávky si Vám dovoluji předložit nabídku na vibrační válce BOMAG za níže uvedených podmínek.
Servis: Veškerý případný servis v České republice je naší firmou zajišťován ze středisek Praha - Osnice a Brno - Modřice.
Dodávka a platební podmínky: termíny dodání do cca 3 - 4 měsíců. Platební podmínky – na základě vystavené faktury dle dohody.
Záruka: záruční doba v délce 24 měsíců nebo 2000 motohodin, dle toho, co nastane dříve.
Technická dokumentace smykového vibračního válce BOMAG BW 154 AP – 5 AM (Asphaltmanager na předním a vibrace na zadním běhounu, možný podrcovač)
provozní hmotnost kg 7950; maximální hmotnost kg 10900; zatížení předního běhounu kg 4100; zatížení zadního běhounu kg 3850; šířka běhounu mm 1500; statické lineární zatížení kg/cm 27,3 / 25,7; provozní rychlost km/h 0 – 11; motor Kubota V 3307 - T; emisní norma EURO V; chlazení vodou""",
    6: """R000145661_Z25_06017
počet válců 4; výkon kW 75,4; elektrická výbava V 12; běhouny ocelové/dělené; pohon hydrostatický; provozní brzda hydrostatická; parkovací brzda hydromechanická; budící síla kN (AM) 121; frekvence Hz 45; amplituda mm 0 - 0,82; budící síla kN (zadní běhoun) 89/48; frekvence Hz 44/45; amplituda mm 0,73/0,41; objem palivové nádrže 180; objem vodní nádrže 550
Standardní výbava vibračního válce BOMAG BW 154 AP – 5 AM: hydrostatický pohon pojezdu a vibrací, řízení smykem, oba dva dělené běhouny, celouzavřená kabina s vytápěním, elektronický kontrolní modul, systém Asphaltmanager, LCD display, akustická signalizace při couvání, výstražný maják, pracovní osvětlení, CE, návod k obsluze v ČJ""",
    7: """R000145661_Z25_06017
katalog náhradních dílů
Systém Asphaltmanager - unikátní patentovaný automatický systém nastavující hutnící účinek dle okamžitého stavu zhutnění zpracovávaného materiálu
Nadstandardní výbava zahrnutá v ceně nabídky: 2x přítlačné a ořezávací kolečko PP+LP, Klimatizace, Rádio, vnější zpětná zrcátka, osvětlení běhounů, ECOSTOP, alarm zpětného chodu „White Sound“, příprava pro podrcovací zařízení.
Cena stroje dle výše uvedené specifikace: Bomag BW 154 AP – 5 AM 3.894.600,- Kč
Technická dokumentace smykového vibračního válce BOMAG BW 154 APO – 5 (Standardní vibrace na předním a oscilace na zadním běhounu, možný podrcovač)
provozní hmotnost kg 7950; maximální hmotnost kg 10500; zatížení předního běhounu kg 3850; zatížení zadního běhounu kg 4100; šířka běhounu mm 1500; motor Kubota V 3307 - T; emisní norma EURO V; počet válců 4; výkon kW 55,4""",
    8: """R000145661_Z25_06017
běhouny ocelové/dělené; pohon hydrostatický; budící síla kN 89/48; frekvence Hz 44/45; amplituda mm 0,73/0,41; frekvence Hz (zadní běhoun - oscilace) 45; amplituda mm 0,82; objem palivové nádrže 180; objem vodní nádrže 550
Standardní výbava vibračního válce BOMAG BW 154 APO – 5: hydrostatický pohon pojezdu a vibrací, řízení smykem, oba dva dělené běhouny, celouzavřená kabina s vytápěním, oscilace na zadním běhounu, LCD display, CE, návod k obsluze v ČJ, katalog náhradních dílů""",
    9: """R000145661_Z25_06017
Systém Oscilace - díky možnosti horizontální vibrace v zadním běhounu válce umožňuje provádět hutnící práce na mostech nebo v zastavěných oblastech
Nadstandardní výbava zahrnutá v ceně nabídky: 2x přítlačné a ořezávací kolečko PP+LP, Klimatizace, Rádio, vnější zpětná zrcátka, osvětlení běhounů, ECOSTOP, alarm zpětného chodu „White Sound“, příprava pro podrcovací zařízení.
Cena stroje dle výše uvedené specifikace: Bomag BW 154 APO – 5 3.698.800,- Kč
Příplatková výbava, která není zahrnuta ve výše uvedených cenách: Kompletní precizní podrcovač BOMAG: 1 ks 275.000,- Kč; Příprava na systém BOMAP: 1 ks 125.000,- Kč
Všechny výše uvedené ceny jsou bez příslušné DPH, včetně dopravy na místo určení, předvedení a zaškolení obsluhy stroje.
S pozdravem
(razítko) AWP s.r.o., Okružní 635, Osnice - Jesenice u Prahy
Mgr. Martin Adam, vedoucí provozovny Brno""",
}

OCR = {
    ("solom-rec", "10_Podklady_k_vylate_objednavka.pdf"): {1: SOLOM_ORDER_P1, 2: ORDER_P2},
    ("solom-rec", "11_Podklady_k_vyplate_Protokol.pdf"): {1: HANDOVER_P1, 2: HANDOVER_P2, 3: HANDOVER_P3, 4: HANDOVER_P4},
    ("unhappy", "10_Podklady_k_vylate_objednavka.pdf"): {1: UNHAPPY_ORDER_P1, 2: ORDER_P2},
    # Pages 3-4 (the filled-in certificate and the work list) are blank in the unhappy bundle.
    ("unhappy", "11_Podklady_k_vyplate_Protokol.pdf"): {1: UNHAPPY_HANDOVER_P1, 2: HANDOVER_P2, 3: "", 4: ""},
    ("stavby-fiser", "10_Podklady_k_vyplate_Objednavka_TS.pdf"): STAVBY_TS,
}

CONFIDENCE = {
    ("solom-rec", "10_Podklady_k_vylate_objednavka.pdf"): 0.92,
    ("solom-rec", "11_Podklady_k_vyplate_Protokol.pdf"): 0.85,
    # The bug graphic makes the middle of the order unreadable.
    ("unhappy", "10_Podklady_k_vylate_objednavka.pdf"): 0.55,
    # Blank pages are read with confidence; they are blank, not unreadable.
    ("unhappy", "11_Podklady_k_vyplate_Protokol.pdf"): 0.9,
    ("unhappy", "09_Form_Dohoda_o_zaplaceni_kupni_ceny.pdf"): 0.95,
    ("stavby-fiser", "10_Podklady_k_vyplate_Objednavka_TS.pdf"): 0.9,
}

SGEF = "Poskytovatel financování: SG Equipment Finance Czech Republic s.r.o."
SOLOM = "Příjemce financování: SOLOM Rec s.r.o."
FISER = "Příjemce financování: Stavby Fišer a.s."

SOLOM_SIGNATURES = {
    "0_Form_Smlouva.pdf": [(3, "provider", f"{SGEF} / Jan Kovák, zmocněnec"), (3, "provider", f"{SGEF} / Josef Jonák, zmocněnec"), (3, "borrower", f"{SOLOM} / Petr Fiala")],
    "09_Form_Dohoda_o_zaplaceni_kupni_ceny.pdf": [
        (3, "provider", "SGEF: SG Equipment Finance Czech Republic s.r.o. / Jan Kovák, zmocněnec"),
        (3, "provider", "SGEF: SG Equipment Finance Czech Republic s.r.o. / Josef Jonák, zmocněnec"),
        (3, "supplier", "Prodávající: Epiroc Czech Republic s.r.o. / Jan Jikra"),
        (3, "borrower", "Kupující: SOLOM Rec s.r.o. / Petr Fiala"),
    ],
    "10_Podklady_k_vylate_objednavka.pdf": [
        (1, "borrower", "Objednal: Jiří Labuda"),
        (1, "borrower", "Vystavil: Ing.Jarmila Kotrbatá"),
        (1, "borrower", "Schválil / Objednatel (razítko a podpis): SMOLO Recycling s.r.o."),
    ],
    "11_Podklady_k_vyplate_Protokol.pdf": [
        (3, "supplier", "Zákaznické centrum Epiroc: NOKA / zástupce servisu Vitásek, Datum a podpis 17.12.2024"),
        (3, "borrower", "Jméno kupujícího/uživatele: Jopál / razítko SMOLO Recycling s.r.o."),
        (4, "supplier", "Podpis technika: Vitásek (NOKA AT s.r.o.)"),
        (4, "borrower", "Podpis zákazníka: razítko SMOLO Recycling s.r.o."),
    ],
    "2_Form_Zajistovaci_prevod_vl._prava.pdf": [(6, "provider", f"{SGEF} / Jan Kovák, zmocněnec"), (6, "provider", f"{SGEF} / Josef Jonák, zmocněnec"), (6, "borrower", f"{SOLOM} / Petr Fiala")],
    "3_Form_Vinkulace_poj.pdf": [(1, "insurer", "Podpis a razítko pojistitele / Evžen Fíla, poradce"), (1, "borrower", "Podpis a razítko příjemce financování (Pojistníka)")],
    "4_Form_Ruceni.pdf": [(2, "guarantor", "Ručitel: SOLOM a.s. / Herbert Jitka, Vedoucí"), (2, "provider", "SG Equipment Finance Czech Republic s.r.o. / Jan Kovák, zmocněnec"), (2, "provider", "SG Equipment Finance Czech Republic s.r.o. / Josef Jonák, zmocněnec")],
}

SIGNATURES = {
    **{("solom-rec", name): signatures for name, signatures in SOLOM_SIGNATURES.items()},
    # The re-exported unhappy PDFs have different page breaks.
    ("unhappy", "0_Form_Smlouva.pdf"): [(5, "provider", f"{SGEF} / Jan Kovák, zmocněnec"), (5, "provider", f"{SGEF} / Josef Jonák, zmocněnec"), (5, "borrower", f"{SOLOM} / Petr Fiala")],
    ("unhappy", "09_Form_Dohoda_o_zaplaceni_kupni_ceny.pdf"): [],
    ("unhappy", "10_Podklady_k_vylate_objednavka.pdf"): [
        (1, "borrower", "Jiří Labuda (popisek částečně zakryt)"),
        (1, "borrower", "Ing.Jarmila Kotrbatá (popisek částečně zakryt)"),
        (1, "borrower", "Schválil / Objednatel (razítko a podpis): SMOLO Recycling s.r.o."),
    ],
    ("unhappy", "11_Podklady_k_vyplate_Protokol.pdf"): [],
    ("unhappy", "2_Form_Zajistovaci_prevod_vl._prava.pdf"): [(10, "provider", f"{SGEF} / Jan Kovák, zmocněnec"), (10, "provider", f"{SGEF} / Josef Jonák, zmocněnec"), (10, "borrower", f"{SOLOM} / Petr Fiala")],
    ("unhappy", "3_Form_Vinkulace_poj.pdf"): [(1, "insurer", "Podpis a razítko pojistitele / Evžen Fíla, poradce"), (2, "borrower", "Podpis a razítko příjemce financování (Pojistníka)")],
    # The second SGEF signatory (Josef Jonák) is missing.
    ("unhappy", "4_Form_Ruceni.pdf"): [(3, "guarantor", "Ručitel: SOLOM a.s. / Herbert Jitka, Vedoucí"), (3, "provider", "SG Equipment Finance Czech Republic s.r.o. / Jan Kovák, zmocněnec")],
    ("stavby-fiser", "0_F_Smlouva.pdf"): [(3, "provider", f"{SGEF} / Petr Kůt, zmocněnec"), (3, "provider", f"{SGEF} / Karel Jíra, zmocněnec"), (3, "borrower", f"{FISER} / George Fišer, Jednatel")],
    # The order's signature boxes (p. 3) are empty; the signature is on the supplier's offer.
    ("stavby-fiser", "10_Podklady_k_vyplate_Objednavka_TS.pdf"): [(9, "supplier", "AWP s.r.o. / Mgr. Martin Adam, vedoucí provozovny Brno")],
    ("stavby-fiser", "11_Protokol_Potvrzeni_o_prechodu_vlastnictvi.pdf"): [(1, "supplier", "Dodavatel: PWA s.r.o. / George Fišer, jednatel")],
    ("stavby-fiser", "14_Podklady_k_vyplate_Uhrada_KC.pdf"): [],
    ("stavby-fiser", "2_Form_Zajistovaci_prevod_vl._prava.pdf"): [(6, "provider", f"{SGEF} / Petr Kůt, zmocněnec"), (6, "provider", f"{SGEF} / Karel Jíra, zmocněnec"), (6, "borrower", "Příjemce financování: FIRESTA-Fišer, rekonstrukce, stavby a.s. / George Fišer, jednatel")],
    ("stavby-fiser", "3_Form_Vinkulace_poj.pdf"): [(1, "insurer", "Podpis a razítko pojistitele / Jirsa, poradce"), (1, "borrower", "Podpis a razítko příjemce financování (Pojistníka)")],
}
