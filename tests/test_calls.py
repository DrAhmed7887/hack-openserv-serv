from contract_audit.calls import validate_calls


def statuses(result):
    return {c["call_id"]: c["status"] for c in result}


def reasons(result, call_id):
    return next(c for c in result if c["call_id"] == call_id)["reasons"]


def test_call_to_confirmed_tool_for_matching_obligation_is_valid(catalog, case):
    c = case("c01_supported_called")
    assert statuses(validate_calls(catalog, c["study"], c["proposed_calls"])) == {"CALL-1": "valid"}


def test_call_to_tool_of_other_modality_is_invalid(catalog, case):
    c = case("c03_unsupported")
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert statuses(result) == {"CALL-1": "invalid"}
    assert "modality_mismatch" in reasons(result, "CALL-1")


def test_call_to_tool_with_unconfirmed_mapping_is_unconfirmed(catalog, case):
    c = case("c04_uncertain_source_insufficient")
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert statuses(result) == {"CALL-1": "unconfirmed"}
    assert "modality_term_not_in_quote" in reasons(result, "CALL-1")


def test_unknown_tool_is_invalid(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["tool_id"] = "SYN-NOPE-9"
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert statuses(result) == {"CALL-1": "invalid"}
    assert "unknown_tool" in reasons(result, "CALL-1")


def test_unknown_obligation_is_invalid(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["obligation_id"] = "OB-99"
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert "unknown_obligation" in reasons(result, "CALL-1")
    assert statuses(result) == {"CALL-1": "invalid"}


def test_missing_required_arg_is_invalid(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["args"] = {}
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert statuses(result) == {"CALL-1": "invalid"}
    assert "missing_arg:study_id" in reasons(result, "CALL-1")


def test_tool_for_a_different_finding_class_is_invalid(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["tool_id"] = "SYN-EFFUSION-1"
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert statuses(result) == {"CALL-1": "invalid"}
    assert "finding_class_mismatch" in reasons(result, "CALL-1")


def test_duplicate_call_ids_are_all_invalid(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"].append(dict(c["proposed_calls"][0]))
    result = validate_calls(catalog, c["study"], c["proposed_calls"])
    assert [x["status"] for x in result] == ["invalid", "invalid"]
    assert "duplicate_call_id" in reasons(result, "CALL-1")
