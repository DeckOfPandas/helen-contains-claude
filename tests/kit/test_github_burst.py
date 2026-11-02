"""guard-github-burst.py: what counts as a creation, and when one is refused."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from conftest import denied, run_hook

HOUR = 60 * 60
CREATE_PR = 'sh scripts/gh-write.sh pr-create site feat "Title" tmp/body.md'


@pytest.fixture
def guard(kit_root: Path) -> Path:
    return kit_root / ".claude" / "hooks" / "guard-github-burst.py"


@pytest.fixture
def config(tmp_path: Path) -> Path:
    return tmp_path / "config"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    path = tmp_path / "project"
    (path / "tmp").mkdir(parents=True)
    return path


def log_file(config: Path) -> Path:
    return config / "claude-kit" / "github-creations.log"


def seed(config: Path, *ages: float) -> None:
    """Log one past creation per age, in seconds before now."""
    log_file(config).parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    log_file(config).write_text("".join(f"{int(now - age)} issue\n" for age in ages))


def check(guard: Path, project: Path, config: Path, command: str) -> dict | None:
    return run_hook(guard, command, project, {"CLAUDE_CONFIG_DIR": str(config)})


def logged(config: Path) -> int:
    path = log_file(config)
    return len(path.read_text().splitlines()) if path.exists() else 0


@pytest.mark.parametrize("command", [
    CREATE_PR,
    'sh scripts/gh-write.sh issue-create site "Title" tmp/body.md bug',
    'sh scripts/gh-agent.sh issue create --repo o/site --title x --body-file tmp/b.md',
    "sh scripts/gh-agent.sh pr create --base main --head feat",
    "gh issue create --title x",
    "gh pr create",
    "gh api --method POST repos/o/site/issues -f title=x",
    "gh api repos/o/site/pulls -X POST -f title=x",
    "sh scripts/gh-agent.sh api --method=POST repos/o/site/pulls",
])
def test_each_form_of_creation_is_counted(guard, project, config, command):
    assert not denied(check(guard, project, config, command))
    assert logged(config) == 1


@pytest.mark.parametrize("command", [
    "sh scripts/gh-write.sh comment site 12 tmp/body.md",
    "sh scripts/gh-write.sh pr-body site 12 tmp/body.md",
    "sh scripts/gh-write.sh issue-label site 12 bug",
    "sh scripts/gh-read.sh repos/o/site/pulls --each number,title",
    "sh scripts/gh-agent.sh issue list --repo o/site",
    "sh scripts/gh-agent.sh pr view 12",
    "gh api repos/o/site/issues",
    "gh api --method POST repos/o/site/issues/12/comments -f body=x",
    "git status",
])
def test_other_github_calls_are_not_counted(guard, project, config, command):
    seed(config, *[60] * 20)
    assert not denied(check(guard, project, config, command))
    assert logged(config) == 20


def test_the_fourth_creation_in_an_hour_is_refused(guard, project, config):
    for _ in range(3):
        assert not denied(check(guard, project, config, CREATE_PR))
    verdict = check(guard, project, config, CREATE_PR)
    assert denied(verdict)
    reason = verdict["hookSpecificOutput"]["permissionDecisionReason"]
    assert "checklist" in reason and "minute" in reason, reason
    assert logged(config) == 3, "a refused creation must not be counted"


def test_creations_older_than_an_hour_leave_the_hourly_count(guard, project, config):
    seed(config, HOUR + 60, HOUR + 120, HOUR + 180)
    assert not denied(check(guard, project, config, CREATE_PR))


def test_the_eleventh_creation_in_a_day_is_refused(guard, project, config):
    seed(config, *[2 * HOUR + n * 60 for n in range(10)])
    verdict = check(guard, project, config, CREATE_PR)
    assert denied(verdict)
    assert "24 hours" in verdict["hookSpecificOutput"]["permissionDecisionReason"]


def test_creations_older_than_a_day_are_forgotten(guard, project, config):
    seed(config, *[25 * HOUR] * 30)
    assert not denied(check(guard, project, config, CREATE_PR))
    assert logged(config) == 1


def test_an_unreadable_log_line_is_dropped(guard, project, config):
    log_file(config).parent.mkdir(parents=True)
    log_file(config).write_text("not a stamp\n\n")
    assert not denied(check(guard, project, config, CREATE_PR))
    assert logged(config) == 1


def test_two_creations_in_one_command_count_twice(guard, project, config):
    seed(config, 60, 120)
    assert denied(check(guard, project, config, f"{CREATE_PR}; gh issue create"))


@pytest.mark.parametrize("body", [
    'sh scripts/gh-write.sh issue-create site "One" tmp/one.md\n',
    "for t in a b c; do\n  gh issue create --title $t\ndone\n",
])
def test_a_creation_inside_a_script_is_refused(guard, project, config, body):
    (project / "tmp" / "make.sh").write_text(body)
    verdict = check(guard, project, config, "sh tmp/make.sh")
    assert denied(verdict)
    assert "direct call" in verdict["hookSpecificOutput"]["permissionDecisionReason"]
    assert logged(config) == 0


def test_a_script_without_creations_passes(guard, project, config):
    (project / "tmp" / "list.sh").write_text("sh scripts/gh-agent.sh issue list\n")
    assert not denied(check(guard, project, config, "sh tmp/list.sh"))


def test_the_wrappers_own_source_is_not_read_as_a_script(guard, kit_root, config):
    assert not denied(check(guard, kit_root, config, CREATE_PR))
    assert logged(config) == 1


def test_a_log_that_cannot_be_written_refuses_the_creation(guard, project, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    verdict = check(guard, project, blocker, CREATE_PR)
    assert denied(verdict)


def test_it_is_wired_into_settings_ungated(kit_root):
    settings = json.loads((kit_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    wired = [
        hook
        for entry in settings["hooks"]["PreToolUse"]
        if entry.get("matcher") == "Bash"
        for hook in entry["hooks"]
        if hook["command"].endswith('/.claude/hooks/guard-github-burst.py"')
    ]
    assert wired, "guard-github-burst.py exists but no PreToolUse hook runs it"
    # A creation need not start the command (`sh scripts/gh-write.sh ...`),
    # and an `if` is a prefix match.
    assert "if" not in wired[0]
