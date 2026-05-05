"""Anthropic API integration: settings, test-key, Mod Creator.

Brings forward the BYOK design from D6 so the Mod Creator feature actually
works end-to-end. The user sets their key in Settings (stored in `.env` at
the repo root, gitignored). The Mod Creator uses Claude with the dayz-coder.md
agent definition as the system prompt and tool calls (`write_file`, `done`)
to scaffold a mod from a natural-language pitch.

Endpoints:
  GET  /api/settings              — return masked key + status (key never leaks raw)
  POST /api/settings              — write key into .env
  POST /api/anthropic/test-key    — fire a 1-token request, return ok/error
  POST /api/mod-creator (SSE)     — pitch → streaming mod scaffold

Note: deliberately omits `from __future__ import annotations` — see proposals.py
for the same reason.
"""
import asyncio
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _junction_helper import create_junction
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


DEFAULT_MODEL = "claude-opus-4-7"
MOD_CREATOR_TIMEOUT_SECONDS = 300       # generous — large pitches take a few minutes
MOD_CREATOR_MAX_FILES = 25
MOD_CREATOR_MAX_FILE_BYTES = 200_000


def make_router(repo_root: Path) -> APIRouter:
    router = APIRouter()

    ENV_FILE = repo_root / ".env"
    AGENT_FILE = repo_root / ".claude" / "agents" / "dayz-coder.md"
    WORKSPACE_DIR = repo_root / "workspace"
    AUTHOR_CACHE = repo_root / ".claude" / "local-memory" / "dayz-author.txt"

    # ---- helpers: .env read/write ----

    def _load_env() -> dict[str, str]:
        if not ENV_FILE.exists():
            return {}
        out: dict[str, str] = {}
        try:
            for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                out[k.strip()] = v
        except OSError:
            pass
        return out

    def _save_env(updates: dict[str, str]) -> None:
        existing = _load_env()
        existing.update(updates)
        # Preserve comments and ordering best-effort: rewrite known keys + append unknown.
        lines: list[str] = []
        seen: set[str] = set()
        if ENV_FILE.exists():
            try:
                for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
                    s = raw.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        lines.append(raw); continue
                    k, _, _v = s.partition("=")
                    k = k.strip()
                    if k in existing:
                        lines.append(f"{k}={existing[k]}")
                        seen.add(k)
                    else:
                        lines.append(raw)
            except OSError:
                pass
        for k, v in existing.items():
            if k not in seen:
                lines.append(f"{k}={v}")
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 12:
            return "***"
        return f"{key[:8]}…{key[-4:]}"

    def _read_anthropic_key() -> str:
        env = _load_env()
        key = env.get("ANTHROPIC_API_KEY", "").strip()
        if key.startswith("export "):
            key = key.split("=", 1)[-1].strip().strip('"').strip("'")
        return key

    def _read_voyage_key() -> str:
        env = _load_env()
        return env.get("VOYAGE_API_KEY", "").strip()

    def _read_author() -> Optional[str]:
        if AUTHOR_CACHE.exists():
            try:
                return AUTHOR_CACHE.read_text(encoding="utf-8").strip() or None
            except OSError: return None
        return None

    # ---- /api/settings ----

    class SettingsResponse(BaseModel):
        anthropic_key_set: bool
        anthropic_key_masked: str
        voyage_key_set: bool
        voyage_key_masked: str
        author: Optional[str] = None
        env_path: str

    class SettingsUpdate(BaseModel):
        anthropic_key: Optional[str] = None
        voyage_key: Optional[str] = None
        author: Optional[str] = None

    @router.get("/api/settings", response_model=SettingsResponse)
    def get_settings() -> SettingsResponse:
        ak = _read_anthropic_key()
        vk = _read_voyage_key()
        return SettingsResponse(
            anthropic_key_set=bool(ak), anthropic_key_masked=_mask_key(ak),
            voyage_key_set=bool(vk), voyage_key_masked=_mask_key(vk),
            author=_read_author(), env_path=str(ENV_FILE),
        )

    @router.post("/api/settings", response_model=SettingsResponse)
    def update_settings(body: SettingsUpdate) -> SettingsResponse:
        updates: dict[str, str] = {}
        if body.anthropic_key is not None and body.anthropic_key.strip():
            k = body.anthropic_key.strip()
            if not (k.startswith("sk-ant-") or k.startswith("sk-")):
                raise HTTPException(status_code=400,
                    detail="Anthropic key should start with 'sk-ant-'")
            updates["ANTHROPIC_API_KEY"] = k
        if body.voyage_key is not None and body.voyage_key.strip():
            updates["VOYAGE_API_KEY"] = body.voyage_key.strip()
        if updates:
            _save_env(updates)
        if body.author is not None and body.author.strip():
            AUTHOR_CACHE.parent.mkdir(parents=True, exist_ok=True)
            AUTHOR_CACHE.write_text(body.author.strip(), encoding="utf-8")
        return get_settings()

    # ---- /api/anthropic/test-key ----

    class TestKeyResponse(BaseModel):
        ok: bool
        model: Optional[str] = None
        error: Optional[str] = None
        latency_ms: Optional[int] = None

    @router.post("/api/anthropic/test-key", response_model=TestKeyResponse)
    def test_key() -> TestKeyResponse:
        key = _read_anthropic_key()
        if not key:
            return TestKeyResponse(ok=False, error="ANTHROPIC_API_KEY not set in .env")
        try:
            import anthropic
        except ImportError:
            return TestKeyResponse(ok=False,
                error="`anthropic` Python package not installed. Run: pip install anthropic")
        client = anthropic.Anthropic(api_key=key)
        started = time.time()
        try:
            resp = client.messages.create(
                model=DEFAULT_MODEL, max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
            elapsed = int((time.time() - started) * 1000)
            return TestKeyResponse(ok=True, model=resp.model or DEFAULT_MODEL, latency_ms=elapsed)
        except Exception as e:  # don't 500 — surface the API error
            return TestKeyResponse(ok=False, error=str(e)[:500])

    # ---- /api/mod-creator (SSE) ----

    class ModCreatorRequest(BaseModel):
        name: str
        pitch: str
        author: Optional[str] = None
        model: Optional[str] = None

    NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

    def _format_sse(data: dict | str, event: Optional[str] = None) -> str:
        payload = json.dumps(data) if isinstance(data, dict) else str(data)
        msg = ""
        if event: msg += f"event: {event}\n"
        for line in payload.splitlines() or [""]: msg += f"data: {line}\n"
        msg += "\n"
        return msg

    def _strip_frontmatter(md: str) -> str:
        if md.startswith("---"):
            end = md.find("\n---\n", 3)
            if end > 0:
                return md[end + 5:]
        return md

    def _safe_path_in_mod(mod_root: Path, rel_path: str) -> Optional[Path]:
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        if ".." in rel_path.split("/"):
            return None
        target = (mod_root / rel_path).resolve()
        try:
            target.relative_to(mod_root.resolve())
        except ValueError:
            return None
        return target

    @router.post("/api/mod-creator")
    async def mod_creator(body: ModCreatorRequest, request: Request) -> StreamingResponse:
        # Validate up-front (these errors surface before the stream starts).
        if not NAME_PATTERN.match(body.name):
            raise HTTPException(status_code=400,
                detail="mod name: letters/digits/underscores, must start with a letter, ≤64 chars")
        mod_root = WORKSPACE_DIR / body.name
        if mod_root.exists():
            raise HTTPException(status_code=409,
                detail=f"workspace/{body.name}/ already exists")
        if not body.pitch.strip():
            raise HTTPException(status_code=400, detail="pitch is required")
        if not AGENT_FILE.exists():
            raise HTTPException(status_code=503,
                detail="dayz-coder agent not installed at .claude/agents/dayz-coder.md")
        key = _read_anthropic_key()
        if not key:
            raise HTTPException(status_code=503,
                detail="ANTHROPIC_API_KEY not set. Open Settings to add it.")

        try:
            import anthropic
        except ImportError:
            raise HTTPException(status_code=500,
                detail="`anthropic` package missing. pip install anthropic")

        author = body.author or _read_author() or "Unknown"
        model = body.model or DEFAULT_MODEL
        system_prompt = _strip_frontmatter(AGENT_FILE.read_text(encoding="utf-8"))
        user_message = (
            f"Generate a complete DayZ mod scaffold for the pitch below by calling the "
            f"`write_file` tool repeatedly, one call per file. End with the `done` tool.\n\n"
            f"Mod name: {body.name}\n"
            f"Author: {author}\n"
            f"Pitch: {body.pitch}\n\n"
            f"Mandatory: write `config.cpp` (with CfgPatches) and `$PBOPREFIX$`. "
            f"Place Enforce Script files in scripts/3_Game/, scripts/4_World/, scripts/5_Mission/ "
            f"as appropriate. Follow the EnScript style guide and L2 conventions you already know. "
            f"Use prefixed class names (e.g. {body.name}_Foo). Use `modded class` (no inheritance "
            f"clause) when extending vanilla. Keep individual files focused — one class per file "
            f"unless very small. Do not exceed {MOD_CREATOR_MAX_FILES} files."
        )

        tools = [
            {
                "name": "write_file",
                "description": (
                    "Write one file in the new mod's workspace folder. "
                    "Path is relative to the mod root (e.g. 'config.cpp', "
                    "'scripts/4_World/MyClass.c'). Content is the full file body."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "done",
                "description": "Signal the mod scaffold is complete. Provide a 1-3 sentence summary.",
                "input_schema": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
            },
        ]

        async def stream():
            mod_root.mkdir(parents=True, exist_ok=True)
            client = anthropic.Anthropic(api_key=key)
            messages = [{"role": "user", "content": user_message}]
            files_written: list[str] = []
            yield _format_sse({"event": "started", "mod": body.name, "model": model}, event="control")

            done_summary: Optional[str] = None
            iteration = 0
            try:
                while iteration < 10:  # max tool-loop iterations
                    iteration += 1
                    if await request.is_disconnected():
                        yield _format_sse({"event": "client_disconnected"}, event="control")
                        return

                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.messages.create(
                            model=model, max_tokens=16384, system=system_prompt,
                            tools=tools, messages=messages,
                        ),
                    )

                    assistant_blocks = []
                    tool_results = []
                    for block in response.content:
                        if block.type == "text":
                            assistant_blocks.append({"type": "text", "text": block.text})
                            if block.text.strip():
                                yield _format_sse({"text": block.text}, event="thought")
                        elif block.type == "tool_use":
                            assistant_blocks.append({
                                "type": "tool_use", "id": block.id,
                                "name": block.name, "input": block.input,
                            })
                            tool_name = block.name
                            tool_input = block.input or {}
                            if tool_name == "write_file":
                                rel = str(tool_input.get("path", "")).strip()
                                content = str(tool_input.get("content", ""))
                                target = _safe_path_in_mod(mod_root, rel)
                                if target is None:
                                    err = f"refused: path '{rel}' escapes mod root"
                                    yield _format_sse({"error": err, "path": rel}, event="error")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                    continue
                                if len(files_written) >= MOD_CREATOR_MAX_FILES:
                                    err = f"refused: file cap ({MOD_CREATOR_MAX_FILES}) reached"
                                    yield _format_sse({"error": err}, event="error")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                    continue
                                if len(content.encode("utf-8")) > MOD_CREATOR_MAX_FILE_BYTES:
                                    err = f"refused: file too large ({len(content)} bytes)"
                                    yield _format_sse({"error": err, "path": rel}, event="error")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                    continue
                                target.parent.mkdir(parents=True, exist_ok=True)
                                target.write_text(content, encoding="utf-8")
                                files_written.append(rel)
                                yield _format_sse({"path": rel, "bytes": len(content)},
                                                  event="file_written")
                                tool_results.append({
                                    "type": "tool_result", "tool_use_id": block.id,
                                    "content": f"wrote {rel} ({len(content)} bytes)",
                                })
                            elif tool_name == "done":
                                done_summary = str(tool_input.get("summary", ""))
                                tool_results.append({
                                    "type": "tool_result", "tool_use_id": block.id,
                                    "content": "acknowledged",
                                })
                            else:
                                tool_results.append({
                                    "type": "tool_result", "tool_use_id": block.id,
                                    "content": f"unknown tool: {tool_name}", "is_error": True,
                                })

                    messages.append({"role": "assistant", "content": assistant_blocks})

                    if response.stop_reason == "end_turn" or done_summary is not None:
                        break
                    if response.stop_reason == "tool_use":
                        messages.append({"role": "user", "content": tool_results})
                        continue
                    # max_tokens or other; bail out
                    break

                # Create the P:\<ModName>\ junction so AddonBuilder can find the source.
                # Mirrors the post-scaffold step from /dayz-new-mod.
                jr = create_junction(mod_root, body.name)
                if jr["ok"]:
                    yield _format_sse({
                        "kind": jr["kind"], "target": jr["target"], "mod": body.name,
                    }, event="junction_created")
                else:
                    yield _format_sse({
                        "error": f"junction creation failed: {jr['error']}",
                        "target": jr["target"], "mod": body.name,
                    }, event="junction_failed")

                yield _format_sse({
                    "event": "done", "files": files_written, "summary": done_summary or "",
                    "iterations": iteration,
                    "junction": {"ok": jr["ok"], "kind": jr.get("kind"), "error": jr.get("error")},
                }, event="control")
            except Exception as e:
                yield _format_sse({"error": str(e)[:500]}, event="error")

        return StreamingResponse(
            stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
