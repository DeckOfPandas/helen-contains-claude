#!/usr/bin/env python3
"""Refuse a Bash command the permission checker cannot statically analyse.

The checker proves before anything runs that a command touches only the working
directory, and can do that only when the command's text is its whole meaning.
Otherwise it prompts the human; a denial here lands on the session instead,
which can put the cleverness in a file and run the file.

Refused: a heredoc; `$(...)` or backticks; a glob `*`; a leading `cd`;
chaining with `&&`, `||` or `;`; a pipe; a quoted `[`, `]` or `|` given to
`sh scripts/...`; a leading `NAME=value`; an unquoted `(` or `)`;
`git -C <path>`; and `$[` outside single quotes.

Allowed: redirection to a static path (`2>&1`, `>/dev/null`), anything inside
quotes except substitution and `$[` inside DOUBLE quotes, a bare `$VAR`, and
`--flag=value` or lowercase `git -c key=value`.

Invoked as `python3 <path>` so it needs no execute bit.
"""
from __future__ import annotations

import json
import re
import sys

_REDIRECT = re.compile(r"\d*>{1,2}\s*&?\s*\d*|\d*<\s*")
_LEADING_CD = re.compile(r"^\s*cd(\s|$)")
# Case-sensitive: lowercase `git -c key=value` is how the git wrappers pass
# their credential helper.
_GIT_DASH_C = re.compile(r"(?:^|\s)git\s+-C(?=\s|$)")
# A live `$[`: an escaped dollar is inert, a dollar after an escaped backslash
# is not.
_LEGACY_ARITHMETIC = re.compile(r"(?<!\\)(?:\\\\)*\$\[")
_GLOB = re.compile(r"\*")
_SCRIPT_CALL = re.compile(r"^\s*sh\s+scripts/")
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

FILE_IT = "put the command in a script in tmp/ and run the file"


def _has_leading_env_assignment(bare: str) -> bool:
    """`NAME=value cmd`. `FOO=bar` alone runs nothing and passes."""
    tokens = bare.split()
    count = 0
    for token in tokens:
        if not _ENV_ASSIGNMENT.match(token):
            break
        count += 1
    return 0 < count < len(tokens)


def _strip_quoted(command: str, quotes: str) -> str:
    """Blank spans in the given quote characters, keeping offsets stable.

    Backslash escapes are honoured outside single quotes, so an escaped quote
    does not close a span early.
    """
    out = []
    quote = None
    escaped = False
    for ch in command:
        if escaped:
            out.append(" " if quote is not None else ch)
            escaped = False
        elif ch == "\\" and quote != "'":
            out.append(" " if quote is not None else ch)
            escaped = True
        elif quote is None and ch in quotes:
            quote = ch
            out.append(" ")
        elif quote is not None and ch == quote:
            quote = None
            out.append(" ")
        elif quote is not None:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _offence(command: str) -> tuple[str, str] | None:
    bare = _strip_quoted(command, "'\"")
    live = _strip_quoted(command, "'")       # substitution is live in "..."

    if "<<" in bare:
        return ("a heredoc", "write the content to a file in tmp/ and pass the file")
    if "$(" in live or "`" in live:
        return ("command substitution",
                "for a commit message or PR body, write a file and pass it "
                "(`git commit -F tmp/msg.txt`); otherwise " + FILE_IT)
    if _LEGACY_ARITHMETIC.search(live):
        return ("`$[` outside single quotes", "put the regex in single quotes")
    if _LEADING_CD.match(bare):
        return ("a leading `cd`", "drop it: the Bash tool already runs in the project root")
    if _GIT_DASH_C.search(bare):
        return ("`git -C <path>`",
                "drop it: every git allow rule names the subcommand, and `-C` "
                "before it defeats the match")
    if _has_leading_env_assignment(bare):
        return ("a leading `NAME=value`", FILE_IT)

    scannable = _REDIRECT.sub(" ", bare)
    if "|" in scannable:
        return ("a pipe", FILE_IT)
    if "&&" in scannable or "||" in scannable or ";" in scannable:
        return ("chained commands", "one command per Bash call")
    if re.search(r"[()]", re.sub(r"\\[()]", "  ", scannable)):
        return ("an unquoted `(` or `)`", "single-quote the argument, or " + FILE_IT)
    if _GLOB.search(scannable):
        return ("a glob", "point the command at the directory and let it recurse")
    if _SCRIPT_CALL.match(command) and any(
        bare[i] == " " and ch in "[]|" for i, ch in enumerate(command)
    ):
        return ("a quoted `[`, `]` or `|` in a scripts/ wrapper's arguments",
                "for a GitHub read use `--fields a,b` or `--each a,b`")
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return 0
    try:
        found = _offence(command)
    except Exception:
        return 0
    if not found:
        return 0
    shape, remedy = found
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"BLOCKED: this command contains {shape}, so the permission "
                "checker cannot statically analyse it and would prompt the "
                "human. A denial lands on the session instead.\n\n"
                f"WHAT TO DO INSTEAD: {remedy}."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
