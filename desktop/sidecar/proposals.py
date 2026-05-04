"""Skill proposal endpoints for the desktop sidecar.

Wraps the output of /agentic-z-promote-skill (Phase 5 of Live Mode). Lets the
user review proposed-skill drafts in the desktop UI, edit the SKILL.md inline,
and promote the proposal into .claude/skills/ with one click.

Note: deliberately omits `from __future__ import annotations` — Pydantic models
defined inside the make_router() closure can't be resolved as ForwardRefs by
FastAPI's type-adapter rebuild step under Pydantic v2.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel


def make_router(repo_root: Path) -> APIRouter:
    router = APIRouter()

    PROPOSALS_DIR = repo_root / "output" / "skill-proposals"
    SKILLS_DIR = repo_root / ".claude" / "skills"

    class ProposalSummary(BaseModel):
        slug: str
        path: str
        skill_md_size: int
        py_files: list
        modified_at: float
        first_line: str

    class ProposalListResponse(BaseModel):
        proposals: list
        proposals_dir: str

    class ProposalDetail(BaseModel):
        slug: str
        skill_md: str
        py_files: dict

    class ProposalEditRequest(BaseModel):
        skill_md: Optional[str] = None
        py_files: Optional[dict] = None

    class PromoteRequest(BaseModel):
        slug: str
        delete_proposal: bool = True

    class PromoteResponse(BaseModel):
        ok: bool
        target_dir: str
        files_copied: list
        sync_skills_exit: Optional[int] = None
        sync_skills_log: Optional[str] = None

    def _scan_proposal(path):
        skill_md = path / "SKILL.md"
        py_files = sorted(p.name for p in path.glob("*.py"))
        size = skill_md.stat().st_size if skill_md.exists() else 0
        try: mtime = path.stat().st_mtime
        except OSError: mtime = 0.0
        first_line = ""
        if skill_md.exists():
            try:
                with skill_md.open("r", encoding="utf-8", errors="replace") as f:
                    in_fm = False
                    for line in f:
                        s = line.strip()
                        if s == "---":
                            in_fm = not in_fm
                            continue
                        if in_fm: continue
                        if not s or s.startswith("#"): continue
                        first_line = s[:200]
                        break
            except OSError: pass
        return ProposalSummary(
            slug=path.name, path=str(path), skill_md_size=size, py_files=py_files,
            modified_at=mtime, first_line=first_line,
        )

    def _safe_proposal_dir(slug: str):
        if not slug or "/" in slug or "\\" in slug or ".." in slug:
            raise HTTPException(status_code=400, detail="invalid slug")
        target = (PROPOSALS_DIR / slug).resolve()
        try:
            target.relative_to(PROPOSALS_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid slug")
        return target

    @router.get("/api/proposals", response_model=ProposalListResponse)
    def list_proposals():
        if not PROPOSALS_DIR.exists():
            return ProposalListResponse(proposals=[], proposals_dir=str(PROPOSALS_DIR))
        proposals = [_scan_proposal(p) for p in sorted(PROPOSALS_DIR.iterdir()) if p.is_dir()]
        return ProposalListResponse(proposals=proposals, proposals_dir=str(PROPOSALS_DIR))

    @router.get("/api/proposals/{slug}", response_model=ProposalDetail)
    def get_proposal(slug: str):
        d = _safe_proposal_dir(slug)
        if not d.exists():
            raise HTTPException(status_code=404, detail="proposal not found")
        skill_md = (d / "SKILL.md")
        py_files = {}
        for p in d.glob("*.py"):
            try: py_files[p.name] = p.read_text(encoding="utf-8", errors="replace")
            except OSError: pass
        return ProposalDetail(
            slug=slug,
            skill_md=skill_md.read_text(encoding="utf-8", errors="replace") if skill_md.exists() else "",
            py_files=py_files,
        )

    @router.post("/api/proposals/{slug}/edit")
    def edit_proposal(slug: str, body: ProposalEditRequest = Body(...)):
        d = _safe_proposal_dir(slug)
        if not d.exists():
            raise HTTPException(status_code=404, detail="proposal not found")
        if body.skill_md is not None:
            (d / "SKILL.md").write_text(body.skill_md, encoding="utf-8")
        if body.py_files is not None:
            for name, content in body.py_files.items():
                if "/" in name or "\\" in name or ".." in name:
                    raise HTTPException(status_code=400, detail="invalid py filename")
                if not name.endswith(".py"):
                    raise HTTPException(status_code=400, detail="py filename must end with .py")
                (d / name).write_text(content, encoding="utf-8")
        return {"ok": True, "modified_at": time.time()}

    @router.post("/api/proposals/promote", response_model=PromoteResponse)
    def promote(body: PromoteRequest):
        d = _safe_proposal_dir(body.slug)
        if not d.exists():
            raise HTTPException(status_code=404, detail="proposal not found")
        target = SKILLS_DIR / body.slug
        if target.exists():
            raise HTTPException(status_code=409,
                detail=f"skill {body.slug} already exists in .claude/skills/")
        target.parent.mkdir(parents=True, exist_ok=True)
        files_copied = []
        for src in d.iterdir():
            if not src.is_file(): continue
            shutil.copy2(src, target / src.name)
            files_copied.append(src.name)
        sync_path = SKILLS_DIR / "sync-skills" / "sync.py"
        sync_exit = None
        sync_log = None
        if sync_path.exists():
            try:
                proc = subprocess.run(
                    [sys.executable, str(sync_path)],
                    capture_output=True, text=True, timeout=30,
                )
                sync_exit = proc.returncode
                sync_log = (proc.stdout + proc.stderr)[-2000:]
            except subprocess.TimeoutExpired:
                sync_log = "sync-skills timed out after 30s"
            except Exception as e:
                sync_log = f"sync-skills failed: {e}"
        if body.delete_proposal:
            shutil.rmtree(d)
        return PromoteResponse(
            ok=True, target_dir=str(target), files_copied=files_copied,
            sync_skills_exit=sync_exit, sync_skills_log=sync_log,
        )

    @router.post("/api/proposals/refresh")
    def refresh_proposals(threshold: int = 2):
        skill = SKILLS_DIR / "agentic-z-promote-skill" / "promote.py"
        if not skill.exists():
            raise HTTPException(status_code=404,
                detail="agentic-z-promote-skill not installed; run Phase 5 deploy first")
        try:
            proc = subprocess.run(
                [sys.executable, str(skill), "--threshold", str(threshold)],
                capture_output=True, text=True, timeout=60,
            )
            return {"ok": True, "exit": proc.returncode,
                    "log": (proc.stdout + proc.stderr)[-4000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "promoter timed out after 60s"}

    return router
