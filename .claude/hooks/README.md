# Hooks

Each hook is one Python file with no imports beyond the standard library. Each is
run as `python3 <path>`, so none needs an execute bit.

## On by default (wired in `.claude/settings.json`)

| Hook | Event | Does |
|---|---|---|
| `session-ground-truth.py` | SessionStart | Reports the checkout, container or host, branch, dirty tree, and position against `origin/main` |
| `guard-main-branch.py` | PreToolUse Bash | Refuses `git commit` / `git merge` on `main` or `master` |
| `guard-destructive-git.py` | PreToolUse Bash | Refuses `reset --hard`, `checkout --`, `clean -f`, `restore` on a dirty tree; `stash drop/clear` while stashes exist |
| `guard-token-expansion.py` | PreToolUse Bash | Refuses commands that would print a secret, embed one in a URL, or dump the environment |

## Strict mode (in `strict/`, off by default)

These four push Claude towards commands the permission checker can analyse, so
it prompts you less. They also make Claude write more small scripts in `tmp/`.

| Hook | Refuses |
|---|---|
| `strict/guard-sed.py` | any `sed` |
| `strict/guard-awk.py` | any `awk` / `gawk` / `mawk` / `nawk` |
| `strict/guard-inline-script.py` | `python3 -c`, `node -e`, `ruby -e`, `perl -e` |
| `strict/guard-unanalyzable-bash.py` | heredocs, `$(...)`, pipes, `&&`/`;` chains, globs, a leading `cd`, `git -C`, a leading `NAME=value` |

To turn one on, add an entry to the `PreToolUse` → `Bash` hooks list in
`.claude/settings.json`:

```json
{
  "type": "command",
  "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/strict/guard-unanalyzable-bash.py\"",
  "timeout": 20,
  "statusMessage": "Checking the command can be analysed"
}
```

If you turn on `guard-unanalyzable-bash.py`, add a line to `CLAUDE.md` that says
so. Claude then knows to put multi-step commands in a `tmp/` script before it
gets refused.
