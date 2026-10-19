"""Markdown report evaluace. Bez síťových volání; jen formátuje slovník z `evaluate()`."""

GROUP_TITLES = {"generic": "generic (20 syntetických případů, generické podpisy)",
                "original": "original (solom-rec, stavby-fiser, lidské rukopisné podpisy)",
                "other": "other (bez skupiny)"}


def num(x, d=1):
    if x is None:
        return "–"
    return f"{x:.{d}f}".replace(".", ",")


def pct(r, ci=True):
    """Podíl z M.ratio() jako „87,5 % (7/8; 95% CI 47–99 %)“."""
    if r is None or r["n"] == 0:
        return "– (0/0)"
    s = f"{num(100 * r['value'])} % ({r['k']}/{r['n']}"
    lo, hi = r["ci95"]
    if ci and lo is not None:
        s += f"; CI {num(100 * lo, 0)}–{num(100 * hi, 0)} %"
    return s + ")"


def ms(x):
    return "–" if x is None else f"{x:,.0f}".replace(",", " ")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def small_n(n):
    return " ⚠ malý vzorek, interval je široký" if 0 < n < 30 else ""


def render_markdown(res, truth):
    meta, pg = res["meta"], res["per_group"]
    L = []
    w = L.append
    w("# Evaluace end-to-end: zpracování dokumentů a čtecí API validačního agenta\n")
    src = meta["source"]
    if src.get("simulated"):
        w("> **FIXTURE, NE MĚŘENÍ.** Odpovědi vygeneroval `fixture_api.py` z pravdy se záměrně vloženými chybami. "
          "Čísla ukazují jen tvar reportu a schopnost metrik chyby zachytit, ne kvalitu systému.\n")
    w(f"- Čas: {meta['generated_at']}; zdroj: `{src['mode']}`" + (f" ({src['host']})" if src.get("host") else ""))
    w(f"- Mapping: {meta['mapping']['cases']} případů, {meta['mapping']['documents']} dokumentů "
      f"({'`' + meta['mapping']['path'] + '`' if meta['mapping']['path'] else 'vestavěný z fixtury / zdroje'})")
    w(f"- Pravda: `{meta['truth']['path']}` (balík `{(meta['truth'].get('zip_sha256') or '?')[:12]}…`)")
    w(f"- Volby: sousedé N={meta['options']['neighbors']}, opakování={meta['options']['retries']}, "
      f"časový limit={meta['options']['timeout']} s, souběžnost={meta['options']['workers']}\n")

    groups = [g for g in ("generic", "original") if g in pg] + [g for g in pg if g not in ("generic", "original")]

    # souhrn
    w("## Souhrn\n")
    rows = []
    for g in groups:
        p = pg[g]
        s = p["signatures"]
        rows.append([g, p["cases"], p["documents"], pct(p["availability"]["available"], False),
                     pct(p["labels"]["accuracy"], False), pct(p["vectors"]["vectors_exist"], False),
                     pct(s["completeness_at_place"], False) if s["documents_with_known_truth"] else "pravda neznámá",
                     pct(s["false_findings_share_of_found"], False) if s["documents_with_known_truth"] else "pravda neznámá"])
    w(table(["skupina", "případů", "dokumentů", "volání 1 dostupné", "přesnost štítku", "vektory existují",
             "podpisy: úplnost", "podpisy: falešné nálezy (podíl nálezů)"], rows))
    lat = res["latency"]
    tot_n = sum(x["n"] for x in lat.values())
    tot_err = sum(x["server_errors"] + x["client_errors"] for x in lat.values())
    w(f"\nVolání celkem {tot_n}, chyby (5xx, síť, 4xx mimo 409) {tot_err}; p95 latence: " + ", ".join(
        f"{n} {ms(lat[k]['p95_ms'])} ms" for k, n in (("detail", "volání 1"), ("vectors", "volání 2"),
                                                     ("signatures", "volání 3")) if k in lat) + ".")
    w("\nPodpisy se vyhodnocují zvlášť pro každou skupinu a nikdy se neslučují do jednoho čísla "
      "(generické vektorové podpisy a lidský rukopis se detekují různě).\n")

    # 1
    w("## 1. Volání 1: dokument je dostupný a má text\n")
    for g in groups:
        a = pg[g]["availability"]
        w(f"### {GROUP_TITLES.get(g, g)}\n")
        w(f"- Dostupné (`completed`/`partial` a neprázdný text): {pct(a['available'])}{small_n(a['documents'])}")
        w(f"- Stavy: {', '.join(f'{k} {v}' for k, v in sorted(a['status'].items()))}; z toho `partial`: {a['partial']}")
        w(f"- `page_count` odpovídá pravdě: {pct(a['page_count_matches_truth'])}")
        w(f"- Počet stran v textu (dělení `\\f`) = `page_count`: {pct(a['text_pages_match_page_count'])}")
        w(f"- Anotované hodnoty polí nalezené v textu (podmínka pro validaci, ne měření extrakce): {pct(a['field_recall'])}")
        if a["field_recall_by_text_layer"]:
            w("  - podle vrstvy textu: " + "; ".join(f"{k}: {pct(v, False)}" for k, v in a["field_recall_by_text_layer"].items()))
        if a["by_quality"] and len(a["by_quality"]) > 1:
            w("- Dostupnost podle kvality vstupu: " + "; ".join(f"{k}: {pct(v, False)}" for k, v in a["by_quality"].items()))
        if a["shape_errors"]:
            w(f"- **Porušení tvaru odpovědi:** {a['shape_errors']}")
        w("")

    # 2
    w("## 2. Štítek a kalibrace `confidence`\n")
    for g in groups:
        lb = pg[g]["labels"]
        w(f"### {GROUP_TITLES.get(g, g)}\n")
        if not lb["eligible"]:
            w("Žádný dokument s pravdou o štítku a dostupným detailem.\n")
            continue
        w(f"- Přesnost štítku (štítek ∈ přijatelné štítky pravdy): {pct(lb['accuracy'])}{small_n(lb['eligible'])}; "
          f"chybný {lb['wrong']}, bez štítku {lb['missing_label']}")
        w("- Podle jistoty pravdy: " + "; ".join(f"{k}: {pct(v, False)}" for k, v in lb["by_certainty"].items())
          + " (`probable` = typ je v taxonomii jen popisem, viz truth.yaml)")
        if len(lb["by_quality"]) > 1:
            w("- Podle kvality vstupu: " + "; ".join(f"{k}: {pct(v, False)}" for k, v in lb["by_quality"].items()))
        w(f"- `label_status`: {lb['label_status']}; `confidence = null`: {lb['confidence_null']}")
        if lb["top_confusions"]:
            w("- Nejčastější záměny (pravda → predikce): " + "; ".join(
                f"{c['truth']} → {c['predicted']} ×{c['n']}" for c in lb["top_confusions"][:6]))
        cal = lb["calibration"]
        if cal:
            w(f"- Kalibrace (jen `predicted`, kde je `confidence`; n={cal['n']}): průměrná jistota u správných "
              f"**{num(cal['mean_confidence_correct'], 3)}** ({cal['n_correct']}), u špatných "
              f"**{num(cal['mean_confidence_wrong'], 3)}** ({cal['n_wrong']}); rozdíl {num(cal['gap'], 3)}; "
              f"ECE {num(cal['ece'], 3)}, Brier {num(cal['brier'], 3)}")
            w("\n" + table(["jistota", "n", "skutečná přesnost", "průměrná jistota"],
                           [[f"{num(b['range'][0], 1)}–{num(b['range'][1], 1)}", b["n"],
                             num(b["accuracy"], 2), num(b["mean_confidence"], 2)] for b in cal["bins"]]))
            if cal["n_wrong"] == 0:
                w("\nŽádný špatný štítek: rozdíl jistoty mezi správnými a špatnými nelze spočítat.")
        if lb["unmapped_documents"]:
            w(f"\n- Dokumenty typů, které taxonomie nezná ({lb['unmapped_documents']}), se z přesnosti vylučují. "
              f"Predikované štítky: {lb['unmapped_predicted']}")
        w("")

    # 3
    w("## 3. Volání 2: vektory\n")
    for g in groups:
        v = pg[g]["vectors"]
        w(f"### {GROUP_TITLES.get(g, g)}\n")
        w(f"- Vektory existují (text nebo obraz): {pct(v['vectors_exist'])}{small_n(v['documents_called'])}")
        w(f"- Obrazové vektory = přesně strany 1…`page_count`: {pct(v['image_pages_equal_page_count'])}")
        w(f"- Textové vektory: části existují, rozsahy stran jsou platné a pokrývají všechny strany s textem: "
          f"{pct(v['text_vectors_ok'])}")
        w(f"- Rozměr 1024: {pct(v['dimension_1024'])}; modely: {v['models'] or '–'}")
        nb = v["neighbors"]
        w(f"- `neighbors` (N={meta['options']['neighbors']}): vyžádáno u {nb['requested']}, neprázdné u "
          f"{nb['returned_nonempty']}, prázdné u {nb['empty']}; porušení pravidel: "
          f"{nb['violations'] or 'žádné'}; sousedé, jejichž `verified` nelze ověřit v testované sadě: "
          f"{nb['unverifiable_neighbors']}")
        w(f"  - štítek nejbližšího souseda = pravda: {pct(nb['top1_label_correct'])}; většina sousedů = pravda: "
          f"{pct(nb['majority_label_correct'])}")
        vs = v["values_sample"]
        w(f"- Ukázka hodnot vektorů ({vs['checked']} dokumentů): " + ("bez nálezu" if not vs["problems"] else str(vs["problems"])))
        if v["shape_errors"]:
            w(f"- **Porušení tvaru odpovědi:** {v['shape_errors']}")
        w("")

    # 4
    w("## 4. Volání 3: podpisy (skupiny odděleně)\n")
    for g in groups:
        s = pg[g]["signatures"]
        w(f"### {GROUP_TITLES.get(g, g)}\n")
        w(f"- Dokumentů s odpovědí: {s['documents_ok']}; s pravdou o podpisech: {s['documents_with_known_truth']} "
          f"({s['truth_kinds'] or '–'}); bez pravdy: {s['documents_with_unknown_truth']}")
        if s["documents_with_known_truth"]:
            w(f"- **Úplnost** (očekávaný podpis nalezen na správné straně, IoU ≥ 0,3): {pct(s['completeness_at_place'])}"
              f"{small_n(s['expected'])}")
            if any(k.endswith("page") for k in s["truth_kinds"]):
                w("  - pravda je na úrovni strany (počet podpisů na straně), proto se porovnává jen strana a počet, "
                  "ne poloha; nález navíc na straně s plným počtem je falešný nález")
            w(f"  - mírněji (≥ 50 % plochy podpisu uvnitř nalezeného boxu): {pct(s['completeness_covered'])}")
            w(f"- **Falešné nálezy** (box bez očekávaného podpisu): {s['false_findings']} z {s['found_in_known_docs']} "
              f"nálezů, {pct(s['false_findings_share_of_found'])}; navíc duplicity / sloučené boxy: {s['duplicate_or_merged']}")
            dz, dp = s["docs_without_signatures_in_truth"], s["docs_with_signatures_in_truth"]
            w(f"- Dokumenty bez podpisu v pravdě: {dz['n']}, z toho s nálezem: {dz['with_false_findings']}. "
              f"Dokumenty s podpisy: {dp['n']}, z toho s chybějícím: {dp['with_missing']}, "
              f"se správným počtem: {dp['exact_count']}")
            r = s["roles"]
            w(f"- Role u spárovaných podpisů ({r['matched_pairs']}): přesná shoda {pct(r['accuracy_exact'], False)}, "
              f"s tolerancí kupující ≈ dlužník {pct(r['accuracy_lenient'], False)}, `unknown` {r['unknown']}, chybná {r['wrong']}")
            if s["by_kind"]:
                w("\n" + table(["typ dokumentu", "očekáváno", "nalezeno na místě", "falešné"],
                               [[k, v["expected"], v["matched"], v["false_findings"]] for k, v in s["by_kind"].items()]))
            if len(s["by_quality"]) > 1:
                w("\nÚplnost podle kvality vstupu: " + "; ".join(f"{k}: {pct(v, False)}" for k, v in s["by_quality"].items()))
        if s["documents_with_unknown_truth"]:
            fk = s["found_without_truth"]
            w(f"- Bez pravdy: v {fk['documents']} dokumentech nalezeno {fk['signatures']} podpisů "
              f"(po dokumentech {fk['per_document']}). **Úplnost ani falešné nálezy se tu nepočítají.**")
        w(f"- Detektory: {s['detectors'] or '–'}; `crop_url` {pct(s['has_crop_url'], False)}; `phash` "
          f"{pct(s['has_phash'], False)}; platný `bbox` {pct(s['bbox_valid'], False)}; role `unknown`/`null` "
          f"{pct(s['role_unknown_share'], False)}")
        if s["copy_suspicion_by_signer"]:
            w("- `copy_suspicion` podle toho, zda tentýž signatář podepsal další dokument případu "
              f"(informativní, balík nemá vložené podvody): {s['copy_suspicion_by_signer']}")
        elif s["copy_suspected_total"]:
            w(f"- `copy_suspicion = suspected` u {s['copy_suspected_total']} nálezů; bez pravdy, jen ke kontrole člověkem.")
        if s["shape_errors"]:
            w(f"- **Porušení tvaru odpovědi:** {s['shape_errors']}")
        if s["missed_total"]:
            w(f"- Chybějící podpisy ({s['missed_total']}), prvních 10: " + "; ".join(
                f"{m['case']}/{m['file']} s.{m['page']} {m.get('role') or ''}" for m in s["missed_examples"][:10]))
        if s["spurious_total"]:
            w(f"- Falešné nálezy ({s['spurious_total']}), prvních 10: " + "; ".join(
                f"{m['case']}/{m['file']} s.{m['page']}" for m in s["spurious_examples"][:10]))
        w("")

    # 5
    w("## 5. Latence a chybovost\n")
    names = {"list": "seznam případu", "detail": "volání 1 dokument", "vectors": "volání 2 vektory",
             "signatures": "volání 3 podpisy"}
    rows = []
    for k in ("list", "detail", "vectors", "signatures"):
        x = res["latency"].get(k)
        if x:
            rows.append([names[k], x["n"], ms(x["p50_ms"]), ms(x["p95_ms"]), ms(x["max_ms"]),
                         x["server_errors"], x["client_errors"], x["not_ready_409"], pct(x["error_rate"], False),
                         x["retried"]])
    w(table(["volání", "n", "p50 ms", "p95 ms", "max ms", "5xx/síť", "4xx", "409", "chybovost", "opakováno"], rows))
    w("\nChybovost = 5xx, chyby sítě a časové limity plus 4xx mimo 409 (id z mappingu mají existovat). "
      "409 je očekávané „zpracování neskončilo“ a do chybovosti se nepočítá. První volání po prodlevě "
      "(studený start Lambdy) se v p50 neprojeví, vidět je v max.")
    if any(x["simulated"] for x in res["latency"].values()):
        w("\n**Latence jsou simulované, nejde o měření.**")
    if meta["options"]["workers"] > 1:
        w(f"\nSouběžnost {meta['options']['workers']}: latence zahrnují čekání na souběžná volání.")
    w("")

    # 6
    w("## 6. Scénáře\n")
    rows = []
    for s in res["scenarios"]:
        rows.append([s["case_id"][:36], s["truth_case"] or "–", s["scenario"] or "–", s["verdict"],
                     s.get("expected_findings", "–"), s["findings_total"], s["findings_by_type"] or "–"])
    w(table(["případ", "pravda", "scénář", "verdikt", "očekávaných nálezů", "nálezů", "druhy nálezů"], rows))
    w("\nPravda pro 20 syntetických případů: všechny jsou `happy_path` bez nálezů (balík je záměrně bez vložených "
      "chyb). Nález typu `podpis_chybi` / `podpis_navic` / `dokument_nedostupny` v happy path je chyba zpracování, "
      "ne obchodní nález.\n")

    # 7
    w("## 7. Co nelze změřit\n")
    for line in unmeasurable(res, truth):
        w(f"- {line}")
    w("")

    # 8
    w("## 8. Příloha: chybně označené dokumenty\n")
    bad = [d for d in res["documents"] if d.get("label_outcome") in ("wrong", "missing")]
    if not bad:
        w("Žádné.\n")
    else:
        w(table(["případ", "soubor", "pravda", "predikce", "jistota", "stav štítku"],
                [[d["case_id"][:20], d.get("filename"), d["label_truth"], d.get("label"), num(d.get("confidence"), 2),
                  d.get("label_status")] for d in bad[:40]]))
        if len(bad) > 40:
            w(f"\n… a dalších {len(bad) - 40} (viz JSON).")
    return "\n".join(L) + "\n"


def unmeasurable(res, truth):
    pg = res["per_group"]
    out = []
    un = res["unresolved"]
    if un["cases"]:
        out.append(f"Případy bez přiřazené pravdy ({len(un['cases'])}): " + ", ".join(c["case_id"][:36] for c in un["cases"][:8])
                   + ". Do mappingu patří `source_case` (např. `SYN-A01`), `sha256` dokumentů, nebo musí soubory jednoznačně určit případ.")
    if un["documents"]:
        out.append(f"Dokumenty bez přiřazené pravdy ({len(un['documents'])}) se z metrik štítků a podpisů vylučují.")
    if res["list_mismatch"]:
        out.append(f"Seznam dokumentů v API se liší od mappingu u {len(res['list_mismatch'])} případů (viz JSON).")
    s_or = pg.get("original", {}).get("signatures")
    if s_or is not None and s_or["documents_with_unknown_truth"]:
        out.append(f"**Podpisy skupiny original:** pravda o podpisech chybí u {s_or['documents_with_unknown_truth']} dokumentů "
                   f"(`originals_review.yaml` je neobsahuje). Úplnost a falešné nálezy se tam nepočítají, vidět je jen počet nálezů.")
    if s_or is not None and s_or["documents_with_known_truth"]:
        kinds = s_or["truth_kinds"]
        out.append(f"Pravda podpisů skupiny original ({kinds}) je ruční vizuální kontrola jednoho posuzovatele bez druhé "
                   "kontroly; zdroj `S_REVIEW`. Je to doložená, ne autoritativní pravda.")
    lab = [g for g in pg if pg[g]["labels"]["unmapped_documents"]]
    for g in lab:
        out.append(f"Štítek u typů bez položky v taxonomii (skupina {g}: {pg[g]['labels']['unmapped_documents']} dokumentů, "
                   "potvrzení o čerpání úvěru, splátkový kalendář): pravdu nelze určit, dokud taxonomie typ nezná.")
    out.append("Typy s jistotou pravdy `probable` (předávací protokol z balíku, cenová nabídka, dodací list) mají štítek odvozený z popisu "
               "taxonomie, ne z jejího přímého názvu; přesnost se u nich uvádí zvlášť.")
    out.append("Skutečné zpracování skenů v původních případech: pravda o textu (přepis) neexistuje, měří se jen neprázdnost a "
               "přítomnost anotovaných hodnot (jen skupina generic).")
    out.append("`copy_suspicion`: balík neobsahuje vložené kopie podpisů ani podvody, takže pravdivě pozitivní nálezy neexistují. "
               "Tentýž signatář má v dokumentech případu shodný základ tahů (`same_signer_in_other_docs`), tabulka v sekci 4 "
               "je proto jen informativní a nehodnotí správnost.")
    out.append("`similar_signatures`, shoda s podpisy klienta (`match_client`) a pravost podpisu: bez pravdy a bez záruky API, neměří se.")
    out.append("Scénáře 3 (špatný dokument) a 4 (špatné údaje) vyžadují porovnání napříč dokumenty, což dělá validační agent; "
               "tři čtecí volání je nemohou „najít“. Nelze je tu změřit.")
    out.append("Scénáře 2, 5, 6 se měří jen s upravenými variantami dokumentů a s `removed_documents` / `variant.removed_signatures` "
               "v mappingu; bez nich je očekávání nelze určit (verdikt `nelze_určit_očekávání`).")
    out.append("Správnost `description` (popis z obsahu), obrazových a podpisových vektorů jako modelu (kvalita hledání) a "
               "pravdivost `neighbors` pro neověřené dokumenty mimo testovanou sadu: bez pravdy.")
    out.append("Kvalita vyhledávání podobných dokumentů se měří jen nepřímo (štítek nejbližšího souseda = pravda), a to pouze "
               "tam, kde index obsahuje ověřené dokumenty.")
    out.append("Latence jde z jednoho klienta, bez zátěže a bez řízeného studeného startu; p95 z malého počtu volání je jen orientační.")
    return out
