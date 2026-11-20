"""The ``pyaddic7ed`` import alias must expose the exact same API as ``pyaddic7``."""

import pyaddic7
import pyaddic7ed


def test_alias_exposes_public_api():
    for name in pyaddic7.__all__:
        assert hasattr(pyaddic7ed, name), f"missing: {name}"
        assert getattr(pyaddic7ed, name) is getattr(pyaddic7, name), f"identity mismatch: {name}"


def test_alias_version_matches():
    assert pyaddic7ed.__version__ == pyaddic7.__version__
