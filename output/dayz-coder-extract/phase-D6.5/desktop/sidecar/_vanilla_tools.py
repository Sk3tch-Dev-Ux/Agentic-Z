"""Vanilla source access tools for the Mod Creator (D6.5).

Works WITHOUT the dayz-rag RAG index — direct file system access. Closes the
verification gap when Voyage is rate-limited or the RAG index isn't built.

Three functions exposed via Mod Creator's tool list:
  - grep_vanilla(pattern, path_glob, ...)  : exact regex search
  - list_vanilla_files(glob)               : path discovery
  - read_vanilla_file (in anthropic_api.py): read full content

Plus a VerificationState class the sidecar uses to refuse `modded class X { }`
declarations for classes that weren't searched/grepped first.
"""
import os
import re
from pathlib import Path
from typing import Optional


DEFAULT_VANILLA_ROOT = Path("P:\\")
DEFAULT_SCRIPTS_ROOT = DEFAULT_VANILLA_ROOT / "scripts"

MAX_HITS_DEFAULT = 50
MAX_PATTERN_LENGTH = 500
MAX_GLOB_RESULTS = 200


def _safe_pattern(pattern: str, flags: int = 0) -> Optional[re.Pattern]:
    if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        return None
    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


def grep_vanilla(
    pattern: str,
    path_glob: Optional[str] = None,
    case_insensitive: bool = True,
    max_hits: int = MAX_HITS_DEFAULT,
    vanilla_root: Optional[Path] = None,
) -> dict:
    """Run a regex over vanilla files and return matching lines with paths.

    Args:
        pattern: regex (Python `re` flavor)
        path_glob: relative glob under vanilla root, default scripts/**/*.c
        case_insensitive: default True
        max_hits: cap, default 50
        vanilla_root: override (testing); default DEFAULT_VANILLA_ROOT
    """
    flags = re.IGNORECASE if case_insensitive else 0
    rx = _safe_pattern(pattern, flags)
    if rx is None:
        return {"pattern": pattern, "files_searched": 0, "hits": [],
                "truncated": False, "error": "invalid or oversized regex"}

    root = (vanilla_root or DEFAULT_VANILLA_ROOT)
    scripts = root / "scripts"
    if path_glob:
        if path_glob.startswith("/") or path_glob.startswith("\\"):
            path_glob = path_glob.lstrip("/\\")
        if "/" not in path_glob and "\\" not in path_glob:
            path_glob = f"scripts/**/*{path_glob}*"
        try:
            files = list(root.glob(path_glob))
        except (OSError, ValueError) as e:
            return {"pattern": pattern, "files_searched": 0, "hits": [],
                    "truncated": False, "error": f"glob failed: {e}"}
    else:
        files = list(scripts.rglob("*.c")) if scripts.exists() else []

    if len(files) > MAX_GLOB_RESULTS:
        files = files[:MAX_GLOB_RESULTS]

    hits = []
    truncated = False
    files_searched = 0
    for path in files:
        if not path.is_file():
            continue
        files_searched += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_num, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append({
                    "path": str(path),
                    "line": line_num,
                    "text": line[:400],
                })
                if len(hits) >= max_hits:
                    truncated = True
                    break
        if truncated:
            break

    return {
        "pattern": pattern,
        "files_searched": files_searched,
        "hits": hits,
        "truncated": truncated,
        "error": None,
    }


def list_vanilla_files(
    glob_pattern: str,
    max_results: int = MAX_GLOB_RESULTS,
    vanilla_root: Optional[Path] = None,
) -> dict:
    if not glob_pattern or len(glob_pattern) > MAX_PATTERN_LENGTH:
        return {"glob": glob_pattern, "matches": [], "truncated": False,
                "error": "invalid or oversized glob"}
    if glob_pattern.startswith("/") or glob_pattern.startswith("\\"):
        glob_pattern = glob_pattern.lstrip("/\\")
    root = (vanilla_root or DEFAULT_VANILLA_ROOT)
    try:
        matches = [str(p) for p in root.glob(glob_pattern) if p.is_file()]
    except (OSError, ValueError) as e:
        return {"glob": glob_pattern, "matches": [], "truncated": False,
                "error": f"glob failed: {e}"}
    truncated = len(matches) > max_results
    if truncated:
        matches = matches[:max_results]
    return {
        "glob": glob_pattern,
        "matches": matches,
        "truncated": truncated,
        "error": None,
    }


_CLASS_DECL_RE = re.compile(
    r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE,
)
_MODDED_CLASS_RE = re.compile(
    r"^\s*modded\s+class\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


class VerificationState:
    """Per-run record of which classes/symbols Claude verified.

    write_file consults this to refuse `modded class X { }` for unverified X.
    """

    def __init__(self):
        self.seen_classes: set = set()

    def note_grep_hits(self, hits: list) -> None:
        for h in hits or []:
            for cls in _CLASS_DECL_RE.findall(h.get("text", "") or ""):
                self.seen_classes.add(cls)

    def note_file_content(self, content: str) -> None:
        for cls in _CLASS_DECL_RE.findall(content or ""):
            self.seen_classes.add(cls)

    def note_search_hits(self, hits: list) -> None:
        for h in hits or []:
            for field in ("parent_context", "parent", "snippet"):
                v = h.get(field, "") or ""
                for cls in _CLASS_DECL_RE.findall(v):
                    self.seen_classes.add(cls)

    def note_glob_matches(self, matches: list) -> None:
        for path in matches or []:
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem:
                self.seen_classes.add(stem)

    def was_verified(self, class_name: str) -> bool:
        if not class_name:
            return False
        cn = class_name.lower()
        return any(cn == c.lower() for c in self.seen_classes)


def find_modded_class_targets(content: str) -> list:
    """Return all class names X in `modded class X` declarations."""
    return _MODDED_CLASS_RE.findall(content or "")
