"""The scripts/ GitHub wrappers: what each accepts and refuses, in dry-run mode.

Each test runs against a copy of scripts/ with its own github.conf, so the
shipped placeholder config is never edited and nothing touches the network.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

CONF = """\
# test config
GH_OWNER=acme
GH_REPOS="site drafts"   # first is the default
GH_AGENT_USER=acme-bot

MAIN_PUSH_REPOS=drafts
"""


@pytest.fixture
def project(tmp_path: Path, kit_root: Path) -> Path:
    shutil.copytree(kit_root / "scripts", tmp_path / "scripts")
    (tmp_path / "scripts" / "github.conf").write_text(CONF)
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "body.md").write_text("hello\n")
    return tmp_path


def run(project: Path, script: str, *args: str, conf: str | None = None):
    if conf is not None:
        (project / "scripts" / "github.conf").write_text(conf)
    return subprocess.run(
        ["sh", f"scripts/{script}", *args],
        cwd=project, capture_output=True, text=True, timeout=30,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "AGENT_WRAPPER_DRY_RUN": "1",
             "AGENT_GH_TOKEN": "not-a-real-token"},
    )


def ok(result) -> list[str]:
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def refused(result) -> bool:
    return result.returncode == 2 and "refused" in result.stderr


# --- push ---------------------------------------------------------------

def test_push_a_branch_to_the_default_repo(project):
    out = ok(run(project, "git-push-agent.sh", "feat:feat"))
    assert "https://github.com/acme/site.git" in out
    assert out[-1] == "feat:feat"
    assert any("git-credential-agent-token.sh" in line for line in out)


@pytest.mark.parametrize("refspec", ["feat:main", "+feat:main", "feat:refs/heads/main",
                                     ":main", "feat:heads/main", "feat:master"])
def test_push_to_main_is_refused(project, refspec):
    assert refused(run(project, "git-push-agent.sh", refspec))


def test_push_to_main_allowed_for_main_push_repos(project):
    out = ok(run(project, "git-push-agent.sh", "feat:main", "drafts", "sub"))
    assert "https://github.com/acme/drafts.git" in out


@pytest.mark.parametrize("args", [["feat"], ["HEAD"], ["-f:x"], ["feat:feat", "other"],
                                  ["feat:feat", "site", "/etc"], ["feat:feat", "site", "../x"],
                                  ["feat:feat", "site", "-C"], ["a:a", "site", ".", "extra"]])
def test_push_refusals(project, args):
    assert refused(run(project, "git-push-agent.sh", *args))


# --- clone / fetch ------------------------------------------------------------

def test_clone(project):
    out = ok(run(project, "git-clone-agent.sh", "drafts", "_drafts"))
    assert out[-2:] == ["https://github.com/acme/drafts.git", "_drafts"]


@pytest.mark.parametrize("args", [["other"], ["site", "/abs"], ["site", "d", "--template=x"]])
def test_clone_refusals(project, args):
    assert refused(run(project, "git-clone-agent.sh", *args))


def test_fetch_agent(project):
    out = ok(run(project, "git-fetch-agent.sh", "_drafts", "drafts", "topic"))
    assert out[-1] == "+refs/heads/topic:refs/remotes/origin/topic"


@pytest.mark.parametrize("args", [["/x", "drafts"], ["d", "nope"], ["d", "drafts", "-x"],
                                  ["d", "drafts", "a:b"], ["d", "drafts", "main", "--nope"]])
def test_fetch_agent_refusals(project, args):
    assert refused(run(project, "git-fetch-agent.sh", *args))


def test_fetch_main_uses_the_default_repo(project):
    out = ok(run(project, "git-fetch-main.sh"))
    assert "https://github.com/acme/site.git" in out
    assert refused(run(project, "git-fetch-main.sh", "--upload-pack=x"))


# --- gh-read --------------------------------------------------------------------

def test_read_fields(project):
    out = ok(run(project, "gh-read.sh", "repos/acme/site/pulls/3", "--fields", "state,user.login"))
    assert out[-2:] == ["--jq", "[.state, .user.login] | @tsv"]
    assert "GET" in out


def test_read_each_and_query_string(project):
    out = ok(run(project, "gh-read.sh", "repos/acme/drafts/pulls?state=all", "--each", "number"))
    assert out[-1] == ".[] | [.number] | @tsv"


@pytest.mark.parametrize("args", [
    ["repos/other/site/pulls"], ["repos/acme/nope"], ["repos/acme/site/../x"],
    ["repos/acme/sitex"], ["repos/acme/site", "-X", "POST"], ["repos/acme/site", "-f", "a=b"],
    ["repos/acme/site", "--jq", "env"], ["repos/acme/site", "--jq", "$ENV.X"],
    ["repos/acme/site", "--fields", "a|b"], ["repos/acme/site", "--fields", "a", "--jq", "."],
])
def test_read_refusals(project, args):
    assert refused(run(project, "gh-read.sh", *args))


# --- gh-write -------------------------------------------------------------------

def test_pr_create(project):
    out = ok(run(project, "gh-write.sh", "pr-create", "site", "feat/x", "Title", "tmp/body.md"))
    assert "repos/acme/site/pulls" in out and "base=main" in out and "head=feat/x" in out


@pytest.mark.parametrize("args", [
    ["pr-create", "site", "main", "T", "tmp/body.md"],
    ["pr-create", "site", "owner:feat", "T", "tmp/body.md"],
    ["pr-create", "other", "feat", "T", "tmp/body.md"],
    ["pr-create", "site", "feat", "", "tmp/body.md"],
    ["pr-create", "site", "feat", "T", "body.md"],
    ["pr-create", "site", "feat", "T", "tmp/../scripts/github.conf"],
    ["pr-create", "site", "feat", "T", "tmp/missing.md"],
    ["comment", "site", "01", "tmp/body.md"],
    ["merge", "site", "1"],
])
def test_write_refusals(project, args):
    assert refused(run(project, "gh-write.sh", *args))


def test_comment(project):
    out = ok(run(project, "gh-write.sh", "comment", "drafts", "12", "tmp/body.md"))
    assert "repos/acme/drafts/issues/12/comments" in out


# --- public status --------------------------------------------------------------

@pytest.mark.parametrize("url", ["https://github.com/acme/site/pull/1", "https://github.com/acme-bot"])
def test_public_status_ok(project, url):
    assert ok(run(project, "github-public-status.sh", url))[-1] == url


@pytest.mark.parametrize("url", ["https://github.com/other", "https://github.com/acme@evil.com",
                                 "http://github.com/acme", "https://github.com/acmex"])
def test_public_status_refusals(project, url):
    assert refused(run(project, "github-public-status.sh", url))


# --- config parsing ---------------------------------------------------------------

@pytest.mark.parametrize("conf", [
    "GH_OWNER=your-org\nGH_REPOS=a\nGH_AGENT_USER=b\n",           # placeholder
    "GH_OWNER=acme\nGH_REPOS=a\nGH_AGENT_USER=b\nSURPRISE=1\n",   # unknown key
    "GH_OWNER=acme\nGH_REPOS=a\nGH_AGENT_USER=b\nMAIN_PUSH_REPOS=z\n",
    "GH_OWNER=acme\nGH_REPOS=\"a b;rm\"\nGH_AGENT_USER=b\n",
    "GH_OWNER=$(id)\nGH_REPOS=a\nGH_AGENT_USER=b\n",
    "GH_OWNER=acme\nGH_REPOS=\nGH_AGENT_USER=b\n",
])
def test_bad_config_is_refused(project, conf):
    assert refused(run(project, "git-fetch-main.sh", conf=conf))


def test_shipped_config_is_the_placeholder(kit_root, project):
    shipped = (kit_root / "scripts" / "github.conf").read_text()
    result = run(project, "git-fetch-main.sh", conf=shipped)
    assert refused(result) and "placeholder" in result.stderr


def test_credential_helper(project):
    done = subprocess.run(
        ["sh", str(project / "scripts" / "git-credential-agent-token.sh"), "get"],
        cwd=project, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "AGENT_GH_TOKEN": "not-a-real-token"},
    )
    assert done.stdout.splitlines() == ["username=acme-bot", "password=not-a-real-token"]
    store = subprocess.run(
        ["sh", str(project / "scripts" / "git-credential-agent-token.sh"), "store"],
        cwd=project, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    assert store.stdout == ""
