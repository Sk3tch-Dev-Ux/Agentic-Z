#!/usr/bin/env python3
"""patch.py - install Phase D6.2 (map setup UI).

Idempotent. Five surgical edits:

  1. Copy desktop/sidecar/server_maps.py (new module)
  2. Copy desktop/src/api/serverMaps.ts  (new types)
  3. Patch desktop/sidecar/main.py:
     a. Add `from server_maps import make_router as make_server_maps_router`
     b. Mount the router via `app.include_router(...)`
     c. Add a POST /api/server/maps/{map}/setup endpoint that uses the
        existing _start_run() to spawn /dayz-add-map.
  4. Patch desktop/src/pages/ModDetail.tsx to render the map readiness pill
     + "Set up <map>" button next to the Launch button.

After install: restart `pnpm tauri:dev` so the sidecar reloads.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


# ----- file copies -----

NEW_FILES = [
    (HERE / "desktop" / "sidecar" / "server_maps.py",
     REPO  / "desktop" / "sidecar" / "server_maps.py"),
    (HERE / "desktop" / "src" / "api" / "serverMaps.ts",
     REPO  / "desktop" / "src" / "api" / "serverMaps.ts"),
]


# ----- main.py patches -----

MAIN_FILE = REPO / "desktop" / "sidecar" / "main.py"

MAIN_IMPORT_OLD = "from anthropic_api import make_router as make_anthropic_router  # noqa: E402"
MAIN_IMPORT_NEW = (
    "from anthropic_api import make_router as make_anthropic_router  # noqa: E402\n"
    "from server_maps import make_router as make_server_maps_router  # noqa: E402"
)

MAIN_MOUNT_OLD = "app.include_router(make_anthropic_router(REPO_ROOT))"
MAIN_MOUNT_NEW = (
    "app.include_router(make_anthropic_router(REPO_ROOT))\n"
    "app.include_router(make_server_maps_router(REPO_ROOT))"
)

# Add the setup endpoint right after the existing stop_diag endpoint.
MAIN_ENDPOINT_OLD = '''@app.post("/api/mods/{mod_name}/stop", response_model=StartRunResponse)
async def stop_diag(mod_name: str) -> StartRunResponse:
    cmd = _skill_python_args("dayz-stop-test")
    rec = await _start_run(mod_name, "dayz-stop-test", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill, args=[], started_at=rec.started_at)'''

MAIN_ENDPOINT_NEW = '''@app.post("/api/mods/{mod_name}/stop", response_model=StartRunResponse)
async def stop_diag(mod_name: str) -> StartRunResponse:
    cmd = _skill_python_args("dayz-stop-test")
    rec = await _start_run(mod_name, "dayz-stop-test", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill, args=[], started_at=rec.started_at)


# D6.2 — map setup
@app.post("/api/server/maps/{map_name}/setup", response_model=StartRunResponse)
async def setup_map(map_name: str) -> StartRunResponse:
    """Run /dayz-add-map for the given map alias. Stream output via /api/runs/{id}/stream."""
    if not map_name or "/" in map_name or "\\\\" in map_name or ".." in map_name:
        raise HTTPException(status_code=400, detail="invalid map name")
    cmd = _skill_python_args("dayz-add-map", map_name)
    rec = await _start_run(None, "dayz-add-map", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill,
                            args=[map_name], started_at=rec.started_at)'''

MAIN_PATCHES = [
    ("import",   MAIN_IMPORT_OLD,   MAIN_IMPORT_NEW),
    ("mount",    MAIN_MOUNT_OLD,    MAIN_MOUNT_NEW),
    ("endpoint", MAIN_ENDPOINT_OLD, MAIN_ENDPOINT_NEW),
]


# ----- ModDetail.tsx patches -----

MOD_DETAIL_FILE = REPO / "desktop" / "src" / "pages" / "ModDetail.tsx"

# Add ServerMapsApi to imports + a map status query + a Setup button.
MOD_DETAIL_IMPORT_OLD = 'import { Api } from "../api/client";'
MOD_DETAIL_IMPORT_NEW = '''import { Api } from "../api/client";
import { ServerMapsApi } from "../api/serverMaps";
import { Map as MapIcon, Wrench } from "lucide-react";'''

# Add the query + setup mutation right after the launchMut definition.
MOD_DETAIL_QUERY_OLD = '''  const stopMut = useMutation({
    mutationFn: () => Api.stopDiag(name!),
    onSuccess: (r) => setModRun(name!, "stopRunId", r.run_id),
  });'''

MOD_DETAIL_QUERY_NEW = '''  const stopMut = useMutation({
    mutationFn: () => Api.stopDiag(name!),
    onSuccess: (r) => setModRun(name!, "stopRunId", r.run_id),
  });
  const mapsQ = useQuery({ queryKey: ["serverMaps"], queryFn: ServerMapsApi.list,
    refetchInterval: 5000 });
  const setupMapMut = useMutation({
    mutationFn: () => ServerMapsApi.setup("chernarus"),
    onSuccess: (r) => {
      setModRun(name!, "stopRunId", r.run_id); // reuse the panel slot
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["serverMaps"] }), 6000);
    },
  });
  const chernarus = mapsQ.data?.maps.find((m) => m.map === "chernarus");'''

# Insert a map-readiness pill row in the Actions panel.
MOD_DETAIL_ACTIONS_OLD = '''      <div className="panel p-4">
        <div className="font-medium mb-3">Actions</div>
        <div className="flex flex-wrap gap-2">'''

MOD_DETAIL_ACTIONS_NEW = '''      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-medium">Actions</span>
          <span className="ml-auto flex items-center gap-2 text-xs">
            <MapIcon className="w-3 h-3 text-muted" />
            <span className="text-muted">chernarus</span>
            {chernarus?.ready ? (
              <span className="pill-ok">ready</span>
            ) : (
              <span className="pill-warn">not set up</span>
            )}
            {!chernarus?.ready && (
              <button
                onClick={() => setupMapMut.mutate()}
                disabled={setupMapMut.isPending}
                className="btn flex items-center gap-1 text-xs"
                title="Run /dayz-add-map chernarus"
              >
                {setupMapMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3" />}
                Set up
              </button>
            )}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">'''

# Make Launch smart: if the map isn't set up, button label changes + click chains setup→launch.
MOD_DETAIL_LAUNCH_OLD = '''          <button className="btn flex items-center gap-2"
            onClick={() => launchMut.mutate()} disabled={anyMutating}>
            {launchMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Launch
          </button>'''

MOD_DETAIL_LAUNCH_NEW = '''          <button className="btn flex items-center gap-2"
            onClick={async () => {
              if (!chernarus?.ready) {
                await setupMapMut.mutateAsync();
                // Wait briefly for /dayz-add-map to finish, then refetch + launch.
                let tries = 0;
                while (tries < 30) {
                  await new Promise((r) => setTimeout(r, 1000));
                  const fresh = await ServerMapsApi.list();
                  if (fresh.maps.find((m) => m.map === "chernarus")?.ready) break;
                  tries++;
                }
              }
              launchMut.mutate();
            }}
            disabled={anyMutating || setupMapMut.isPending}>
            {(launchMut.isPending || setupMapMut.isPending) ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {chernarus?.ready ? "Launch" : "Set up & launch"}
          </button>'''

MOD_DETAIL_PATCHES = [
    ("imports",      MOD_DETAIL_IMPORT_OLD,  MOD_DETAIL_IMPORT_NEW),
    ("queries",      MOD_DETAIL_QUERY_OLD,   MOD_DETAIL_QUERY_NEW),
    ("actions row",  MOD_DETAIL_ACTIONS_OLD, MOD_DETAIL_ACTIONS_NEW),
    ("launch btn",   MOD_DETAIL_LAUNCH_OLD,  MOD_DETAIL_LAUNCH_NEW),
]


# ----- runner -----

def copy_files(dry_run: bool) -> int:
    print("1. Copy new modules")
    print("-" * 60)
    changed = 0
    for src, dst in NEW_FILES:
        if not src.exists():
            print(f"  [FAIL] source missing: {src}")
            continue
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            print(f"  [OK ] {dst.relative_to(REPO)} (already current)")
            continue
        action = "DRY" if dry_run else "WRITE"
        existed = "(replace)" if dst.exists() else "(new)"
        print(f"  [{action}] {dst.relative_to(REPO)} {existed}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        changed += 1
    return changed


def patch_file(path: Path, patches: list, label: str, dry_run: bool) -> int:
    print()
    print(label)
    print("-" * 60)
    if not path.exists():
        print(f"  [FAIL] target missing: {path}")
        return 0
    text = path.read_text(encoding="utf-8")
    changed = 0
    for name, old, new in patches:
        if new.split("\n")[0].strip() in text and "server_maps" in text and name == "import":
            print(f"  [OK ] {path.name}: {name} (already patched)")
            continue
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print(f"  [{'DRY' if dry_run else 'PATCH'}] {path.name}: {name}")
        elif _already_patched(text, new):
            print(f"  [OK ] {path.name}: {name} (already patched)")
        else:
            print(f"  [WARN] {path.name}: {name} anchor not found")
    if changed and not dry_run:
        path.write_text(text, encoding="utf-8")
    return changed


def _already_patched(text: str, new_block: str) -> bool:
    """Detect prior patches by the new-only sentinel lines."""
    sentinels = ["server_maps", "ServerMapsApi", "Set up & launch", "setupMapMut"]
    for s in sentinels:
        if s in new_block and s in text:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run - no files will be written)")
    print()

    total = 0
    total += copy_files(args.dry_run)
    total += patch_file(MAIN_FILE, MAIN_PATCHES, "2. Patch desktop/sidecar/main.py", args.dry_run)
    total += patch_file(MOD_DETAIL_FILE, MOD_DETAIL_PATCHES,
                        "3. Patch desktop/src/pages/ModDetail.tsx", args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Restart the dev session: pnpm tauri:dev (Ctrl+C the running one first).")
        print("On the mod detail page you'll see a 'chernarus: not set up · Set up' pill.")
        print("Click 'Set up' or just hit 'Set up & launch' — both run /dayz-add-map first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
