# Helen Contains Claude

I built this kit to solve three problems:

1. I want Claude Code to work on my project but not on the rest of my machine.
2. I want it to stop harassing me for permission to run commands that are obviously fine, such as the clearly baffling `ls -l tmp/`.
3. I want it never to do something terrifying based on my response to a permissions request, because one
   day, whether due to tiredness or prompt fatigue, I will say yes to a command resolving to `git reset --hard`, or to committing my GitHub keys to a public repository.

The goal of this kit is to make it easy to set up a web project running Claude Code in Docker without having to solve the above three problems every time. The threat model is just honest mistakes, so complex projects will need to make other arrangements. In particular, the GitHub token is in the container's environment: the hooks make printing it hard, not impossible.

## 1. Boundaries

**Container**
- Only this project is mounted, at `/workspace`. My home directory isn't in the container, and so neither are my SSH keys.
- Claude's login and config live in a Docker volume per project, not in my `~/.claude`.
- It runs with my uid, so files come back owned by me, but never as root. `run.sh` won't start as root at all.
- `sudo` works for exactly one command, which turns on the firewall. `chmod`, `chown` and `sudo` are denied in settings.
- The container is `--rm`. Anything Claude installs mid-session is gone when I exit, which is the correct amount of time for a unit of my attention to exist.
- My dotfiles go in read-only for quality of life (`MOUNT_DOTFILES`).
- One container per project. A second `run.sh` is refused, so two Claudes
  never fight over one working tree. Parallel sessions use git worktrees.
- Ports are published only if I list them in `PORTS`, and only on `127.0.0.1` unless `PORTS_ON_LAN=1`.

**Network** (`run.sh --firewall`)
- Outbound traffic is dropped except to Anthropic, npm, GitHub, `storage.googleapis.com`, whatever my toggles need (rubygems, PyPI), and
  anything I add to `EXTRA_ALLOWED_DOMAINS`.
- The allowlist is baked into the image in a root-owned file, and the firewall script doesn't take arguments, so nothing inside can finagle its way onto the list.
- It tests itself on start: example.com must fail, api.github.com must work.

**Claude Code's own settings**
- Reads outside the working directory are blocked. The only exceptions are `/opt` and other agents' worktrees.
- `.env` files and `.claude/settings.local.json` can't be read.

**GitHub access ish**
- Claude pushes as a separate bot account, invited only to the repos I choose.
- The token is read from `.claude/settings.local.json` into the container's environment for one `docker run`, and is never printed. Git gets it from a credential helper over a pipe, never from a URL or `.git/config`, and the helper ignores requests to save it.
- Every wrapper checks the repo against `github.local.conf`. The file is parsed rather than sourced, so it can't run code or weaken a check.
- `git-push-agent.sh` refuses to push to `main`, and to `master`, `refs/heads/main`, `+x:main` and the other spellings.
- `gh-write.sh` opens PRs and issues and comments on them. It can't merge, approve, close, delete, or touch settings.
- `gh-read.sh` sends GETs to my repos and nothing else. It refuses `env` in a jq expression, because gh's jq can read the environment the token lives in.

## 2. Claude doesn't ask me about things that are obviously fine

Most prompts are the permission checker failing to read a command and asking just in case, which teaches me to click
Yes without reading. So:

**A reviewed allow list for prompts**
- Read-only git, `git add --`, `git commit -F`, pytest, the screenshot tools and every wrapper in `scripts/` run unasked.
- A rule ending in ` *` accepts any arguments, so each one is a decision. `tests/kit/test_allow_list.py` fails on a new one until it joins a reviewed
  set, with a note saying which of the tool's options I checked for running programs or writing files.

**Wrappers for tools too powerful to allow**
- `curl -o` writes anywhere, so there's no safe rule for `curl`.
  `check-link.sh` and `github-public-status.sh` are curl with one job each.
- `gh api` will merge a PR if asked nicely. `gh-read.sh` and `gh-write.sh` are the parts of it I want.
- `cd` and `git -C` prompt every time. `git-nested.sh` (a short list of git commands inside a nested clone, hooks off) and `git-diff-main-checkout.sh`
  replace them.
- Every wrapper's refusals are tested, dry-run and offline.

**Hooks that teach Claude to write readable commands**
- Pipes, chains, `$(...)`, heredocs, globs, a leading `cd`, `python3 -c`, `node -e`, `sed` and `awk` are all refused. Each refusal says what to do
  instead: usually a script in `tmp/` with every argument written out literally, which the checker can read, and so can I.
- `/dev/null` is fine as a redirection but refused as an argument, because as an argument it counts as reading outside the project.
- A new project's Claude memory starts with the same habits, plus a reminder to pass them on to subagents, who otherwise arrive knowing none of this.

**Things Claude can check without me**
- With `WITH_PLAYWRIGHT=1`, the image has Chromium and WebKit. Claude screenshots its own work, crops single elements and reads computed styles.
- At session start, a hook tells Claude where it is: container or host, which branch, clean or dirty, ahead of or behind `main`. Fewer wrong assumptions, fewer silly questions for Helen.

**An image I don't have to babysit**
- The image rebuilds when the content of its inputs changes. Reverting an edit goes back to the image that already matches.
- A new Claude Code release rebuilds only the last layer. Offline, the image starts as it is.
- A typo in `kit.env` is treated as an error rather than a surprise default setting.

## 3. Claude never asks me about scary things

A dangerous command is not offered to me as a Yes/No question, flagged, queued or politely raised, only refused. Claude is told what to
do instead.

- Denied outright: `chmod`, `chown`, `sudo`, merging a PR, approving a PR.
- No commits or merges on `main`.
- No `reset --hard`, `checkout --`, `clean -f` or `restore` with uncommitted changes, and no `stash drop` or `stash clear` while stashes exist. On a clean tree they're allowed, because there's nothing to lose.
- No printing secrets: no secret in `echo` or `printf`, no `${TOKEN:-x}` (which is the token, if set), no token in a URL, no literal `ghp_…`, no
  `printenv`, no `env` in a gh call. It reads the scripts a command runs too, since every other guard sends Claude off to write scripts.
- The git reads that run unasked can't write files or run programs: `--output`, `--no-index`, `--ext-diff` and `--textconv` are refused.
- Wrappers refuse rather than ask: `refused -- <reason>`, exit 2.
- One plain command per Bash call, and every description says what it reads or writes, and where. When I am asked, the question is short and says what the command does so it's simple for me to decide on.
- Anything that has to reach outside the project is written to a script in `scripts/` with one fixed action, checked arguments, safety stated at
  the top, and tests. It goes on the allow list only when I say so.
- A recommendation to add a GitHub ruleset on `main`, for when everything above has somehow failed.
- No bursts of issues or PRs to avoid GitHub flagging the account as spam. `guard-github-burst.py` allows one every 5 minutes, and 20 issues or 20 PRs a day, and none from inside a script, since a script can loop. `github-public-status.sh` checks whether it happened anyway: a page that's 404 logged out but 200 through the API.

The mechanism behind each hook is in [`.claude/hooks/README.md`](.claude/hooks/README.md).

## Getting started

You need Docker and `python3` on the host (WSL2 + Docker Desktop is fine).

0. **Make the project from the kit.** In the new project's empty git repo,
   with the kit cloned beside it:

       python3 ../helen-contains-claude-webdev/tools/kit/sync.py --kit ../helen-contains-claude-webdev --adopt

   That writes the kit's files, this project's own starting files (`CLAUDE.md`,
   `kit.env`, `.gitignore`…) and `.claude/kit/kit.lock`. Don't copy the kit
   repo wholesale: its `kit/` folder marks a repo as the kit itself.

1. **Name it.** This names the image, the container and the volumes:

       python3 .devcontainer/set-project-name.py myproject

2. **Pick toolchains** in `.devcontainer/kit.env`:

   | Toggle | Adds |
   |---|---|
   | *(always)* | Debian bookworm, git, curl, jq, Python 3, pytest, Node, `gh`, Claude Code |
   | `WITH_RUBY=1` | Ruby `RUBY_VERSION` (base becomes `ruby:<v>-slim-bookworm`), build headers, a persistent bundle cache |
   | `WITH_PLAYWRIGHT=1` | Playwright `PLAYWRIGHT_VERSION` + headless Chromium and WebKit (nearest Safari) under `/opt/playwright`, npm and pip bindings |
   | `WITH_AUDIVERIS=1` | Audiveris `AUDIVERIS_VERSION` (sheet-music PDFs to MusicXML, with its own Java) under `/opt/audiveris`, the full tessdata English OCR model under `/opt/audiveris-tessdata`, and Pillow, PyMuPDF and pypdf. x86_64 only |
   | `WITH_PY_REQS=1` | `pip install -r .devcontainer/requirements.txt`: PyYAML and Pillow, plus whatever you add |

   Also in `kit.env`: `PORTS` (e.g. `"5000:5000 5001:5001"`), `EXTRA_ALLOWED_DOMAINS`
   for the firewall, and `MOUNT_DOTFILES`.

3. **GitHub agent account** (skip this step if Claude won't push):
   - Create a separate GitHub account for the bot and invite it as a
     collaborator on just the repos you want it to work in.
   - Give it a classic PAT scoped to `repo`, plus `workflow` if it should
     edit `.github/workflows/`.
   - `cp .claude/settings.local.example.json .claude/settings.local.json`
     (gitignored) and paste the token between the quotes. An empty value
     means the container starts without one.
   - `cp scripts/github.conf scripts/github.local.conf` (gitignored) and fill
     in `GH_OWNER`, `GH_REPOS` (the first is the default), `GH_AGENT_USER`,
     and `MAIN_PUSH_REPOS` if any repo may take direct pushes to `main`.

4. **Fill in `CLAUDE.md`**: the project name, the build/test commands, and
   any project rules. The kit's rules arrive through its
   `@.claude/kit/RULES.md` line; don't edit that file here.

5. **Run it:**

       bash .devcontainer/run.sh            # or --firewall
       claude

   The first build takes a few minutes, as does the first after a change.
   The first `claude` asks you to log in. The login is kept in the project's
   config volume, so it's once per project, not once per container.

`run.sh --rebuild` rebuilds from scratch, pulling the base image fresh.
`--build-only` builds and stops. For VS Code, use Dev Containers →
**Reopen in Container**: `devcontainer.json` runs `run.sh --build-only` first,
so both routes use the same image.

## Staying in step with the kit

Every file has one owner (`kit/manifest` in the kit): the kit's files arrive
by sync, the project's own are never touched, and `.claude/settings.json` and
`devcontainer.json` are generated from a kit part and a project part.

- **Sync:** tell Claude "sync the kit" (`/kit-sync`). It opens one PR, or
  nothing when the kit hasn't moved, and says when to run `run.sh` again.
- **Which kit am I on?** `python3 tools/kit/sync.py --status`, and every
  session starts with a `kit:` line saying how far behind it is.
- **A kit file edited in a project** turns the suite red, naming the file.
  The change goes to the kit as a PR there, then comes back by sync.
- **Project additions** go in `.claude/settings.project.json` (allow rules,
  hooks) and `.devcontainer/kit.env`; then `python3 tools/kit/build.py`. A
  project allow rule can't undo a kit deny: the builder refuses it.
- **A Jekyll site** must exclude the kit's folders (`scripts`, `tests`,
  `tools`) in `_config.yml`; `tests/kit/test_site_excludes_kit.py` checks it,
  and checks the built site when there is one.
- **Never start Claude inside a nested clone** (a drafts folder, say): the
  project's rules and guard hooks don't load there. A hook baked into the
  image warns if you do.

## When things bite

- **A push touching `.github/workflows/` is refused** by GitHub unless the
  token has the `workflow` scope. The fix is a new token, not a retry.
- **A Pages workflow publishes nothing** until you set the repository's
  Settings → Pages → Source to GitHub Actions. The agent may not change
  repository settings, so that one is yours.
- **The firewall resolves hosts once**, at start. A CDN that rotates
  addresses can drop out mid-session; `sudo /usr/local/bin/init-firewall.sh`
  re-resolves.
- **The base image and apt packages moving upstream** don't trigger a
  rebuild. Use `--rebuild` when that matters.
- **To pin Claude Code for one run:** `PIN_CLAUDE_CODE=2.1.0 bash .devcontainer/run.sh`.
- **To try a branch's `kit.env` or Dockerfile** before merging, run that
  worktree's copy from the host:
  `bash .claude/worktrees/<name>/.devcontainer/run.sh`. It always mounts the
  primary clone.
- **A server must listen on `0.0.0.0`** to be reachable through a published port.
- **VS Code and the token:** export `AGENT_GH_TOKEN` in the host shell VS
  Code starts from. The firewall needs
  `"runArgs": ["--cap-add=NET_ADMIN", "--cap-add=NET_RAW"]` and
  `"postStartCommand": "sudo /usr/local/bin/init-firewall.sh"` in
  `devcontainer.json`, which is generated: an edit there is undone by the
  next build, and `kit.env` has no toggle for it yet.

## Tests

    python3 -m pytest

They cover the wrappers' refusals (dry-run, no network), the hooks, the build
stamp and the config. Working on the kit itself, rather than a project made
from it? See [`docs/maintaining-the-kit.md`](docs/maintaining-the-kit.md).
