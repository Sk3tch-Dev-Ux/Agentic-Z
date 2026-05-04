"""Tiny helper module: create the P:\\<ModName>\\ junction.

Mirrors the logic in .claude/skills/dayz-new-mod/new_mod.py but extracted so
the Mod Creator endpoint can call it without re-implementing the platform
fallback (symlink → mklink /J).

Imported by anthropic_api.py.
"""
import os
import subprocess
import sys
from pathlib import Path


def _link_target(path: Path):
    """Return the link target (without \\\\?\\ prefix) or None if not a link."""
    try:
        target = os.readlink(path)
    except OSError:
        return None
    if isinstance(target, bytes):
        target = target.decode("utf-8", errors="replace")
    if target.startswith("\\\\?\\"):
        target = target[4:]
    return Path(target)


def junction_status(p_drive_link: Path, expected_target: Path) -> str:
    """Classify the current state of P:\\<ModName>\\.

    Returns one of:
      "absent"       — nothing at that path
      "valid"        — junction/symlink pointing at expected_target
      "stale_match"  — junction at expected_target's path but it doesn't exist (we can recreate)
      "wrong_target" — junction pointing somewhere else (refuse)
      "real_folder"  — exists as a regular folder (refuse)
    """
    if not os.path.lexists(p_drive_link):
        return "absent"
    target = _link_target(p_drive_link)
    if target is None:
        return "real_folder"
    try:
        if target.resolve() == expected_target.resolve():
            return "valid"
    except OSError:
        pass
    if str(target).rstrip("\\/") == str(expected_target).rstrip("\\/"):
        return "stale_match"
    return "wrong_target"


def create_junction(mod_root: Path, mod_name: str) -> dict:
    """Create P:\\<ModName>\\ → mod_root. Idempotent.

    Returns dict with:
      ok (bool), kind ('symlink' | 'junction' | 'existing'),
      target (str), error (str | None)
    """
    p_drive_link = Path(f"P:\\{mod_name}")
    status = junction_status(p_drive_link, mod_root)

    if status == "valid":
        return {"ok": True, "kind": "existing", "target": str(p_drive_link), "error": None}

    if status == "real_folder":
        return {"ok": False, "kind": None, "target": str(p_drive_link),
                "error": f"P:\\{mod_name} exists as a real folder, not a link. "
                         "Move or delete it manually before retrying."}

    if status == "wrong_target":
        return {"ok": False, "kind": None, "target": str(p_drive_link),
                "error": f"P:\\{mod_name} is a junction pointing somewhere else. "
                         "Remove it manually (cmd /c rmdir P:\\{mod_name}) before retrying."}

    if status == "stale_match":
        # Same-name junction but its workspace target is gone. Clean it up.
        try:
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "rmdir", str(p_drive_link)],
                    check=True, capture_output=True, text=True,
                )
            else:
                os.unlink(p_drive_link)
        except Exception as e:
            return {"ok": False, "kind": None, "target": str(p_drive_link),
                    "error": f"failed to clean stale junction: {e}"}

    # status was "absent" (or just cleaned). Create.
    try:
        os.symlink(str(mod_root), str(p_drive_link), target_is_directory=True)
        return {"ok": True, "kind": "symlink", "target": str(p_drive_link), "error": None}
    except OSError:
        if os.name != "nt":
            return {"ok": False, "kind": None, "target": str(p_drive_link),
                    "error": "symlink failed and no Windows fallback available on this OS"}
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(p_drive_link), str(mod_root)],
                check=True, capture_output=True, text=True,
            )
            return {"ok": True, "kind": "junction", "target": str(p_drive_link), "error": None}
        except subprocess.CalledProcessError as e:
            return {"ok": False, "kind": None, "target": str(p_drive_link),
                    "error": f"mklink /J failed: {e.stderr.strip() if e.stderr else e}"}
        except Exception as e:
            return {"ok": False, "kind": None, "target": str(p_drive_link),
                    "error": f"junction creation failed: {e}"}
