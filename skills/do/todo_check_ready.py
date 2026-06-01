#!/usr/bin/env python3
"""todo_check_ready.py - decide whether a project's docs/TODO.md is "ready".

Run ~daily from cron. When the task list has accumulated enough work and its
content changed since the last notification, build a message and send it via
the bundled ``telegram-send`` CLI so the user can open Claude and run
``/ralphex:ralphex-adopt docs/TODO.md``.

Stdlib only (no venv, no deps) so cron has zero install friction.

Configuration (all via environment, with defaults):
  DO_TODO_PATH       relative path to the task list      (docs/TODO.md)
  DO_PROJECT_DIR     project root                        (git root or cwd)
  DO_MIN_TASKS       readiness threshold                 (3)
  DO_STATE_DIR       debounce state directory            (~/.cache/ai-slash-commands/do)
  DO_AGENT           agent to launch in opt-in mode      (codex)
  DO_LAUNCH_AGENT    spawn $DO_AGENT with /do when ready  (0)

Exit codes:
  0  ran successfully (whether or not a notification was sent)
  1  could not send the notification
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        root = out.stdout.strip()
        return Path(root) if root else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def default_project_dir() -> Path:
    cwd = Path.cwd()
    return _git_root(cwd) or cwd


def default_state_dir() -> Path:
    return Path.home() / ".cache" / "ai-slash-commands" / "do"


# ---------------------------------------------------------------------------
# Readiness heuristics (pure functions)
# ---------------------------------------------------------------------------

_LIST_ITEM = re.compile(r"^\s*[-*] (\[[ xX]\] )?\S")
_CHECKED_ITEM = re.compile(r"^\s*[-*] \[[xX]\] ")
_HEADING = re.compile(r"^#{1,3} \S")


def count_task_units(text: str) -> int:
    """Count open "task units": markdown list items plus level 1-3 headings.

    The first heading is treated as the document title and not counted.
    Completed checkbox items (``- [x]``) are work already done, so they are
    not counted — otherwise a fully-checked list would still trigger a nudge.
    """
    count = 0
    seen_title = False
    for line in text.splitlines():
        if _HEADING.match(line):
            if not seen_title:
                seen_title = True
                continue
            count += 1
        elif _LIST_ITEM.match(line):
            if _CHECKED_ITEM.match(line):
                continue
            count += 1
    return count


def is_ready(text: str, min_tasks: int) -> bool:
    """A non-empty file with at least ``min_tasks`` task units is ready."""
    if not text.strip():
        return False
    return count_task_units(text) >= min_tasks


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def project_slug(project_dir: Path) -> str:
    """Stable filesystem-safe slug for a project path."""
    raw = str(Path(project_dir).resolve())
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", raw).strip("-")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{safe[-40:]}-{digest}" if safe else digest


# ---------------------------------------------------------------------------
# Debounce / state
# ---------------------------------------------------------------------------


def state_path(state_dir: Path, project_dir: Path) -> Path:
    return Path(state_dir) / f"{project_slug(project_dir)}.json"


def load_state(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_state(path: Path, hash_: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"hash": hash_, "notified_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def should_notify(text: str, state: dict) -> bool:
    """Notify only when the content changed since the last notification."""
    return content_hash(text) != state.get("hash")


def plan_already_exists(project_dir: Path) -> bool:
    """Skip notifying if a ralphex plan already exists under docs/plans/."""
    plans = Path(project_dir) / "docs" / "plans"
    if not plans.is_dir():
        return False
    for entry in plans.iterdir():
        if entry.is_file() and entry.suffix == ".md":
            return True
    return False


# ---------------------------------------------------------------------------
# Message building
# ---------------------------------------------------------------------------

ADOPT_PROMPT = "/ralphex:ralphex-adopt docs/TODO.md"


def build_message(project_dir: Path, todo_path: Path) -> str:
    project_abs = str(Path(project_dir).resolve())
    text = todo_path.read_text(encoding="utf-8") if Path(todo_path).exists() else ""
    n = count_task_units(text)
    # Reflect the configured task-list path (DO_TODO_PATH) in the command/URL/text
    # rather than a hardcoded docs/TODO.md, so a custom path points the user at
    # the file that was actually evaluated.
    try:
        rel_todo = (
            Path(todo_path).resolve().relative_to(Path(project_dir).resolve()).as_posix()
        )
    except ValueError:
        rel_todo = Path(todo_path).name
    adopt_prompt = f"/ralphex:ralphex-adopt {rel_todo}"
    # Single-quote the copy-paste command so a project path or task-list path
    # containing shell metacharacters ($, backticks, $()) is pasted literally
    # rather than expanded/executed by the user's shell.
    command = f"cd {shlex.quote(project_abs)} && claude {shlex.quote(adopt_prompt)}"
    # The message is sent as plain text (see send_telegram's parse_mode=""), so
    # the path/command fields cannot open an unbalanced Telegram Markdown entity
    # — a literal `_`, `*`, backtick, or `[` in the project or task-list path
    # would otherwise corrupt or drop the nudge. quote() already yields a valid
    # URL; no Markdown-specific encoding is needed.
    cwd_q = quote(project_abs, safe="")
    prompt_q = quote(adopt_prompt, safe="")
    url = (
        "claude-code://open"
        f"?cwd={cwd_q}"
        f"&prompt={prompt_q}"
    )
    return (
        f"📋 TODO ready — {n} task units queued in {rel_todo}.\n\n"
        f"Open & adopt:\n{command}\n\n"
        f"Or: {url}\n\n"
        f"After the adopt plan is approved, run /ralphex:ralphex.\n"
        f"Task-list edits commit with the todo: prefix."
    )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def bundled_telegram_send() -> Path:
    """Path to the telegram-send wrapper shipped next to this script."""
    return Path(__file__).resolve().parent / "telegram-send"


def default_local_bin() -> Path:
    return Path.home() / ".local" / "bin"


def ensure_telegram_send(local_bin: Path | None = None) -> str | None:
    """Resolve telegram-send, self-healing onto PATH when missing.

    Resolution order:
      1. an existing ``telegram-send`` on PATH;
      2. otherwise symlink the bundled copy into ``local_bin`` (default
         ``~/.local/bin``), creating the dir and making the target executable,
         and return that link so future runs find it on PATH;
      3. fall back to the bundled copy directly if linking is not possible.
    """
    from shutil import which

    found = which("telegram-send")
    if found:
        return found

    bundled = bundled_telegram_send()
    if not bundled.exists():
        return None

    # Make sure the bundled script itself is executable.
    try:
        mode = bundled.stat().st_mode
        os.chmod(bundled, mode | 0o111)
    except OSError:
        pass

    target_dir = Path(local_bin) if local_bin is not None else default_local_bin()
    link = target_dir / "telegram-send"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            # Refresh a stale/foreign entry only if it is our symlink.
            if link.is_symlink():
                link.unlink()
            else:
                return str(link)
        link.symlink_to(bundled)
        return str(link)
    except OSError:
        return str(bundled)


def send_telegram(message: str, sender=None) -> bool:
    """Send ``message`` via telegram-send. ``sender`` is injectable for tests."""
    if sender is not None:
        return bool(sender(message))
    exe = ensure_telegram_send()
    if not exe:
        print("todo_check_ready: telegram-send not found", file=sys.stderr)
        return False
    try:
        # Send as plain text (empty parse_mode) so a project/TODO path with
        # Telegram Markdown metacharacters (_ * ` [) cannot open an unbalanced
        # entity and make the Bot API reject the whole message. ``--`` keeps the
        # message from being parsed as an option.
        subprocess.run([exe, "--parse-mode", "", "--", message], check=True)
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"todo_check_ready: telegram-send failed: {exc}", file=sys.stderr)
        return False


def launch_agent(agent: str, project_dir: Path) -> None:
    """Opt-in: spawn the agent with a /do prompt (non-blocking)."""
    try:
        subprocess.Popen(
            [agent, "/do"],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"todo_check_ready: could not launch {agent}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(config: dict, sender=None) -> dict:
    """Evaluate readiness and notify. Returns a result dict for tests/logging."""
    project_dir = Path(config["project_dir"])
    todo_path = project_dir / config["todo_path"]
    result = {"ready": False, "notified": False, "message": None, "reason": ""}

    if not todo_path.exists():
        result["reason"] = "todo-missing"
        return result
    text = todo_path.read_text(encoding="utf-8")

    if not is_ready(text, config["min_tasks"]):
        result["reason"] = "not-ready"
        return result
    result["ready"] = True

    if plan_already_exists(project_dir):
        result["reason"] = "plan-exists"
        return result

    state = load_state(state_path(config["state_dir"], project_dir))
    if not should_notify(text, state):
        result["reason"] = "unchanged"
        return result

    message = build_message(project_dir, todo_path)
    result["message"] = message

    if config.get("dry_run"):
        result["reason"] = "dry-run"
        return result

    if send_telegram(message, sender=sender):
        save_state(state_path(config["state_dir"], project_dir), content_hash(text))
        result["notified"] = True
        result["reason"] = "notified"
        if config.get("launch_agent"):
            launch_agent(config["agent"], project_dir)
    else:
        result["reason"] = "send-failed"
    return result


def config_from_env() -> dict:
    project_dir = os.environ.get("DO_PROJECT_DIR") or str(default_project_dir())
    state_dir = os.environ.get("DO_STATE_DIR") or str(default_state_dir())
    return {
        "todo_path": os.environ.get("DO_TODO_PATH", "docs/TODO.md"),
        "project_dir": project_dir,
        "min_tasks": int(os.environ.get("DO_MIN_TASKS", "3")),
        "state_dir": state_dir,
        "agent": os.environ.get("DO_AGENT", "codex"),
        "launch_agent": os.environ.get("DO_LAUNCH_AGENT", "0") == "1",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check whether docs/TODO.md is ready.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="evaluate and print the message instead of sending it",
    )
    args = parser.parse_args(argv)

    config = config_from_env()
    # DRY_RUN=1 in the environment must prevent sending, not merely gate the
    # print below; otherwise an operator expecting a preview would trigger a
    # real Telegram send plus state/PATH mutation.
    dry_run = args.dry_run or os.environ.get("DRY_RUN") == "1"
    config["dry_run"] = dry_run

    result = run(config)
    if result["message"] and dry_run:
        print(result["message"])
    if result["reason"] == "send-failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
