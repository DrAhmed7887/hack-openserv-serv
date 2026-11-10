import importlib.util
import json
import re

from conftest import DATA

ROOT = DATA.parent
HTML = ROOT / "mock" / "index.html"


def builder():
    spec = importlib.util.spec_from_file_location("build_mock", ROOT / "scripts" / "build_mock.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def embedded():
    m = re.search(r'<script type="application/json" id="mock-data">(.*?)</script>', HTML.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1))


def test_embedded_data_is_exactly_what_the_offline_modules_produce():
    assert embedded() == builder().payload()


def test_mock_is_marked_not_connected_and_names_all_five_screens():
    text = HTML.read_text(encoding="utf-8")
    assert "DESIGN MOCK — NOT CONNECTED" in text
    for step in ("catalog", "study", "coverage", "repair", "export"):
        assert f'id="step-{step}"' in text


def test_mock_makes_no_network_requests_and_loads_nothing_external():
    text = HTML.read_text(encoding="utf-8")
    assert not re.search(r"https?://", text)
    for api in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "<img", "<link", "src="):
        assert api not in text


def test_mock_never_shows_a_serv_result_or_trace():
    text = HTML.read_text(encoding="utf-8")
    assert "SERV result" not in text and "step_trace" not in text
    assert "SERV response" not in text.replace("No SERV response", "")


def test_payload_is_labelled_fixture_and_synthetic():
    p = builder().payload()
    assert p["audit"]["synthetic"] is True and p["audit"]["serv"]["executed"] is False
    assert p["audit"]["case_id"] == "c07_combined"
