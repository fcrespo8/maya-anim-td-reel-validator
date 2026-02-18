# -*- coding: utf-8 -*-
from __future__ import annotations

from .app import ValidatorWindow

_WINDOW = None

def show() -> None:
    global _WINDOW
    try:
        if _WINDOW:
            _WINDOW.close()
    except Exception:
        pass

    _WINDOW = ValidatorWindow()
    _WINDOW.show_docked()


if __name__ == "__main__":
    show()
