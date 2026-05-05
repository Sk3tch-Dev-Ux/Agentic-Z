"""Server-map setup endpoints for the desktop sidecar.

Wraps the existing /dayz-add-map skill so the desktop UI can:
  - Show which maps are ready for /dayz-launch-test
  - One-click set up a missing map (copies mission template from DayZ Server,
    writes per-map serverDZ.cfg + profiles/)

Note: deliberately omits `from __future__ import annotations` — see proposals.py
for the same reason (Pydantic + closure factory + ForwardRef).
"""
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


# Map alias -> mission template directory name (matches what /dayz-add-map writes).
MAP_TEMPLATES = {
    "chernarus": "dayzOffline.chernarusplus",
    "livonia":   "dayzOffline.enoch",
    "sakhal":    "dayzOffline.sakhal",
}


def make_router(repo_root: Path) -> APIRouter:
    router = APIRouter()

    SKILLS_DIR = repo_root / ".claude" / "skills"
    ADD_MAP_SKILL = SKILLS_DIR / "dayz-add-map" / "add_map.py"
    SERVER_DIR = repo_root / "workspace" / "_server"
    MISSIONS_DIR = SERVER_DIR / "missions"
    MAPS_DIR = SERVER_DIR / "maps"

    class MapStatus(BaseModel):
        map: str
        mission_template: str
        mission_present: bool
        mission_path: str
        cfg_present: bool
        cfg_path: str
        profiles_present: bool
        ready: bool

    class MapsListResponse(BaseModel):
        maps: list
        server_dir: str
        dayz_server_install_present: bool

    @router.get("/api/server/maps", response_model=MapsListResponse)
    def list_maps():
        # Best-effort detect of DayZ Server install via the existing resolver.
        dayz_server_present = False
        try:
            preflight_dir = SKILLS_DIR / "dayz-preflight"
            sys.path.insert(0, str(preflight_dir))
            from preflight import find_dayz_server  # type: ignore
            try:
                dayz_server_present = find_dayz_server() is not None
            except Exception:
                dayz_server_present = False
        except Exception:
            dayz_server_present = False

        out = []
        for alias, template in MAP_TEMPLATES.items():
            mission_dir = MISSIONS_DIR / template
            cfg = MAPS_DIR / alias / "serverDZ.cfg"
            profiles = MAPS_DIR / alias / "profiles"
            mission_present = mission_dir.exists() and mission_dir.is_dir()
            cfg_present = cfg.exists()
            profiles_present = profiles.exists()
            out.append(MapStatus(
                map=alias,
                mission_template=template,
                mission_present=mission_present,
                mission_path=str(mission_dir),
                cfg_present=cfg_present,
                cfg_path=str(cfg),
                profiles_present=profiles_present,
                ready=mission_present and cfg_present,
            ))
        return MapsListResponse(
            maps=out, server_dir=str(SERVER_DIR),
            dayz_server_install_present=dayz_server_present,
        )

    class SetupResponse(BaseModel):
        ok: bool
        run_id: Optional[str] = None
        skill: str
        args: list

    return router


# The actual subprocess dispatch is done in main.py via the existing
# _start_run() machinery so the run-stream SSE works transparently. This
# router only owns the read endpoint; the write endpoint lives in main.py
# alongside the other "spawn a skill subprocess" handlers.
