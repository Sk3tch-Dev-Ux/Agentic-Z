"""dayz-director-status — write/update the director's live status JSON.

Called by the dayz-director agent on every state-machine transition. The
desktop app's sidecar tails the resulting file and streams updates to the
DirectorPanel UI via SSE.

Output file: <repo>/.claude/local-memory/dayz-director-status.json

Schema:
{
  "run_id": "2026-05-04T15-32-08",
  "goal": "ship MyMod",
  "mod": "MyMod",
  "status": "running" | "done" | "halted" | "refused",
  "current_state": "BUILD",
  "transitions": [
    {"from": "IDLE", "to": "PREFLIGHT", "ts": 1735844000, "notes": ""},
    ...
  ],
  "subagent_calls": [
    {"ts": 1735844010, "agent": "dayz-coder", "mode": "audit",
     "digest": "12 findings: 3 critical..."}
  ],
  "files_changed": ["workspace/MyMod/config.cpp"],
  "skill_invocations": [
    {"ts": 1735844050, "skill": "/dayz-build-pbo", "exit": 0, "elapsed": 8.3}
  ],
  "halt_reason": null,
  "started_at": 1735844000,
  "updated_at": 1735844060
}

Atomic write: write to .tmp then os.replace() so readers never see a half-
written file.

Run (from the director agent):
  python .../write.py start --run-id <id> --goal "ship MyMod" --mod MyMod
  python .../write.py transition --from PREFLIGHT --to AUDIT --notes "OK"
  python .../write.py subagent --agent dayz-coder --mode audit --digest "..."
  python .../write.py file-changed --path workspace/MyMod/config.cpp
  python .../write.py skill --name /dayz-build-pbo --exit 0 --elapsed 8.3
  python .../write.py halt --reason "max_state_turns reached"
  python .../write.py done
  python .../write.py status         # print current JSON, exit 0
  python .../write.py reset          # clear the file (start of new run)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# Walk up to find repo root (CLAUDE.md marker)
_cur = _HERE
REPO_ROOT = None
for _ in range(8):
    if (_cur / "CLAUDE.md").exists():
        REPO_ROOT = _cur
        break
    _cur = _cur.parent
if REPO_ROOT is None:
    # Fallback: assume <repo>/.claude/skills/dayz-director-status/write.py
    REPO_ROOT = _HERE.parents[2]

STATUS_FILE = REPO_ROOT / ".claude" / "local-memory" / "dayz-director-status.json"


def _now() -> float:
    return time.time()


def _load() -> dict:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    tmp = STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATUS_FILE)


# --------- subcommands ---------


def cmd_start(args: argparse.Namespace) -> int:
    state = {
        "run_id": args.run_id or time.strftime("%Y-%m-%dT%H-%M-%S"),
        "goal": args.goal,
        "mod": args.mod,
        "status": "running",
        "current_state": "IDLE",
        "transitions": [],
        "subagent_calls": [],
        "files_changed": [],
        "skill_invocations": [],
        "halt_reason": None,
        "started_at": _now(),
    }
    _save(state)
    print(f"started run {state['run_id']}")
    return 0


def cmd_transition(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run; call `start` first", file=sys.stderr)
        return 1
    rec = {
        "from": args.from_state,
        "to": args.to_state,
        "ts": _now(),
        "notes": args.notes or "",
    }
    state.setdefault("transitions", []).append(rec)
    state["current_state"] = args.to_state
    _save(state)
    return 0


def cmd_subagent(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run", file=sys.stderr)
        return 1
    state.setdefault("subagent_calls", []).append({
        "ts": _now(),
        "agent": args.agent,
        "mode": args.mode,
        "digest": args.digest or "",
    })
    _save(state)
    return 0


def cmd_file_changed(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run", file=sys.stderr)
        return 1
    files = state.setdefault("files_changed", [])
    if args.path not in files:
        files.append(args.path)
    _save(state)
    return 0


def cmd_skill(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run", file=sys.stderr)
        return 1
    state.setdefault("skill_invocations", []).append({
        "ts": _now(),
        "skill": args.name,
        "exit": args.exit,
        "elapsed": args.elapsed,
    })
    _save(state)
    return 0


def cmd_halt(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run", file=sys.stderr)
        return 1
    state["status"] = "halted"
    state["halt_reason"] = args.reason
    state["current_state"] = "HALTED"
    _save(state)
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("error: no active run", file=sys.stderr)
        return 1
    state["status"] = "done"
    state["current_state"] = "DONE"
    _save(state)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = _load()
    if not state:
        print("(no active run)")
        return 0
    print(json.dumps(state, indent=2))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    if STATUS_FILE.exists():
        STATUS_FILE.unlink()
    print("cleared")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start"); p.add_argument("--run-id"); p.add_argument("--goal", required=True)
    p.add_argument("--mod", required=True); p.set_defaults(func=cmd_start)

    p = sub.add_parser("transition")
    p.add_argument("--from", dest="from_state", required=True)
    p.add_argument("--to",   dest="to_state",   required=True)
    p.add_argument("--notes")
    p.set_defaults(func=cmd_transition)

    p = sub.add_parser("subagent")
    p.add_argument("--agent", required=True)
    p.add_argument("--mode",  required=True)
    p.add_argument("--digest")
    p.set_defaults(func=cmd_subagent)

    p = sub.add_parser("file-changed"); p.add_argument("--path", required=True)
    p.set_defaults(func=cmd_file_changed)

    p = sub.add_parser("skill")
    p.add_argument("--name", required=True)
    p.add_argument("--exit", type=int, required=True)
    p.add_argument("--elapsed", type=float, required=True)
    p.set_defaults(func=cmd_skill)

    p = sub.add_parser("halt"); p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_halt)

    p = sub.add_parser("done");   p.set_defaults(func=cmd_done)
    p = sub.add_parser("status"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("reset");  p.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
