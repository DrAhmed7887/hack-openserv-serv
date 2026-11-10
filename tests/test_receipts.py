from contract_audit.receipts import check_receipt


def run(case):
    return check_receipt(case["proposed_calls"][0], case["receipts"])


def test_matching_ok_mock_receipt_is_valid(case):
    r = run(case("c01_supported_called"))
    assert r["status"] == "valid"
    assert r["receipt_id"] == "RCPT-1"


def test_no_receipt_is_missing(case):
    r = run(case("c05_missing_receipt"))
    assert r["status"] == "missing"
    assert r["receipt_id"] is None


def test_error_receipt_is_failed(case):
    assert run(case("c06_execution_failure"))["status"] == "failed"


def test_tampered_output_is_invalid(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["output"]["region_id"] = "R-999"
    r = run(c)
    assert r["status"] == "invalid"
    assert "output_digest_mismatch" in r["reasons"]


def test_receipt_for_another_tool_is_invalid(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["tool_id"] = "SYN-EFFUSION-1"
    r = run(c)
    assert r["status"] == "invalid"
    assert "tool_mismatch" in r["reasons"]


def test_unrecognised_executor_is_invalid(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["executor"] = "somebody-else"
    r = run(c)
    assert r["status"] == "invalid"
    assert "unrecognised_executor" in r["reasons"]


def test_unknown_status_is_invalid(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["status"] = "partial"
    assert run(c)["status"] == "invalid"


def test_two_receipts_for_one_call_are_invalid(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"].append(dict(c["receipts"][0], receipt_id="RCPT-X"))
    r = run(c)
    assert r["status"] == "invalid"
    assert "multiple_receipts" in r["reasons"]


def test_receipt_for_other_call_does_not_count(case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["call_id"] = "CALL-77"
    assert run(c)["status"] == "missing"
