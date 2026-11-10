"""The workflow diagram is built from the code: every module it names exists, and it loads nothing external."""
import re

import pytest

from conftest import DATA

ROOT = DATA.parent


def make_workflow():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_workflow", ROOT / "scripts" / "make_workflow.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_step_names_a_module_that_exists():
    mod = make_workflow()
    for _, module, _ in mod.STEPS:
        assert (ROOT / module).is_file(), module
    assert (ROOT / mod.SERV_MODULE).is_file()


@pytest.mark.parametrize("name", ["workflow.svg", "workflow_4x5.svg"])
def test_committed_svgs_match_the_generator_and_load_nothing_external(name):
    mod = make_workflow()
    text = (ROOT / "docs" / name).read_text(encoding="utf-8")
    assert text == (mod.wide() if name == "workflow.svg" else mod.tall()) + "\n"
    assert not re.search(r"(?:href|src)\s*=", text)
    for _, module, _ in mod.STEPS[1:]:
        assert module.rsplit("/", 1)[-1] in text
