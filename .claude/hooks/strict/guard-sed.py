#!/usr/bin/env python3
"""Refuse any Bash command that runs `sed`, in any form.

A subtly wrong regex corrupts a file silently, with none of the visible diff an
Edit call gives, and Python in a file covers everything sed does. It does not
tell a safe sed from an unsafe one: that detection is where the next gap grows.

Allowed on purpose: the word inside a quoted string or heredoc, and tokens that
merely contain it (`guard-sed.py`, `processed.txt`).

Invoked as `python3 <path>` so it needs no execute bit.
"""
from __future__ import annotations

import json
import re
import sys

TOKEN_SPLIT = re.compile(r"[\s|;&()]+")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1.*?^\2$",
    re.DOTALL | re.MULTILINE,
)


def _mentions_sed(command: str) -> bool:
    stripped = QUOTED.sub(" ", HEREDOC.sub(" ", command))
    return any(t and t.rsplit("/", 1)[-1] == "sed" for t in TOKEN_SPLIT.split(stripped))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not _mentions_sed(command):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "BLOCKED: this command runs `sed`. No sed, in any form.\n\n"
                "Use the Edit tool for a file change, or write the "
                "transformation in Python in tmp/ and run the file. If this "
                "case genuinely needs sed, say so and let the human decide."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
