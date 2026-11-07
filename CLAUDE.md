# Claude Code Rules for helen-contains-claude-webdev (the kit)

@.claude/kit/RULES.md

## This repo is the kit
- Projects are synced from it: `kit/manifest` says who owns each path. A file
  marked `kit` is edited here and nowhere else; a `project` file here is only
  this repo's own copy, and new projects get theirs from the template the
  manifest names. Every tracked file is in the manifest, and
  `tests/kit/test_kit_manifest.py` fails on one that isn't.
- **Committed copies stay placeholders** (`PROJECT_NAME=changeme`,
  `your-org`, `<PROJECT>`): what this repo commits is what a project starts
  from. Local values go in the gitignored files `docs/maintaining-the-kit.md`
  lists.
- Build / test: `python3 tools/kit/build.py`, then `python3 -m pytest`.
