import e2e_metrics as M


def sig(page, bbox, role="borrower"):
    return {"page": page, "bbox": bbox, "role": role}


def test_wilson_interval_and_empty():
    lo, hi = M.wilson(8, 10)
    assert 0.49 < lo < 0.5 and 0.94 < hi < 0.95
    assert M.wilson(0, 0) == (None, None)
    r = M.ratio(0, 0)
    assert r["value"] is None


def test_percentile_nearest_rank():
    assert M.percentile([10, 20, 30, 40], 50) == 20
    assert M.percentile([10, 20, 30, 40], 95) == 40
    assert M.percentile([], 50) is None


def test_field_found_ignores_diacritics_spaces_and_extra_part():
    t = M.norm_text("Smlouva č. 860001/26, částka 1 749 000,00 CZK, IČO 98000110")
    assert M.field_found("860001/26", t)
    assert M.field_found("1 749 000,00 CZK / 100 % ceny bez DPH", t)   # jen první část
    assert M.field_found("98000110 / CZ98000110", t)
    assert not M.field_found("12345678", t)


def test_calibration_gap_and_bins():
    items = [(0.95, True), (0.9, True), (0.6, False), (0.55, False), (0.8, True)]
    c = M.calibration(items)
    assert c["n_correct"] == 3 and c["n_wrong"] == 2
    assert abs(c["mean_confidence_correct"] - 0.8833333) < 1e-5
    assert abs(c["mean_confidence_wrong"] - 0.575) < 1e-9
    assert c["gap"] > 0.3
    assert sum(b["n"] for b in c["bins"]) == 5
    assert 0 <= c["ece"] <= 1 and 0 <= c["brier"] <= 1


def test_match_perfect_miss_and_spurious():
    truth = [sig(3, [0.1, 0.5, 0.3, 0.6]), sig(3, [0.5, 0.5, 0.7, 0.6])]
    found = [sig(3, [0.11, 0.51, 0.31, 0.61]), sig(1, [0.1, 0.1, 0.2, 0.15])]
    m = M.match_signatures(truth, found)
    assert len(m["pairs"]) == 1 and m["missed"] == [1]
    assert m["spurious"] == [1] and m["duplicate_or_merged"] == []


def test_match_requires_same_page():
    m = M.match_signatures([sig(2, [0.1, 0.1, 0.3, 0.2])], [sig(3, [0.1, 0.1, 0.3, 0.2])])
    assert m["pairs"] == [] and m["missed"] == [0] and m["spurious"] == [0]


def test_merged_box_over_two_signatures_is_covered_not_matched_twice():
    truth = [sig(1, [0.1, 0.5, 0.3, 0.6]), sig(1, [0.35, 0.5, 0.55, 0.6])]
    found = [sig(1, [0.1, 0.5, 0.55, 0.6])]      # jeden box přes oba
    m = M.match_signatures(truth, found)
    assert len(m["pairs"]) == 1 and len(m["missed"]) == 1
    assert len(m["covered"]) == 2                # mírné kritérium vidí oba
    assert m["spurious"] == []


def test_tight_box_inside_truth_region_matches_via_containment():
    truth = [sig(1, [0.1, 0.5, 0.4, 0.7])]
    found = [sig(1, [0.15, 0.55, 0.35, 0.6333])]   # IoU = 0.28, ale celý uvnitř
    assert M.iou(truth[0]["bbox"], found[0]["bbox"]) < 0.3
    assert len(M.match_signatures(truth, found)["pairs"]) == 1


def test_huge_box_does_not_match_small_truth():
    truth = [sig(1, [0.4, 0.5, 0.5, 0.55])]
    found = [sig(1, [0.0, 0.0, 1.0, 1.0])]
    m = M.match_signatures(truth, found)
    assert m["pairs"] == []


def test_duplicate_box_on_same_signature_is_not_false_finding():
    truth = [sig(1, [0.1, 0.5, 0.3, 0.6])]
    found = [sig(1, [0.1, 0.5, 0.3, 0.6]), sig(1, [0.12, 0.52, 0.28, 0.58])]
    m = M.match_signatures(truth, found)
    assert len(m["pairs"]) == 1 and m["duplicate_or_merged"] == [1] and m["spurious"] == []


def test_page_level_truth_without_bbox():
    truth = [{"page": 3, "role": "provider"}, {"page": 3, "role": "provider"}, {"page": 3, "role": "borrower"}]
    found = [sig(3, [0.1, 0.5, 0.2, 0.6]), sig(3, [0.3, 0.5, 0.4, 0.6]), sig(5, [0.1, 0.1, 0.2, 0.2])]
    m = M.match_signatures(truth, found)
    assert len(m["pairs"]) == 2 and len(m["missed"]) == 1 and m["spurious"] == [2]
    assert all(v is None for _, _, v in m["pairs"])


def test_found_without_bbox_matches_by_page():
    m = M.match_signatures([sig(2, [0.1, 0.1, 0.3, 0.2])], [{"page": 2, "bbox": None, "role": None}])
    assert len(m["pairs"]) == 1


def test_role_match_levels():
    assert M.role_match("borrower", "borrower") == "exact"
    assert M.role_match("borrower", "buyer") == "lenient"
    assert M.role_match("provider", "borrower") == "wrong"
    assert M.role_match("provider", "unknown") == "unknown"
    assert M.role_match("provider", None) == "unknown"


def test_apply_removed():
    items = [sig(1, [0, 0, .1, .1], "provider"), sig(1, [.2, 0, .3, .1], "borrower"), sig(2, [0, 0, .1, .1])]
    left, gone = M.apply_removed(items, [{"page": 1, "role": "borrower"}, {"page": 9}])
    assert [s["role"] for s in left] == ["provider", "borrower"] and len(gone) == 1
    assert gone[0]["role"] == "borrower"


def test_valid_bbox():
    assert M.valid_bbox([0, 0, .5, .5])
    assert not M.valid_bbox([0.5, 0, 0.2, 0.5])
    assert not M.valid_bbox([0, 0, 1.2, 1])
    assert not M.valid_bbox(None)
