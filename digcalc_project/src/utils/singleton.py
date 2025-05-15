from __future__ import annotations

"""singleton.py
Utility module providing a trivial *Singleton* base‑class that can be inherited
by services requiring a single application‑wide instance.

The implementation is intentionally lightweight – only one instance per Python
process.  Classes inheriting from :class:`Singleton` **must** implement their
own *idempotent* ``__init__`` (guarding against re‑initialisation) if they hold
state initialisation that should run once.
"""

from typing import Any


class Singleton:  # noqa: D101 – trivial helper
    _instance: Singleton | None = None

    def __new__(cls, *args: Any, **kwargs: Any):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
