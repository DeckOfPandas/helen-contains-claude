#!/usr/bin/env python3
"""Refuse ANY inline program passed to an interpreter's -c/-e. Put it in a file.

Matched: `-c` after python/python2/python3, `-e` after ruby/node/perl. An
inline program is opaque to the permission checker, so under
`blockReadsOutsideWorkingDirectories` it prompts the human at any length.
A file argument is one static path, so it is silent, and it leaves a record.

Allowed on purpose: a file argument; `-c` on other commands (`git -c k=v`);
`sh -c` and `bash -c`. A command that will not tokenise is allowed rather than
guessed at.

Invoked as `python3 <path>` so it needs no execute bit.
"""
from __future__ import annotations

import json
import shlex
import sys

INTERPRETERS = {
    "python": "-c", "python3": "-c", "python2": "-c",
    "ruby": "-e", "node": "-e", "perl": "-e",
}


def _offending_program(command: str) -> tuple[str, str] | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, token in enumerate(tokens):
        name = token.rsplit("/", 1)[-1]
        flag = INTERPRETERS.get(name)
        if flag is None:
            continue
        for j in range(i + 1, len(tokens)):
            if tokens[j] == flag:
                if j + 1 < len(tokens):
                    return name, flag
                break
            if not tokens[j].startswith("-"):
                break
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    found = _offending_program(command)
    if not found:
        return 0
    name, flag = found
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"BLOCKED: this `{name} {flag}` program belongs in a file, "
                "however short.\n\n"
                "An inline program is opaque to the permission checker, so it "
                "always prompts the human. Write it with the Write tool and run "
                "the file:\n\n"
                "    Write  tmp/thing.py\n"
                "    Bash   python3 tmp/thing.py"
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
