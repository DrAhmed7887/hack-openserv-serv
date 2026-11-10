"""build_audit is fail-closed on the synthetic flag itself, not only through the file loaders."""
import pytest

from contract_audit.audit import build_audit
from contract_audit.inputs import InputError, validate_case, validate_catalog

MISSING = object()
NOT_TRUE = [False, MISSING, None, 0, 1, "true", "yes", [], {}, [True]]


def with_flag(obj, clone, value):
    out = clone(obj)
    if value is MISSING:
        out.pop("synthetic", None)
    else:
        out["synthetic"] = value
    return out


@pytest.mark.parametrize("value", NOT_TRUE, ids=repr)
def test_direct_build_audit_refuses_a_case_not_marked_synthetic_true(catalog, case, clone, value):
    c = with_flag(case("c01_supported_called"), clone, value)
    with pytest.raises(InputError, match="synthetic"):
        build_audit(catalog, c)


@pytest.mark.parametrize("value", NOT_TRUE, ids=repr)
def test_direct_build_audit_refuses_a_catalog_not_marked_synthetic_true(catalog, case, clone, value):
    cat = with_flag(catalog, clone, value)
    with pytest.raises(InputError, match="synthetic"):
        build_audit(cat, case("c01_supported_called"))


def test_validators_refuse_the_flag_on_their_own(catalog, case, clone):
    with pytest.raises(InputError, match="synthetic"):
        validate_case(with_flag(case("c01_supported_called"), clone, False))
    with pytest.raises(InputError, match="synthetic"):
        validate_catalog(with_flag(catalog, clone, MISSING))


def test_a_synthetic_case_still_audits_and_is_labelled_synthetic(catalog, case):
    a = build_audit(catalog, case("c01_supported_called"))
    assert a["synthetic"] is True and a["completeness"] == "full_support"
