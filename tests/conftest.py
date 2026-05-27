"""Pytest bootstrap for source-tree test runs.

Some Windows Python launchers start collection with ``tests/`` as the first
import root.  Insert the repository root explicitly so both ``pytest`` and
``python -m pytest`` can import ``refchecker`` and the compatibility wrapper.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
