#!/usr/bin/env bash
# do statusline_block — a ccstatusline Custom Command.
#   Renders docs/TODO.md checkbox progress as a compact block:
#     plain:  ☑ 3/8
#     split:  ☑ 7/23 week │ 48 week+
# Zero deps (jq used if present, else grepped). Reads Claude Code's status JSON on stdin
# (ccstatusline forwards it), the same way claude-statusline-todo's statusline.cjs does.
# A faithful bash port of that script's tasks block (tasksSegment/splitSections/splitRender).
#
# Config via env (all optional):
#   STATUSLINE_TODO           TODO file, relative to cwd unless absolute (default docs/TODO.md)
#   STATUSLINE_TODO_SPLIT     on by default; 0|off|false → never split, always plain done/total
#   STATUSLINE_TODO_TOPLEVEL  on by default; 0|off|false → count indented sub-tasks too

# --- config (env, all optional) ---
TODO_REL="${STATUSLINE_TODO:-docs/TODO.md}"

is_off() { # 0|off|false (case-insensitive) → true (these opt-out of an on-by-default flag)
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    0 | off | false) return 0 ;;
    *) return 1 ;;
  esac
}

# --- no color: render plain text (all ANSI vars empty) ---
R=''
DIM=''
GREEN=''
CYAN=''
EMOJI='☑'

# --- stdin: Claude Code status JSON (forwarded by ccstatusline) → cwd ---
# Read stdin only when it's piped; a bare terminal run has no JSON, so don't block on cat —
# fall through to $PWD instead.
input=""
[ -t 0 ] || input="$(cat)"
cwd=""
if command -v jq >/dev/null 2>&1; then
  cwd="$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty' 2>/dev/null)"
fi
if [ -z "$cwd" ]; then # grep fallback: "current_dir":"…", then "cwd":"…"
  cwd="$(printf '%s' "$input" | grep -oE '"current_dir"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"current_dir"[[:space:]]*:[[:space:]]*"//; s/"$//')"
fi
if [ -z "$cwd" ]; then
  cwd="$(printf '%s' "$input" | grep -oE '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
fi
[ -z "$cwd" ] && cwd="$PWD"

# --- resolve TODO path ---
case "$TODO_REL" in
  /*) todo_path="$TODO_REL" ;;
  *) todo_path="$cwd/$TODO_REL" ;;
esac
[ -f "$todo_path" ] || exit 0 # no file → no segment

# --- checkbox / header regexes (mirror statusline.cjs) ---
# STATUSLINE_TODO_TOPLEVEL (on by default) → col-0 only (drop the leading-indent prefix).
if is_off "$STATUSLINE_TODO_TOPLEVEL"; then INDENT="[[:blank:]]*"; else INDENT=""; fi
done_re="^${INDENT}[-*][[:space:]]+\[[xX]\]"
todo_re="^${INDENT}[-*][[:space:]]+\[ \]"
h1_re="^#[[:space:]]+(.+)$" # top-level header only (a single leading `#`)

# --- split by `# ` header into label/done/todo, dropping empty sections ---
sec_label=()
sec_done=()
sec_todo=()
split_sections() {
  sec_label=()
  sec_done=()
  sec_todo=()
  local cur=-1 line label isdone
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ $line =~ $h1_re ]]; then
      label="${BASH_REMATCH[1]}"
      label="${label%"${label##*[![:space:]]}"}" # trim trailing whitespace
      label="${label%:}"                         # trim a trailing colon
      label="$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]')"
      sec_label+=("$label")
      sec_done+=(0)
      sec_todo+=(0)
      cur=$((${#sec_label[@]} - 1))
      continue
    fi
    isdone=0
    [[ $line =~ $done_re ]] && isdone=1
    if [ $isdone -eq 0 ] && ! [[ $line =~ $todo_re ]]; then continue; fi
    if [ $cur -lt 0 ]; then # checkboxes before any header → unlabeled lead section
      sec_label+=("")
      sec_done+=(0)
      sec_todo+=(0)
      cur=0
    fi
    if [ $isdone -eq 1 ]; then
      sec_done[cur]=$((${sec_done[cur]} + 1))
    else
      sec_todo[cur]=$((${sec_todo[cur]} + 1))
    fi
  done <"$todo_path"

  local -a l=() d=() t=() # filter sections with no checkboxes
  local i
  for i in "${!sec_label[@]}"; do
    if [ $((${sec_done[i]} + ${sec_todo[i]})) -gt 0 ]; then
      l+=("${sec_label[i]}")
      d+=("${sec_done[i]}")
      t+=("${sec_todo[i]}")
    fi
  done
  sec_label=("${l[@]}")
  sec_done=("${d[@]}")
  sec_todo=("${t[@]}")
}

# lead `done/total label`; each later section adds its open count (cyan).
split_render() {
  local sep=" ${DIM}│${R} "
  local ld=${sec_done[0]} lt=${sec_todo[0]} llabel="${sec_label[0]}"
  local total=$((ld + lt))
  local out="${EMOJI} ${GREEN}${ld}/${total}${R}"
  [ -n "$llabel" ] && out+=" ${DIM}${llabel}${R}"
  local i
  for i in "${!sec_label[@]}"; do
    [ "$i" -eq 0 ] && continue
    out+="${sep}${CYAN}${sec_todo[i]}"
    [ -n "${sec_label[i]}" ] && out+=" ${sec_label[i]}"
    out+="${R}"
  done
  printf '%s' "$out"
}

# --- render: split (on by default) when 2+ sections exist, else plain done/total ---
if ! is_off "$STATUSLINE_TODO_SPLIT"; then
  split_sections
  if [ ${#sec_label[@]} -ge 2 ]; then
    split_render
    exit 0
  fi
fi

done_ct="$(grep -cE "$done_re" "$todo_path" || true)"
todo_ct="$(grep -cE "$todo_re" "$todo_path" || true)"
total=$((done_ct + todo_ct))
[ "$total" -eq 0 ] && exit 0 # no checkboxes → no segment
printf '%s' "${EMOJI} ${GREEN}${done_ct}/${total}${R}"
