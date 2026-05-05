---
name: feedback_verify_class_before_modded
description: Always call search_vanilla / search_dayz_source to verify a class exists before writing `modded class X { ... }`. Hallucinated class names cause "Unknown type 'X'" compile errors.
type: feedback
---

Before writing `modded class X { ... }`, verify X exists in vanilla via `search_vanilla(query="class X")` (in the Mod Creator) or `search_dayz_source(query="class X")` (in dayz-coder). If the search returns no hits, X almost certainly doesn't exist — pick a real vanilla class to extend instead.

**Why:** Real session 2026-05-04 — the Mod Creator generated `modded class SalineBag_Full { ... }` for a saline IV-completion heal mod. AddonBuilder rejected it with `Unknown type 'SalineBag_Full'`. Real DayZ has only `SalineBag` (no `_Full` suffix); saline state is tracked via the `Quantity` property on a single class, not a paired `_Empty/_Full` class structure. The LLM confused saline bags with blood bags (which do follow the paired pattern).

The hallucination cost the user a build-fail cycle. With `search_vanilla` available, the LLM could have verified before declaring.

**How to apply:**
- For every `modded class X` declaration, search vanilla for `class X` first
- Pay extra attention to paired-state assumptions: `_Empty/_Full`, `_Open/_Closed` etc. don't apply to all items uniformly
- For medical mods specifically, `requiredAddons[]` should include `"DZ_Gear_Medical"` — but adding that won't fix a hallucinated class name; it has to be a real vanilla type
- When in doubt, search wide first, narrow second: `search_vanilla(query="SalineBag")` before `search_vanilla(query="SalineBag_Full")` so you see what really exists

The agent's prompt now includes a CRITICAL — verify before you write directive that locks this in. The Mod Creator user-message preamble enforces the rule for this specific surface.
