from contract_audit.catalog import resolve_capability


def test_confirmed_mapping_is_supported(catalog):
    r = resolve_capability(catalog, "chest-xr", "nodule_like")
    assert r["capability"] == "supported"
    assert r["tool_id"] == "SYN-NODULE-1"


def test_tool_for_other_modality_only_is_unsupported_not_substituted(catalog):
    r = resolve_capability(catalog, "chest-xr", "fracture_like")
    assert r["capability"] == "unsupported"
    assert r["tool_id"] is None  # no invented substitute


def test_source_that_omits_modality_is_uncertain(catalog):
    r = resolve_capability(catalog, "chest-xr", "cardiac_size")
    assert r["capability"] == "uncertain"
    assert "modality_term_not_in_quote" in r["reasons"]


def test_unknown_finding_class_is_unsupported(catalog):
    assert resolve_capability(catalog, "chest-xr", "no_such_class")["capability"] == "unsupported"


def test_quote_not_verbatim_in_source_is_uncertain(catalog, clone):
    cat = clone(catalog)
    next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")["quote"] = "flag nodule-like findings on chest-xr scans"
    r = resolve_capability(cat, "chest-xr", "nodule_like")
    assert r["capability"] == "uncertain"
    assert "quote_not_in_source" in r["reasons"]


def test_source_text_changed_after_hashing_is_uncertain(catalog, clone):
    cat = clone(catalog)
    cat["sources"]["SRC-SYN-A"]["text"] += " Edited later."
    r = resolve_capability(cat, "chest-xr", "nodule_like")
    assert r["capability"] == "uncertain"
    assert "source_hash_mismatch" in r["reasons"]


def test_missing_source_is_uncertain(catalog, clone):
    cat = clone(catalog)
    del cat["sources"]["SRC-SYN-A"]
    r = resolve_capability(cat, "chest-xr", "nodule_like")
    assert r["capability"] == "uncertain"
    assert "source_missing" in r["reasons"]


def test_finding_term_missing_from_quote_is_uncertain(catalog, clone):
    cat = clone(catalog)
    next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")["finding_term"] = "mass-like"
    r = resolve_capability(cat, "chest-xr", "nodule_like")
    assert r["capability"] == "uncertain"
    assert "finding_term_not_in_quote" in r["reasons"]


def test_removing_the_only_confirmed_entry_never_yields_supported(catalog, clone):
    cat = clone(catalog)
    cat["tools"] = [t for t in cat["tools"] if t["tool_id"] != "SYN-NODULE-1"]
    r = resolve_capability(cat, "chest-xr", "nodule_like")
    assert r["capability"] == "unsupported"
    assert r["tool_id"] is None
