#!/bin/sh
# Tests for install-cron.sh --print: must emit a valid 5-field cron line
# that targets the given project and invokes todo_check_ready.py.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL="$SCRIPT_DIR/../install-cron.sh"
FAILED=0

fail() { echo "FAIL: $1" >&2; FAILED=1; }
pass() { echo "ok: $1"; }

PROJ="/tmp/some-project"
line="$($INSTALL --print --project "$PROJ")"

# 1. The schedule prefix is a valid 5-field cron spec.
fields="$(printf '%s\n' "$line" | awk '{print $1, $2, $3, $4, $5}')"
case "$fields" in
  *' '*' '*' '*' '*) pass "five schedule fields present" ;;
  *) fail "schedule does not have five fields: $line" ;;
esac

# Each of the five fields must be a cron token (digit, *, range, list, step).
# Disable globbing so a bare '*' field is not expanded into filenames.
set -f
i=1
for f in $(printf '%s\n' "$line" | awk '{print $1, $2, $3, $4, $5}'); do
  case "$f" in
    *[!0-9*/,-]*) fail "field $i not a cron token: '$f'" ;;
    "") fail "field $i empty" ;;
    *) : ;;
  esac
  i=$((i + 1))
  [ "$i" -gt 5 ] && break
done
set +f
[ "$FAILED" -eq 0 ] && pass "all five fields are cron tokens"

# 2. The command targets the project and the checker script.
case "$line" in
  *"$PROJ"*) pass "project dir present" ;;
  *) fail "project dir missing: $line" ;;
esac
case "$line" in
  *"todo_check_ready.py"*) pass "checker script present" ;;
  *) fail "checker script missing: $line" ;;
esac

# 3. The marker comment is present for idempotent replacement.
case "$line" in
  *"# ai-slash-commands:do $PROJ"*) pass "idempotency marker present" ;;
  *) fail "marker missing: $line" ;;
esac

# 4. --print must not produce more than one line.
n="$(printf '%s\n' "$line" | wc -l | tr -d ' ')"
[ "$n" = "1" ] && pass "single line emitted" || fail "expected one line, got $n"

# 5. A project path containing spaces must be single-quoted so the cron command
#    cd's into the right directory instead of splitting on the space.
SPACED="/tmp/space dir/proj"
sline="$($INSTALL --print --project "$SPACED")"
case "$sline" in
  *"cd '$SPACED'"*) pass "spaced project dir is quoted in cd" ;;
  *) fail "spaced project dir not quoted: $sline" ;;
esac
case "$sline" in
  *"DO_PROJECT_DIR='$SPACED'"*) pass "spaced DO_PROJECT_DIR is quoted" ;;
  *) fail "spaced DO_PROJECT_DIR not quoted: $sline" ;;
esac

# 5b. A project path containing shell metacharacters must be single-quoted so
#     it is not expanded or executed when cron re-parses the line via /bin/sh.
DANGER='/tmp/p$(touch /tmp/should-not-exist)`whoami`'
dline="$($INSTALL --print --project "$DANGER")"
case "$dline" in
  *"cd '$DANGER'"*) pass "metachar project dir is single-quoted" ;;
  *) fail "metachar project dir not single-quoted: $dline" ;;
esac

# 5c. cron treats '%' specially (newline + stdin split) before /bin/sh runs the
#     command, so single quotes cannot protect it. A '%' in the project path
#     must be backslash-escaped ('\%') in the emitted line, including the marker.
PCT='/tmp/100% done/proj'
pline="$($INSTALL --print --project "$PCT")"
case "$pline" in
  *'100\% done'*) pass "percent in path is escaped to \\%" ;;
  *) fail "percent in path not escaped: $pline" ;;
esac
case "$pline" in
  *'100% done'*) fail "unescaped percent leaked into line: $pline" ;;
  *) pass "no bare percent remains in line" ;;
esac

# 6. When TELEGRAM_* are set in the environment, they must be embedded in the
#    line so cron's minimal environment can still send the notification.
tline="$(TELEGRAM_TOKEN=tok123 TELEGRAM_CHAT_ID=42 "$INSTALL" --print --project "$PROJ" 2>/dev/null)"
case "$tline" in
  *"TELEGRAM_TOKEN='tok123'"*) pass "telegram token embedded" ;;
  *) fail "telegram token not embedded: $tline" ;;
esac
case "$tline" in
  *"TELEGRAM_CHAT_ID='42'"*) pass "telegram chat id embedded" ;;
  *) fail "telegram chat id not embedded: $tline" ;;
esac

# 7. The line must redirect output to a log file so cron does not mail stderr.
case "$line" in
  *'cron.log'*) pass "log redirect present" ;;
  *) fail "log redirect missing: $line" ;;
esac

# 8. Installing twice for the same project must be idempotent: the second run
#    replaces the existing line rather than appending a duplicate. Exercise this
#    with a '%' path, since the stored line carries the escaped '\%' marker and a
#    naive match (e.g. `awk -v`, which strips the backslash) would never match it
#    and would re-append on every run. Stub `crontab` with a file-backed fake so
#    the real user crontab is never touched.
STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$STUB_DIR"' EXIT
CRONTAB_FILE="$STUB_DIR/crontab.txt"
: > "$CRONTAB_FILE"
cat > "$STUB_DIR/crontab" <<EOF
#!/bin/sh
# Minimal crontab(1) stand-in: -l prints the file, '-' reads stdin into it.
if [ "\$1" = "-l" ]; then
  cat "$CRONTAB_FILE"
elif [ "\$1" = "-" ]; then
  cat > "$CRONTAB_FILE"
fi
EOF
chmod +x "$STUB_DIR/crontab"

PCT2='/tmp/100% done/proj'
PATH="$STUB_DIR:$PATH" "$INSTALL" --project "$PCT2" >/dev/null 2>&1
PATH="$STUB_DIR:$PATH" "$INSTALL" --project "$PCT2" >/dev/null 2>&1
dupes="$(grep -c 'ai-slash-commands:do /tmp/100\\% done/proj' "$CRONTAB_FILE" || true)"
[ "$dupes" = "1" ] && pass "install twice for % path is idempotent (one line)" \
  || fail "install twice for % path produced $dupes lines, expected 1"

if [ "$FAILED" -eq 0 ]; then
  echo "All install-cron tests passed."
  exit 0
fi
echo "install-cron tests FAILED." >&2
exit 1
