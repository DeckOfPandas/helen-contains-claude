# Claude Code project kit

A starting point for a project where Claude Code works inside a Docker sandbox.
Only the project folder is mounted (at `/workspace`), so Claude cannot read
`~/.ssh`, your other projects, or anything else on the host. On top of the
sandbox it adds guard hooks, an agent-account GitHub workflow, and a
`CLAUDE.md` starter.

Make this a **template repository** on GitHub (Settings → Template
repository). Each new project then starts from **Use this template**.

## What's in the box

```
.devcontainer/
  run.sh                 build-if-stale, then start the container
  kit.env                toggles: what goes in the image, ports, firewall extras
  Dockerfile             the image; every toggle is a build argument
  init-firewall.sh       optional default-deny egress allowlist
  requirements.txt       pip installs, when WITH_PY_REQS=1
  project.bashrc         project aliases, read live from the mount
  container.bashrc       loads project.bashrc and host dotfiles, once per shell
  devcontainer.json      VS Code Dev Containers, using the same image
  build_inputs_hash.py   the build stamp (see "Staying current")
  claude_code_latest.py  asks npm for the newest Claude Code
  read_local_token.py    reads AGENT_GH_TOKEN for one docker run
  set-project-name.py    sets PROJECT_NAME in kit.env and devcontainer.json
.claude/
  settings.json          permissions + hooks
  hooks/                 guards (see .claude/hooks/README.md); strict/ is opt-in
scripts/
  github.conf            owner, repos, bot account: the wrappers' whole world
  gh-*.sh, git-*-agent.sh, git-fetch-main.sh, github-public-status.sh
CLAUDE.md                rules starter: fill in <PROJECT> and the build commands
tests/kit/               tests for the wrappers, hooks, stamp and config
```

## Setting up a new project

You need Docker and `python3` on the host (WSL2 + Docker Desktop is fine).

1. **Name it.** This names the image, the container and the volumes:

       python3 .devcontainer/set-project-name.py myproject

2. **Pick toolchains** in `.devcontainer/kit.env`:

   | Toggle | Adds |
   |---|---|
   | *(always)* | Debian bookworm, git, curl, jq, Python 3, Node, `gh`, Claude Code |
   | `WITH_RUBY=1` | Ruby `RUBY_VERSION` (base becomes `ruby:<v>-slim-bookworm`), build headers, a persistent bundle cache |
   | `WITH_PLAYWRIGHT=1` | Playwright `PLAYWRIGHT_VERSION` + headless Chromium under `/opt/playwright`, npm and pip bindings |
   | `WITH_PY_REQS=1` | `pip install -r .devcontainer/requirements.txt` |

   Also in `kit.env`: `PORTS` (e.g. `"5998:4000"`), `EXTRA_ALLOWED_DOMAINS`
   for the firewall, and `MOUNT_DOTFILES`.

3. **GitHub agent account** (skip this step if Claude won't push):
   - Create a separate GitHub account for the bot. Invite it as a
     collaborator on just the repos it should touch.
   - Give it a classic PAT with `repo` scope, plus `workflow` scope if it
     should edit `.github/workflows/`.
   - Put the token in `.claude/settings.local.json`, which is gitignored. A
     fresh project doesn't have that file yet, so copy the committed example
     into place first, then paste the token between the quotes:

         cp .claude/settings.local.example.json .claude/settings.local.json

     `run.sh` reads the token for each `docker run` and never prints it. An
     empty value means no token, and the container starts without one.
   - Fill in `scripts/github.conf`: `GH_OWNER`, `GH_REPOS` (the first is the
     default), `GH_AGENT_USER`, and `MAIN_PUSH_REPOS` if any repo may take
     direct pushes to `main`.
   - Optionally, protect `main` with a ruleset as well. The wrappers refuse
     to push there, but a ruleset is a second wall.

4. **Fill in `CLAUDE.md`**: the project name and the build/test commands. Add
   any project rules.

5. **Run it:**

       bash .devcontainer/run.sh            # or --firewall
       claude                               # first time: log in (below)

   The first build takes a few minutes. Later starts are instant unless
   something changed.

### First login

`claude` prints a login URL. Open it in your normal browser on the host and
sign in. Either it completes on its own, or the browser shows a code to paste
back into the terminal (common on WSL2). The login lives in a named volume
(`<project>-claude-config`), so it survives container restarts.

## Using it

- `bash .devcontainer/run.sh` starts the container. `--rebuild` rebuilds from
  scratch, pulling the base image fresh. `--build-only` builds and stops.
- **One container per project.** The fixed container name refuses a second
  `run.sh`, so two Claudes never edit one working tree. To run several
  sessions at once, use git worktrees inside the one container.
- Run `run.sh` from inside a worktree and it still mounts the primary clone,
  so all worktrees share one container.
- `.devcontainer/project.bashrc` holds project aliases. It is read from the
  mount at shell start, so edits need no rebuild. A server must listen on
  `0.0.0.0` to be reachable through a published port.

### The firewall

`run.sh --firewall` adds `NET_ADMIN`/`NET_RAW` and runs `init-firewall.sh`
before the shell starts. Outbound traffic is then dropped except to:
Anthropic, npm, GitHub, `storage.googleapis.com`, rubygems (when Ruby is on),
PyPI (when the requirements toggle is on), and `EXTRA_ALLOWED_DOMAINS`. The
list is written into the image at build time, in a root-owned file, so nothing
inside the container can widen it. Hosts are resolved once at start; a
rotating CDN can drop out mid-session, and re-running the script re-resolves
them.

### VS Code

Dev Containers → **Reopen in Container**. `devcontainer.json` runs
`run.sh --build-only` on the host first, then uses the same image, so the two
routes cannot drift. Export `AGENT_GH_TOKEN` in the host shell VS Code starts
from if the wrappers need it there. For the firewall, add
`"runArgs": ["--cap-add=NET_ADMIN", "--cap-add=NET_RAW"]` and
`"postStartCommand": "sudo /usr/local/bin/init-firewall.sh"`.

## Staying current

**The image is checked against the files on every start.** `run.sh` stamps
each image with a SHA-256 of its build context and build arguments. When the
stamp no longer matches, it rebuilds. The check compares content, not
timestamps: `touch` costs nothing, and reverting an edit goes back to the image
that already matches. Files in `.devcontainer/.dockerignore` (run.sh, kit.env's
comments, these helpers) are outside the stamp, so editing them doesn't
rebuild.

**Claude Code updates by rebuild.** Every start asks npm for the newest
version. If the image has an older one, only the last layer rebuilds. When
offline, the image starts as it is. To pin a version for one run:
`PIN_CLAUDE_CODE=2.1.0 bash .devcontainer/run.sh`.

**What the stamp can't see:** the base image or apt packages moving upstream.
Use `--rebuild` when that matters.

## What this does and doesn't protect against

**Does:** it stops Claude, or a mistaken command it runs, from reading anything
outside the project, structurally rather than by convention. With
`--firewall`, it also stops traffic to hosts outside the allowlist. The hooks
stop commits to `main`, destructive git on a dirty tree, and the common ways a
token ends up printed.

**Doesn't:** it is not a defence against a deliberate, sophisticated container
escape. The threat model is an honest mistake. Also, the token is in the
container's environment: the hooks make printing it hard, not impossible.

## Tests

    python3 -m pytest

These cover the wrappers' refusals (dry-run, no network), the hooks, the build
stamp, and that `kit.env` and `devcontainer.json` agree. They need `pytest`;
put it in `requirements.txt` with `WITH_PY_REQS=1`, or run them on the host.
