#!/usr/bin/env python3
"""Refuse any Bash command that runs `awk` (or gawk, mawk, nawk).

awk's program arrives inline, where the permission checker cannot see it write
a file (`print > "path"`) or run a command (`system()`). Python in a file
covers it, in a form the checker can name.

Allowed on purpose: the word inside a quoted string or heredoc, and tokens that
merely contain it (`guard-awk.py`, `hawkish.txt`).

Invoked as `python3 <path>` so it needs no execute bit.
"""
from __future__ import annotations

import json
import re
import sys

AWKS = {"awk", "gawk", "mawk", "nawk"}
TOKEN_SPLIT = re.compile(r"[\s|;&()]+")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1.*?^\2$",
    re.DOTALL | re.MULTILINE,
)


def _mentions_awk(command: str) -> bool:
    stripped = QUOTED.sub(" ", HEREDOC.sub(" ", command))
    return any(t and t.rsplit("/", 1)[-1] in AWKS for t in TOKEN_SPLIT.split(stripped))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not _mentions_awk(command):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "BLOCKED: this command runs `awk`. No awk, in any form: its "
                "program can write files and run commands where the "
                "permission checker cannot see.\n\n"
                "Write it in Python in tmp/ and run the file. If this case "
                "genuinely needs awk, say so and let the human decide."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
