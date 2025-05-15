"""Global test fixtures for environments without pytest-mock installed."""
import importlib
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the repository root is on sys.path so that `import digcalc_project` is
# always resolvable when tests are run from any working directory (e.g., CI).
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


@pytest.fixture
def mocker(monkeypatch):
    """Very small subset of *pytest-mock*'s fixture.

    Only implements :py:meth:`patch` with *return_value* support which is all
    that our current test suite requires.  If *pytest-mock* **is** available we
    simply delegate to the real fixture so developers with the plugin installed
    get the full API.
    """
    try:
        # If pytest-mock is installed, use the real fixture to avoid surprises.
        # pylint: disable=import-error
        import pytest_mock  # noqa: F401
        # Request the real fixture from pytest's fixture store.
        return pytest.MockerFixture(monkeypatch)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover – fall back to tiny stub
        class _StubMocker:
            def __init__(self, _mp):
                self._mp = _mp

            def patch(self, target: str, **kwargs):
                module_name, attr_name = target.rsplit(".", 1)
                module = importlib.import_module(module_name)
                dummy = kwargs.get("return_value")
                if dummy is None:
                    dummy = types.SimpleNamespace()
                self._mp.setattr(module, attr_name, dummy)
                return dummy

        return _StubMocker(monkeypatch)
