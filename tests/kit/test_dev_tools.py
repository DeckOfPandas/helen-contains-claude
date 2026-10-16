"""tools/dev/: the scripts parse, and refuse bad arguments before needing a browser.

Taking a real screenshot needs WITH_PLAYWRIGHT=1, so it is not tested here.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.mark.parametrize("script", ["shoot.js", "slice-png.js"])
def test_parses(kit_root, script):
    subprocess.run([NODE, "--check", str(kit_root / "tools" / "dev" / script)], check=True)


@pytest.mark.parametrize("script,args", [
    ("shoot.js", []),
    ("shoot.js", ["http://127.0.0.1:9000"]),
    ("shoot.js", ["http://127.0.0.1:9000", "a/b"]),
    ("shoot.js", ["http://127.0.0.1:9000", "x", "--scheme", "sepia"]),
    ("shoot.js", ["http://127.0.0.1:9000", "x", "--click"]),
    ("slice-png.js", []),
    ("slice-png.js", ["shot.png"]),
    ("slice-png.js", ["tmp/../x.png"]),
    ("slice-png.js", ["tmp/x.jpg"]),
    ("slice-png.js", ["tmp/x.png", "10"]),
])
def test_refuses(kit_root, tmp_path, script, args):
    done = subprocess.run([NODE, str(kit_root / "tools" / "dev" / script), *args],
                          cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert done.returncode == 2, done.stderr
    assert "usage" in done.stderr or "must be" in done.stderr, done.stderr
