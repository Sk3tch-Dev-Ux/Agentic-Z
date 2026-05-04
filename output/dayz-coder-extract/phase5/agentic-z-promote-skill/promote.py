"""Skill promotion scanner.

Walk every `.md` under `.claude/agent-memory/`, find recurring patterns in
feedback memories and dayz-director postmortems, optionally scan
`.claude/local-memory/dayz-watch.log` for recurring runtime errors, and
propose new skills for the top clusters.

Conservative by design: this script writes proposals to
`output/skill-proposals/<name>/` for user review. It NEVER drops anything
into `.claude/skills/` directly. Bad skills proliferate faster than good
ones — every promotion gets a human eyeball.

Three input sources:
  1. Per-agent feedback memories
       `.claude/agent-memory/<agent>/*.md` with `type: feedback` frontmatter
  2. dayz-director postmortems
       `.claude/agent-memory/dayz-director/runs/*.md` (Phase 4 output)
  3. Recurring runtime errors
       `.claude/local-memory/dayz-watch.log` JSON events (Phase 3 output)

Each source contributes signals; clusters with combined count >=
--threshold get a draft SKILL.md + skeleton .py script.

Run:
    python .claude/skills/agentic-z-promote-skill/promote.py                    # propose
    python .claude/skills/agentic-z-promote-skill/promote.py --status           # just count
    python .claude/skills/agentic-z-promote-skill/promote.py --threshold 5      # higher bar
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Resolve repo root from this file: <repo>/.claude/skills/agentic-z-promote-skill/promote.py
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]

AGENT_MEMORY_DIR = REPO_ROOT / ".claude" / "agent-memory"
DIRECTOR_RUNS_DIR = AGENT_MEMORY_DIR / "dayz-director" / "runs"
WATCH_LOG = REPO_ROOT / ".claude" / "local-memory" / "dayz-watch.log"
PROPOSAL_DIR = REPO_ROOT / "output" / "skill-proposals"

OK = "[OK]   "
WARN = "[WARN] "
INFO = "[INFO] "
ACT = "[ACT]  "

# Tokens to strip from filenames before topic extraction
_FILENAME_NOISE = re.compile(
    r"^(feedback|user|project|reference|memory|note|notes)[_\-]+|"
    r"[_\-]+(feedback|memory|note|notes)$",
    re.IGNORECASE,
)
_NORMALIZE = re.compile(r"[^a-z0-9]+")


# ---------- data classes ----------------------------------------------------


@dataclass
class Signal:
    """A single piece of evidence pointing at a recurring pattern."""
    topic: str  # normalized cluster key
    source: str  # "memory" | "postmortem" | "watch_error"
    path: str  # absolute path or log identifier
    excerpt: str  # human-readable preview


@dataclass
class Cluster:
    topic: str
    signals: list[Signal] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.signals)

    @property
    def display_name(self) -> str:
        return self.topic.replace("_", " ").title()


# ---------- topic extraction ------------------------------------------------


def _normalize_topic(raw: str) -> str:
    """Lowercase, drop boilerplate prefixes, replace non-alnum with single underscores."""
    s = _FILENAME_NOISE.sub("", raw)
    s = _NORMALIZE.sub("_", s.lower()).strip("_")
    return s or "uncategorized"


def _topic_from_filename(path: Path) -> str:
    return _normalize_topic(path.stem)


def _topic_from_frontmatter(text: str) -> str | None:
    """Pull `name:` or `description:` from YAML frontmatter."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---\n", 3)
    if end < 0:
        return None
    fm = text[3:end]
    for line in fm.splitlines():
        line = line.strip()
        if line.lower().startswith("name:"):
            return _normalize_topic(line.split(":", 1)[1].strip().strip('"').strip("'"))
    return None


def _extract_excerpt(text: str, max_chars: int = 160) -> str:
    """First non-empty non-frontmatter, non-heading line of the body."""
    body = text
    if body.startswith("---"):
        end = body.find("\n---\n", 3)
        if end > 0:
            body = body[end + 5:]
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---"):
            continue
        return s[:max_chars]
    return ""


# ---------- scanners --------------------------------------------------------


def scan_agent_memory(threshold_marker: str = "type: feedback") -> list[Signal]:
    """Walk agent-memory/<agent>/*.md, extract feedback signals."""
    out: list[Signal] = []
    if not AGENT_MEMORY_DIR.exists():
        return out
    for md in AGENT_MEMORY_DIR.rglob("*.md"):
        if md.name == "MEMORY.md":
            continue
        # Skip director postmortems — handled by scan_director_postmortems
        try:
            if md.is_relative_to(DIRECTOR_RUNS_DIR):
                continue
        except (ValueError, AttributeError):
            pass
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if threshold_marker not in text:
            continue
        topic = _topic_from_frontmatter(text) or _topic_from_filename(md)
        out.append(Signal(
            topic=topic,
            source="memory",
            path=str(md),
            excerpt=_extract_excerpt(text),
        ))
    return out


def scan_director_postmortems() -> list[Signal]:
    """Walk dayz-director/runs/*.md. Each postmortem contributes one signal
    keyed on its goal-type (extracted from a `**Goal:**` line)."""
    out: list[Signal] = []
    if not DIRECTOR_RUNS_DIR.exists():
        return out
    for md in DIRECTOR_RUNS_DIR.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Extract goal — first **Goal:** line
        goal_match = re.search(r"\*\*Goal:\*\*\s*(.+)", text)
        if not goal_match:
            continue
        goal = goal_match.group(1).strip().strip('"').strip("'").strip("`")
        topic = _normalize_topic(goal)
        out.append(Signal(
            topic=topic,
            source="postmortem",
            path=str(md),
            excerpt=goal[:160],
        ))
    return out


def scan_watch_errors() -> list[Signal]:
    """Walk dayz-watch.log JSON events, extract recurring error patterns."""
    out: list[Signal] = []
    if not WATCH_LOG.exists():
        return out
    cutoff = time.time() - 30 * 86400  # last 30 days
    try:
        with WATCH_LOG.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                if rec.get("ts", 0) < cutoff:
                    continue
                if rec.get("event") not in ("log_error", "log_warning"):
                    continue
                pattern = rec.get("pattern", "")
                if not pattern:
                    continue
                # Cluster on (lane, pattern) — same pattern in different lanes
                # is rare but possible.
                topic = _normalize_topic(f"{rec.get('lane', 'unknown')}_{pattern}")
                out.append(Signal(
                    topic=topic,
                    source="watch_error",
                    path=str(WATCH_LOG),
                    excerpt=(rec.get("excerpt") or "")[:160],
                ))
    except OSError:
        return out
    return out


# ---------- clustering ------------------------------------------------------


def _cluster_key(topic: str) -> str:
    """Coarsen a topic to its first 2 tokens for cluster grouping.

    `types_xml_split`, `types_xml_validate`, `types_xml_balance` all map to
    `types_xml` — that's how we cluster the family without exact-match-only.
    `config_missing_class_declaration` stays distinct from `script_missing_*`
    because the first token (the lane) differs.
    """
    tokens = [t for t in topic.split("_") if t]
    if len(tokens) >= 2:
        return f"{tokens[0]}_{tokens[1]}"
    return topic


def cluster_signals(all_signals: list[Signal]) -> list[Cluster]:
    by_topic: dict[str, Cluster] = {}
    for sig in all_signals:
        key = _cluster_key(sig.topic)
        c = by_topic.setdefault(key, Cluster(topic=key))
        c.signals.append(sig)
    return sorted(by_topic.values(), key=lambda c: c.count, reverse=True)


# ---------- proposal drafter ------------------------------------------------


SKILL_TEMPLATE = """---
name: {slug}
description: |
  PROPOSED — addresses a recurring pattern detected by /agentic-z-promote-skill.
  This skill aggregates {count} signals across {sources} sources. Review the
  source list below, then either flesh out the action and copy this folder
  into `.claude/skills/`, or delete it if the pattern doesn't warrant a skill.
---

# /{slug} (PROPOSED)

This is an auto-generated skill proposal. It is NOT yet wired into the agents.
Treat it as a starting point — the action below is a placeholder.

Follow `.claude/skills/_shared/dayz-conventions.md`.

## What it should do

[REPLACE — define the action this skill automates. Suggested action based on
cluster topic "{display_name}":]

- TODO: enumerate the manual steps the user/agent has been repeating
- TODO: identify the inputs (mod name? file path? something else?)
- TODO: identify the output (file written? config edited? PBO built?)

## Source signals

{signals_block}

## How to run

```cmd
python .claude\\skills\\{slug}\\{slug_script}.py [args]
```

## Suggested implementation skeleton

See `{slug_script}.py` in this folder.

## Promotion checklist

Before copying this proposal into `.claude/skills/`:

- [ ] Action is well-defined (the "What it should do" section is filled in)
- [ ] Skeleton script is replaced with real logic
- [ ] Skill follows L2 conventions (preflight gate if it touches DayZ state)
- [ ] Skill name doesn't collide with an existing skill
- [ ] L3 references L2 in one line ("Follow `.claude/skills/_shared/dayz-conventions.md`.")
- [ ] Run `/sync-skills` after copying so all three CLIs see it
"""


SCRIPT_TEMPLATE = '''"""Skeleton for /{slug} — proposed by /agentic-z-promote-skill.

Replace this stub with real logic before copying into .claude/skills/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve repo root from this file: <repo>/.claude/skills/{slug}/{slug_script}.py
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="PROPOSED skill: /{slug}")
    parser.add_argument("--dry-run", action="store_true", help="preview only")
    args = parser.parse_args()

    print("PROPOSED skill stub — replace this main() with real logic.")
    print(f"Repo root resolved at: {{REPO_ROOT}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def write_proposal(cluster: Cluster, dry_run: bool) -> bool:
    """Write or update a proposal folder for this cluster. Returns True if
    anything was written."""
    slug = cluster.topic[:48].rstrip("_") or "uncategorized"
    slug_script = re.sub(r"[^a-z0-9]+", "_", slug)
    proposal_dir = PROPOSAL_DIR / slug
    skill_md = proposal_dir / "SKILL.md"
    skill_py = proposal_dir / f"{slug_script}.py"

    sources = sorted({s.source for s in cluster.signals})
    signal_lines = []
    for s in cluster.signals[:10]:
        signal_lines.append(f"- ({s.source}) `{s.path}`")
        if s.excerpt:
            signal_lines.append(f"  > {s.excerpt}")
    if cluster.count > 10:
        signal_lines.append(f"- ...and {cluster.count - 10} more")
    signals_block = "\n".join(signal_lines) or "_(no signal previews available)_"

    skill_md_content = SKILL_TEMPLATE.format(
        slug=slug,
        slug_script=slug_script,
        count=cluster.count,
        sources=len(sources),
        display_name=cluster.display_name,
        signals_block=signals_block,
    )
    skill_py_content = SCRIPT_TEMPLATE.format(slug=slug, slug_script=slug_script)

    if dry_run:
        action = "DRY"
    else:
        proposal_dir.mkdir(parents=True, exist_ok=True)
        action = "WRITE"

    wrote = False
    # Always rewrite SKILL.md (it's auto-generated). Preserve the .py if user
    # has begun editing it (i.e. content differs from the bare skeleton).
    existing_md = skill_md.read_text(encoding="utf-8") if skill_md.exists() else None
    if existing_md != skill_md_content:
        if not dry_run:
            skill_md.write_text(skill_md_content, encoding="utf-8")
        print(f"  [{action}] {skill_md.relative_to(REPO_ROOT)}")
        wrote = True
    else:
        print(f"  [OK ] {skill_md.relative_to(REPO_ROOT)} (already current)")

    if not skill_py.exists():
        if not dry_run:
            skill_py.write_text(skill_py_content, encoding="utf-8")
        print(f"  [{action}] {skill_py.relative_to(REPO_ROOT)} (skeleton)")
        wrote = True
    else:
        print(f"  [OK ] {skill_py.relative_to(REPO_ROOT)} (preserved — existing edits)")

    return wrote


# ---------- main ------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=int, default=2,
                        help="Minimum cluster count to propose a skill (default 2).")
    parser.add_argument("--status", action="store_true",
                        help="Print cluster counts only — no proposals written.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview proposals without writing.")
    parser.add_argument("--top", type=int, default=10,
                        help="Cap proposals at top-N clusters (default 10).")
    args = parser.parse_args()

    print("Agentic-Z skill promotion scanner\n")

    signals: list[Signal] = []
    signals.extend(scan_agent_memory())
    signals.extend(scan_director_postmortems())
    signals.extend(scan_watch_errors())

    print(f"{INFO} signals scanned: {len(signals)} "
          f"(memory={sum(1 for s in signals if s.source == 'memory')}, "
          f"postmortem={sum(1 for s in signals if s.source == 'postmortem')}, "
          f"watch_error={sum(1 for s in signals if s.source == 'watch_error')})")

    clusters = cluster_signals(signals)
    candidates = [c for c in clusters if c.count >= args.threshold]
    print(f"{INFO} clusters: {len(clusters)} total, "
          f"{len(candidates)} above threshold ({args.threshold}+)\n")

    if args.status or not candidates:
        if not clusters:
            print("(no signals yet — agents haven't accumulated memories)")
            return 0
        print("All clusters:")
        for c in clusters[:args.top]:
            mark = "*" if c.count >= args.threshold else " "
            print(f"  {mark} {c.count:3d}x  {c.topic}")
        if not candidates:
            print(f"\n{INFO} nothing above threshold yet. Run a few /dayz-director "
                  f"jobs or save more feedback memories, then re-run.")
        return 0

    print(f"Top {min(len(candidates), args.top)} promotion candidate(s):\n")
    written_any = False
    for c in candidates[:args.top]:
        print(f"=== {c.count}x  {c.display_name}  ({c.topic}) ===")
        wrote = write_proposal(c, args.dry_run)
        written_any = written_any or wrote
        print()

    if written_any and not args.dry_run:
        print(f"{OK} proposals written to {PROPOSAL_DIR.relative_to(REPO_ROOT)}/")
        print(f"{INFO} review each, fill in the action, then copy into .claude/skills/")
        print(f"{INFO} run /sync-skills after promoting any proposal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
