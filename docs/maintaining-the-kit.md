# Maintaining the kit

The kit is a template, so what it commits is what every new project starts
from. Keep the committed copies as placeholders (`PROJECT_NAME=changeme`,
`your-org`, `<PROJECT>`) and put your own values in the gitignored local files:

    cp .devcontainer/kit.local.example.env .devcontainer/kit.local.env   # PROJECT_NAME
    cp scripts/github.conf scripts/github.local.conf                     # GitHub
    cp .claude/settings.local.example.json .claude/settings.local.json   # token

`tests/kit/` fails if `scripts/github.conf` holds anything but the
placeholders. Nothing checks the name or `CLAUDE.md`'s title, because a
project made from the kit commits its own.

## Who owns what

`kit/manifest` names every file the kit tracks, each with one owner:

- **`kit`**: copied whole into projects by every sync. Edit it here, never in
  a project: a project's `tests/kit/test_kit_lock.py` goes red when one
  differs from `.claude/kit/kit.lock`.
- **`project`**: written into a project once, from the template the manifest
  names, when the project lacks it; a sync never touches it again. The kit's
  own copy is only the kit's.
- **`generated`**: `.claude/settings.json` and
  `.devcontainer/devcontainer.json`, written by `python3 tools/kit/build.py`.
- **`kit-repo`**: this repo's own, never shipped.

A new file needs a line there, or `tests/kit/test_kit_manifest.py` fails. A
file under a `kit` folder (`scripts/`, `tests/kit/`, …) is covered already.

## The split files

- **Rules:** `.claude/kit/RULES.md` holds the rules every project shares.
  `CLAUDE.md` imports it with `@.claude/kit/RULES.md` and adds its own. A
  session started inside a nested clone doesn't load the import; the image's
  managed-settings hook (`.devcontainer/session-place.py`) warns it.
- **Settings:** the kit's hooks, allow and deny rules are in
  `.claude/kit/settings.kit.json`; a project's additions are in
  `.claude/settings.project.json`. The builder joins them: a project adds
  rules and hooks, never changes a kit value, and an allow rule a deny rule
  covers is refused.
- **Devcontainer:** `.devcontainer/devcontainer.template.json`, with
  `{{PROJECT_NAME}}` filled from `kit.env`.

After editing any of those inputs, run `python3 tools/kit/build.py`;
`tests/kit/test_kit_build.py` fails while a generated file is stale.

## Syncing a project

In the project, `/kit-sync` (`.claude/skills/kit-sync/SKILL.md`) clones the
kit into `tmp/kit`, runs `python3 tools/kit/sync.py`, tests, and opens one PR
whose description is the sync's report. The project's `scripts/github.local.conf`
needs `helen-contains-claude-webdev` in `GH_REPOS`, with PR rights so a
project session can send a kit improvement back here.

A project with no `kit.lock` (made before the split) adopts once with
`python3 tools/kit/sync.py --adopt`, after comparing its kit files with the
kit's (`--adopt --dry-run` lists the ones that differ).

## The build stamp

`run.sh` stamps each image with a SHA-256 of its build context and build
arguments, and rebuilds when the stamp no longer matches. Files listed in
`.devcontainer/.dockerignore` (`run.sh` and the Python helpers) are outside
the stamp, so editing them doesn't rebuild. `kit.env` is listed too: its
values reach the build as arguments, which the stamp covers, so editing a
comment there costs nothing. `.dockerignore` takes exact filenames only.

## Tests

    python3 -m pytest

Claude may run `python3 -m pytest` or `python3 -m pytest -q` unasked.
Anything with more arguments asks, because `--basetemp` empties the folder
it is given.

## Adding to the allow list

Every rule in `.claude/settings.json` that ends in ` *` is listed in
`tests/kit/test_allow_list.py`, which fails on one it hasn't seen. Before
adding one, check the tool for an option that runs a program or writes a
file anywhere, and say in the commit which options you checked. A project's
own open-ended rule goes in `_reviewedOpenRules` in its
`.claude/settings.project.json`, with that note.

## Adding a hook

Each hook is one standard-library Python file, wired in
`.claude/kit/settings.kit.json` (then `python3 tools/kit/build.py`) and
listed in `.claude/hooks/README.md`, with tests under `tests/kit/`.
