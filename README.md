# Helen Contains Claude, web dev edition

A quickstart kit for Claude Code in Docker for web projects, built to solve three problems:

1. I want Claude working on my project, not on the rest of my machine.
2. I want it to stop asking permission for things that are obviously fine, such as the clearly baffling `ls -l tmp/`.
3. One day, tired, I will say yes to `git reset --hard` or to committing my GitHub token, so don't ever ask me those questions.

The threat model is only honest mistakes. Hooks make printing the token hard, not impossible.

## 1. Boundaries

**Container.** Only the project is mounted, at `/workspace`. No home directory, no SSH keys. Claude's login and config live in a per-project Docker volume. It runs as my uid, never root, and is `--rm`, so anything installed mid-session is gone when I exit, which is the correct amount of time for a unit of my attention to exist. One container per project: parallel sessions use git worktrees. Only the ports I list are published.

**Network** (`run.sh --firewall`). Outbound traffic is dropped except to Anthropic, npm, GitHub, `storage.googleapis.com`, whatever the toggles need, and `EXTRA_ALLOWED_DOMAINS`. The list is baked into the image, root-owned, and the firewall script takes no arguments. It checks itself on start: example.com must fail, api.github.com must work.

**Reads.** Nothing outside the working directory except `/opt` and other agents' worktrees. No `.env` files, no `.claude/settings.local.json`.

**GitHub.** Claude pushes as a separate bot account, invited only to the repos I choose. Git gets the token from a credential helper, never a URL or `.git/config`. Every wrapper checks the repo against `scripts/github.local.conf`, which is parsed, not sourced:
- `git-push-agent.sh` refuses `main` in all its spellings;
- `gh-write.sh` opens and edits PRs and issues, and can't merge, approve, close or touch settings; a repo in `PR_ONLY_REPOS` gets PRs only;
- `gh-read.sh` sends GETs and nothing else.

## 2. No asking about obviously fine things

Most prompts are the permission checker failing to parse a command and asking just in case, which trains me to click Yes without reading properly.

- **An allow list** for read-only git, `git add --`, `git commit -F`, pytest, the screenshot tools and every wrapper. A rule ending ` *` accepts any argument, so `tests/kit/test_allow_list.py` fails on a new one until it's reviewed, with a note on which of the tool's options I checked.
- **Wrappers for tools too powerful to allow.** `curl -o` writes anywhere; `check-link.sh` is curl with one job. `gh api` will merge a PR if asked nicely; `gh-read.sh` and `gh-write.sh` are the parts I want. `cd` and `git -C` always prompt; `git-nested.sh` and `git-diff-main-checkout.sh` replace them. Every refusal is tested offline.
- **Hooks that teach readable commands.** Pipes, chains, `$(...)`, globs and a leading `cd` are refused with a pointer to the alternative, usually a script in `tmp/` with literal arguments. Claude Code also prompts for any `$VARIABLE` on a command line, however harmless, so the kit wraps the ones Claude needs (`kit-ports.sh`).
- **Checking its own work.** With `WITH_PLAYWRIGHT=1`: screenshots in Chromium and WebKit, crops, computed styles. A session-start hook says where Claude is: container or host, branch, dirty or clean, behind `main`, behind this kit.

## 3. No asking about scary things

A dangerous command is refused, not offered as a question.
- `chmod`, `chown`, `sudo`, merging and approving PRs.
- Commits or merges on `main`.
- `reset --hard`, `checkout --`, `restore`, `clean -f` over uncommitted work; `stash drop`/`clear` while stashes exist.
- Printing secrets in any of the usual ways, including from inside a script Claude wrote to get around the other guards.
- Git reads that write files or run programs (`--output`, `--ext-diff`, ...).
- Inline programs: `sed`, `awk`, `python3 -c`, `node -e`. Each can write or run anything, and the checker can't tell what. Written to a script in `tmp/` they're no safer, but at least there's a file to open and a record of what ran. The rest is down to the container boundary.
- Issue or PR bursts, which get the account flagged as spam: one per 5 minutes, 20 of each a day. `github-public-status.sh` checks for the flag (404 logged out, 200 through the API).

Each hook's mechanism is in [`.claude/hooks/README.md`](.claude/hooks/README.md).

## Getting started

Needs Docker and `python3` on the host (WSL2 + Docker Desktop is fine).

0. **Make the project**, from its empty repo with the kit cloned beside it:

       python3 ../helen-contains-claude-webdev/tools/kit/sync.py --kit ../helen-contains-claude-webdev --adopt

   Don't copy the kit repo: its `kit/` folder marks a repo as the kit itself.

1. **Name it:** `python3 .devcontainer/set-project-name.py myproject` (image, container, volumes).

2. **Pick toolchains** in `.devcontainer/kit.env`:

   | Toggle | Adds |
   |---|---|
   | *(always)* | Debian bookworm, git, curl, jq, Python 3, pytest, Node, `gh`, Claude Code |
   | `WITH_RUBY=1` | Ruby, build headers, a persistent bundle cache |
   | `WITH_PLAYWRIGHT=1` | Playwright with Chromium and WebKit, npm and pip bindings |
   | `WITH_AUDIVERIS=1` | Audiveris (sheet-music PDFs to MusicXML) with its OCR model, Pillow, PyMuPDF and pypdf. x86_64 only |
   | `WITH_PY_REQS=1` | `.devcontainer/requirements.txt` (exact pins only) |

   Plus `PORTS`, `EXTRA_ALLOWED_DOMAINS` and `MOUNT_DOTFILES`. Give each project on a machine its own block of ports so they can run side by side.

3. **GitHub** (skip if Claude won't push). A bot account invited to the chosen repos, with a classic PAT (`repo`, plus `workflow` to touch `.github/workflows/`). Then two gitignored files, the only per-machine setup a project needs:
   - `.claude/settings.local.json`, from `settings.local.example.json`, holding the token;
   - `scripts/github.local.conf`, from `scripts/github.conf`: owner, repos, bot account, and optionally `MAIN_PUSH_REPOS`, `PR_ONLY_REPOS` and `NESTED_DIRS` (gitignored clones inside the project, such as a private drafts repo; paths may nest). Worktrees read the main checkout's copy.

4. **Fill in `CLAUDE.md`'s "This project" section.** The kit's rules arrive via `@.claude/kit/RULES.md`.

5. **Run:** `bash .devcontainer/run.sh` (or `--firewall`), then `claude` or `claude --worktree whatever`. Logging in (via Anthropic) is only required once per project. `--rebuild` starts from scratch. VS Code's **Reopen in Container** uses the same image.

Handy hint: **to pin the Claude Code version**, `PIN_CLAUDE_CODE=2.1.0 bash .devcontainer/run.sh`.

## Staying in step

`kit/manifest` gives every file one owner: kit files arrive by sync, project files are never touched, and `.claude/settings.json` and `devcontainer.json` are generated from a kit part plus `settings.project.json` and `kit.env`.

- **Sync:** tell Claude "sync the kit" (`/kit-sync`). One PR, or nothing if the kit hasn't moved.
- **Editing a kit file in a project** turns the suite red. Change it in the kit, then sync.
- **A file the project must own outright** goes in `.claude/kit/watched`: never overwritten, and the sync report says when the kit's version moves.
- **A Jekyll site** must exclude `scripts`, `tests` and `tools`; a test checks.
- **Never start Claude inside a nested clone.** No rules or hooks load there, and the image warns you.

## Easy to get wrong

- **A hook change takes effect from the checkout the session started in**, usually `main`. A branch that fixes a guard is still guarded by the old one until it's merged and pulled.
- **Pushing `.github/workflows/`** needs the `workflow` scope.
- **A Pages workflow publishes nothing** until Settings → Pages → Source is GitHub Actions.
- **The firewall resolves hosts once.** If a CDN rotates, `sudo /usr/local/bin/init-firewall.sh` re-resolves.
- **Upstream base-image and apt changes don't trigger a rebuild.** Use `--rebuild`.
- **To try a branch's container changes**, run its worktree's `run.sh` from the host.
- **`.devcontainer/kit.local.env`** (gitignored) can override `PROJECT_NAME` and `PORTS` for one machine. Mostly for the kit's own checkout; a project should commit both.
- **VS Code:** export `AGENT_GH_TOKEN` in the shell it starts from. `--firewall` has no VS Code toggle yet.

Working on the kit itself: [`docs/maintaining-the-kit.md`](docs/maintaining-the-kit.md).
