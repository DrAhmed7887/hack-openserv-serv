import copy
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def catalog():
    return json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))


@pytest.fixture
def case():
    def _load(case_id):
        return json.loads((DATA / "cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def expected():
    def _load(case_id):
        return json.loads((DATA / "expected" / f"{case_id}.json").read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def clone():
    return copy.deepcopy
