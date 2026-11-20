"""Compatibility import alias: ``pyaddic7ed`` -> ``pyaddic7``.

This project was renamed to PyAddic7 and is published on PyPI as
``pyaddic7``. The ``pyaddic7ed`` import name keeps working for integrations
written before the rename and exposes the exact same API objects.

New code should prefer::

    import pyaddic7
"""

from pyaddic7 import *  # noqa: F401,F403

from pyaddic7 import __all__ as _pyaddic7_all
from pyaddic7 import __version__

__all__ = list(_pyaddic7_all)
