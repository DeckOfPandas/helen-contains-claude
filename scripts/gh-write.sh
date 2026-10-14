#!/bin/sh
# The three GitHub writes a session makes routinely, each checked. It builds
# the `gh api` call itself and accepts nothing it does not understand, which is
# why .claude/settings.json can allow it unasked.
#
# USAGE -- the body is always a file under tmp/, written with the Write tool:
#   sh scripts/gh-write.sh pr-create <repo> <branch> "<title>" tmp/<body>.md
#   sh scripts/gh-write.sh pr-body   <repo> <number> tmp/<body>.md
#   sh scripts/gh-write.sh comment   <repo> <number> tmp/<body>.md
#
# <repo> is a bare name from GH_REPOS in scripts/github.conf. A PR's base is
# always main and its head never is. `comment` takes an issue or PR number.
#
# It cannot merge, approve, close, delete, change a title or state, or touch
# settings. Prints the login GitHub recorded, so the author is read, not assumed.
set -eu

WRAPPER=gh-write.sh
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/_github_conf.sh"
load_conf

usage="usage: sh scripts/gh-write.sh pr-create <repo> <branch> \"<title>\" tmp/<body>.md | pr-body <repo> <number> tmp/<body>.md | comment <repo> <number> tmp/<body>.md"

check_number() {
  case "$1" in
    '' | *[!0-9]* | 0*) refuse "'$1' is not an issue or PR number" ;;
  esac
}

check_branch() {
  case "$1" in
    '' | main | master | refs/* | -* | *..* | */ | *[!A-Za-z0-9._/-]*)
      refuse "'$1' is not a branch this wrapper opens a PR from (never main, no options, no owner: prefix)" ;;
  esac
}

# A body outside tmp/, or reached through `..` or a symlink, would let gh read
# and post a file from anywhere.
check_body() {
  case "$1" in
    tmp/*) ;;
    *) refuse "the body must be a file under tmp/, got '$1'" ;;
  esac
  case "$1" in
    *..* | *[!A-Za-z0-9._/-]*) refuse "'$1' is not a plain path under tmp/" ;;
  esac
  [ ! -L "$1" ] || refuse "'$1' is a symlink, and a link can point outside the project"
  [ -f "$1" ] || refuse "'$1' does not exist -- write the body with the Write tool first"
}

[ "$#" -ge 1 ] || refuse "$usage"
action="$1"
shift

case "$action" in
  pr-create)
    [ "$#" -eq 4 ] || refuse "$usage"
    check_repo "$1"
    check_branch "$2"
    [ -n "$3" ] || refuse "a PR needs a title"
    check_body "$4"
    set -- sh "$here/gh-agent.sh" api --method POST "repos/$GH_OWNER/$1/pulls" \
      -f "title=$3" -f "head=$2" -f "base=main" -F "body=@$4" \
      --jq '[.number, .html_url, .user.login] | @tsv'
    ;;
  pr-body)
    [ "$#" -eq 3 ] || refuse "$usage"
    check_repo "$1"
    check_number "$2"
    check_body "$3"
    set -- sh "$here/gh-agent.sh" api --method PATCH "repos/$GH_OWNER/$1/pulls/$2" \
      -F "body=@$3" \
      --jq '[.number, .html_url, .user.login, .state] | @tsv'
    ;;
  comment)
    [ "$#" -eq 3 ] || refuse "$usage"
    check_repo "$1"
    check_number "$2"
    check_body "$3"
    set -- sh "$here/gh-agent.sh" api --method POST "repos/$GH_OWNER/$1/issues/$2/comments" \
      -F "body=@$3" \
      --jq '[.html_url, .user.login] | @tsv'
    ;;
  *)
    refuse "'$action' is not a write this wrapper makes. $usage"
    ;;
esac

run_or_print "$@"
