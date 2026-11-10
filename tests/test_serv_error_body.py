"""An HTTP error whose body cannot be read is still a SERV failure (exit 5), never a crash.

Found 10 Nov 2026 as an intermittent failure of test_urllib_post_does_not_follow_redirects_or_forward_the_key:
reading the redirect's body raised ConnectionResetError, which escaped urllib_post. Reproduced here without a
socket, so it fails or passes the same way every run.
"""
import urllib.error

import pytest

from contract_audit import serv
from contract_audit.serv import ServCallFailed

KEY = "test-not-a-real-key-123"
HEADERS = {"Authorization": "Bearer " + KEY}


class _UnreadableBody:
    def read(self, *args):
        raise ConnectionResetError(54, "Connection reset by peer")

    def close(self):
        pass


@pytest.mark.parametrize("code", [302, 500])
def test_http_error_with_an_unreadable_body_is_a_serv_failure(monkeypatch, code):
    def fake_open(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "error", {}, _UnreadableBody())
    monkeypatch.setattr(serv._OPENER, "open", fake_open)
    with pytest.raises(ServCallFailed) as exc:
        serv.urllib_post("https://serv.invalid/v1/chat/completions", HEADERS, {}, 5)
    assert exc.value.status == code and KEY not in str(exc.value)
