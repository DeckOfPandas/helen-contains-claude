# Shared by the scripts/ GitHub wrappers: loads scripts/github.conf and checks
# arguments against it. Sourced, never run; the caller sets WRAPPER (its name,
# for messages) and `here` (its own directory) first.
#
# github.conf is PARSED, never sourced. Every allow rule naming a wrapper runs
# whatever these checks let through, so the config must not be able to run code
# or widen a check: unknown keys and out-of-charset values are refused.

refuse() {
  echo "$WRAPPER: refused -- $1" >&2
  exit 2
}

in_list() {
  item="$1"
  shift
  for candidate in "$@"; do
    [ "$candidate" = "$item" ] && return 0
  done
  return 1
}

# Trims and collapses whitespace, and drops quote characters.
_conf_clean() {
  set -f
  # shellcheck disable=SC2086
  set -- $(printf '%s' "$1" | tr -d "\"'")
  set +f
  printf '%s' "$*"
}

load_conf() {
  GH_OWNER=""
  GH_REPOS=""
  GH_AGENT_USER=""
  MAIN_PUSH_REPOS=""
  conf="$here/github.conf"
  [ -f "$conf" ] || refuse "$conf is missing"
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    case "$line" in
      *[!\ \	]*) ;;
      *) continue ;;
    esac
    case "$line" in
      *=*) ;;
      *) refuse "github.conf: '$line' is not KEY=value" ;;
    esac
    key="$(_conf_clean "${line%%=*}")"
    value="$(_conf_clean "${line#*=}")"
    case "$key" in
      GH_OWNER) GH_OWNER="$value" ;;
      GH_REPOS) GH_REPOS="$value" ;;
      GH_AGENT_USER) GH_AGENT_USER="$value" ;;
      MAIN_PUSH_REPOS) MAIN_PUSH_REPOS="$value" ;;
      *) refuse "github.conf: unknown key '$key'" ;;
    esac
  done < "$conf"

  case "$GH_OWNER" in
    '' | -* | *[!A-Za-z0-9-]*) refuse "github.conf: GH_OWNER '$GH_OWNER' is not a GitHub account name" ;;
    your-org) refuse "fill in scripts/github.conf first: GH_OWNER is still the placeholder" ;;
  esac
  case "$GH_AGENT_USER" in
    '' | -* | *[!A-Za-z0-9-]*) refuse "github.conf: GH_AGENT_USER '$GH_AGENT_USER' is not a GitHub account name" ;;
  esac
  [ -n "$GH_REPOS" ] || refuse "github.conf: GH_REPOS is empty"
  for repo in $GH_REPOS; do
    case "$repo" in
      -* | .* | *[!A-Za-z0-9._-]*) refuse "github.conf: '$repo' is not a repository name" ;;
    esac
  done
  # shellcheck disable=SC2086
  for repo in $MAIN_PUSH_REPOS; do
    in_list "$repo" $GH_REPOS || refuse "github.conf: MAIN_PUSH_REPOS names '$repo', which is not in GH_REPOS"
  done
  # shellcheck disable=SC2086
  set -- $GH_REPOS
  DEFAULT_REPO="$1"
}

check_repo() {
  # shellcheck disable=SC2086
  in_list "$1" $GH_REPOS || refuse "'$1' is not one of the repos in scripts/github.conf ($GH_REPOS)"
}

# A path relative to this checkout: no absolute path, no `..`, no option.
check_dir() {
  case "$1" in
    /* | *..* | -*) refuse "'$1' is outside this checkout" ;;
  esac
}

# Prints the command instead of running it, one argument per line, when
# AGENT_WRAPPER_DRY_RUN is set; tests/kit/test_wrappers.py relies on it.
run_or_print() {
  if [ -n "${AGENT_WRAPPER_DRY_RUN:-}" ]; then
    printf '%s\n' "$@"
    exit 0
  fi
  exec "$@"
}
