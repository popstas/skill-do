#!/bin/sh
# Tests for telegram-send. Uses DRY_RUN as the primary seam plus a fake curl
# on PATH to confirm the real path invokes curl with the expected request.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEND="$SCRIPT_DIR/../telegram-send"
FAILED=0

fail() {
  echo "FAIL: $1" >&2
  FAILED=1
}

pass() {
  echo "ok: $1"
}

# 1. DRY_RUN builds the correct URL, chat_id and text.
out="$(DRY_RUN=1 TELEGRAM_TOKEN=abc123 TELEGRAM_CHAT_ID=42 "$SEND" "hello world")"
case "$out" in
  *"url=https://api.telegram.org/botabc123/sendMessage"*) pass "url built" ;;
  *) fail "url missing/incorrect: $out" ;;
esac
case "$out" in
  *"chat_id=42"*) pass "chat_id present" ;;
  *) fail "chat_id missing: $out" ;;
esac
case "$out" in
  *"text=hello world"*) pass "text present" ;;
  *) fail "text missing: $out" ;;
esac

# 2. --chat / --token overrides win over env.
out="$(DRY_RUN=1 TELEGRAM_TOKEN=envtok TELEGRAM_CHAT_ID=99 "$SEND" --chat 7 --token clitok "hi")"
case "$out" in
  *"botclitok"*) pass "--token override" ;;
  *) fail "--token override ignored: $out" ;;
esac
case "$out" in
  *"chat_id=7"*) pass "--chat override" ;;
  *) fail "--chat override ignored: $out" ;;
esac

# 3. Text from stdin.
out="$(printf 'piped msg' | DRY_RUN=1 TELEGRAM_TOKEN=t TELEGRAM_CHAT_ID=1 "$SEND")"
case "$out" in
  *"text=piped msg"*) pass "stdin text" ;;
  *) fail "stdin text missing: $out" ;;
esac

# 4. Missing token exits 2.
set +e
TELEGRAM_TOKEN="" TELEGRAM_CHAT_ID=1 "$SEND" "x" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" -eq 2 ] && pass "exit 2 on missing token" || fail "expected exit 2 on missing token, got $rc"

# 5. Missing chat exits 2.
set +e
TELEGRAM_TOKEN=t TELEGRAM_CHAT_ID="" "$SEND" "x" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" -eq 2 ] && pass "exit 2 on missing chat" || fail "expected exit 2 on missing chat, got $rc"

# 6. Real path invokes curl (faked) with the URL.
TMPBIN="$(mktemp -d)"
cat > "$TMPBIN/curl" <<'EOF'
#!/bin/sh
echo "$@" > "$FAKE_CURL_LOG"
exit 0
EOF
chmod +x "$TMPBIN/curl"
LOG="$(mktemp)"
FAKE_CURL_LOG="$LOG" PATH="$TMPBIN:$PATH" TELEGRAM_TOKEN=rt TELEGRAM_CHAT_ID=55 "$SEND" "real" >/dev/null 2>&1
if grep -q "botrt/sendMessage" "$LOG" && grep -q "chat_id=55" "$LOG"; then
  pass "curl invoked with url+chat"
else
  fail "curl args wrong: $(cat "$LOG")"
fi
rm -rf "$TMPBIN" "$LOG"

if [ "$FAILED" -eq 0 ]; then
  echo "All telegram-send tests passed."
  exit 0
fi
echo "telegram-send tests FAILED." >&2
exit 1
