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
file anywhere, and say in the commit which options you checked.

## Adding a hook

Each hook is one standard-library Python file, wired in
`.claude/settings.json` and listed in `.claude/hooks/README.md`, with tests
under `tests/kit/`.
