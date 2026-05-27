#!/bin/sh
# install-cron.sh - install (or print) a ~daily crontab line that runs
# todo_check_ready.py for the current project.
#
# Usage:
#   install-cron.sh             # install the line for $PWD (idempotent)
#   install-cron.sh --print     # just print the line, do not touch crontab
#   install-cron.sh --project /path/to/proj   # target a specific project
#
# The line is tagged with a marker comment that embeds the project dir so it
# can be matched and replaced idempotently across runs.
set -eu

PRINT_ONLY=0
PROJECT_DIR="$PWD"

# POSIX single-quote escaping: wrap a value in single quotes, turning any
# embedded ' into '\''. The cron line is re-parsed by /bin/sh when cron runs
# it, so double quotes would let $, backticks, and $() in a project path expand
# (or execute) at run time. Single quotes are the only fully literal shell
# quoting, so generated paths/env values point exactly where intended.
sq() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

# cron treats '%' specially in the command field: it turns the first unescaped
# '%' into a newline and feeds everything after it to the command on stdin.
# This happens *before* /bin/sh sees the line, so single quotes do NOT protect
# it. Escape every '%' as '\%' in the command text cron stores and runs.
esc_pct() {
  printf '%s' "$1" | sed 's/%/\\%/g'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --print) PRINT_ONLY=1; shift ;;
    --project)
      [ $# -ge 2 ] || { echo "install-cron.sh: --project needs a value" >&2; exit 2; }
      PROJECT_DIR="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *)
      echo "install-cron.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Resolve to an absolute path.
PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECKER="$SCRIPT_DIR/todo_check_ready.py"

# Prefer python3, fall back to python.
PYTHON="$(command -v python3 || command -v python || echo python3)"

# Marker keys this line to the project so re-runs replace rather than duplicate.
MARKER="# ai-slash-commands:do ${PROJECT_DIR}"

# Log directory mirrors the checker's default state dir.
LOG_DIR="${DO_STATE_DIR:-$HOME/.cache/ai-slash-commands/do}"
LOG_FILE="${LOG_DIR}/cron.log"

# cron runs with a minimal environment that does not inherit the shell's
# TELEGRAM_* vars, so embed them into the line when they are set at install
# time. Without them the checker can never send the nudge it exists to send.
ENV_PREFIX="DO_PROJECT_DIR=$(sq "${PROJECT_DIR}")"
if [ -n "${TELEGRAM_TOKEN:-}" ]; then
  ENV_PREFIX="TELEGRAM_TOKEN=$(sq "${TELEGRAM_TOKEN}") ${ENV_PREFIX}"
fi
if [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  ENV_PREFIX="TELEGRAM_CHAT_ID=$(sq "${TELEGRAM_CHAT_ID}") ${ENV_PREFIX}"
fi
if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "install-cron.sh: warning: TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not set in" \
       "the current environment, so the cron line will not be able to send a" \
       "notification. Re-run with them exported, or edit the crontab line to" \
       "add them." >&2
fi

# ~daily: 09:17 every day (minute chosen off the :00/:30 mark).
SCHEDULE="17 9 * * *"
# Escape '%' across the whole command portion (the schedule fields never
# contain one) so a project/log path like /tmp/100% done survives cron parsing.
CRON_LINE="$(esc_pct "${SCHEDULE} cd $(sq "${PROJECT_DIR}") && ${ENV_PREFIX} $(sq "${PYTHON}") $(sq "${CHECKER}") >> $(sq "${LOG_FILE}") 2>&1 ${MARKER}")"

if [ "$PRINT_ONLY" -eq 1 ]; then
  echo "$CRON_LINE"
  exit 0
fi

# The redirect appends to LOG_FILE, so its directory must exist before cron
# runs the line, otherwise the whole command fails before the checker starts.
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Idempotent install: drop any existing line for this project, then append.
# Match the marker as an exact line *suffix* (not a substring): a plain
# substring match would treat "...do /tmp/proj" as present in a sibling line
# "...do /tmp/proj-extra" and wipe out that other project's cron entry.
# Match against the escaped marker: the stored line carries '\%' wherever the
# project path had '%', so the raw MARKER would not match it.
# Pass the marker through the environment (ENVIRON), not `awk -v`: the latter
# runs C-style escape processing on the value, turning the '\%' we need to match
# back into a plain '%', which would never match the stored '\%' line and so
# would re-append a duplicate on every install for a '%' path.
MARKER_MATCH="$(esc_pct "$MARKER")"
EXISTING="$(crontab -l 2>/dev/null || true)"
NEW="$(printf '%s\n' "$EXISTING" | MARKER_MATCH="$MARKER_MATCH" awk \
  'BEGIN { m = ENVIRON["MARKER_MATCH"] }
   length($0) < length(m) || substr($0, length($0) - length(m) + 1) != m' || true)"
{
  printf '%s\n' "$NEW" | sed '/^$/d'
  printf '%s\n' "$CRON_LINE"
} | crontab -

echo "Installed daily TODO check for ${PROJECT_DIR}:"
echo "  $CRON_LINE"
