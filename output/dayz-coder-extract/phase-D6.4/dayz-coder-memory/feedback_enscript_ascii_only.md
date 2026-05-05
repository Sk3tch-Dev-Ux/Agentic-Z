---
name: feedback_enscript_ascii_only
description: Generated Enforce Script source files must be ASCII-only. Em dashes, smart quotes, ellipsis, NBSP all break the parser with confusing "Expected ',' or ')'" errors that point at whole strings.
type: feedback
---

Source `.c` files MUST be ASCII-only. No em dashes (—), smart quotes (' " ' "), ellipsis (…), non-breaking spaces, Unicode arrows (→), or accented characters. Anywhere — including comments.

**Why:** Real session 2026-05-04 — the Mod Creator generated `SalineHealing_MissionBoot.c` with `// SalineHealing — header` (em dash). AddonBuilder rejected it with `Expected ',' or ')', not a '[SalineHealing] Server mission initialised â€" saline IV heals '` — error pointing at the WHOLE string, not the em dash, because the file is read as Windows-1252 and the UTF-8 bytes for `—` (E2 80 94) become mojibake that doesn't lex.

The user lost ~10 minutes diagnosing because the error message blames the string content, not the em dash specifically.

**How to apply:** When writing or reviewing Enforce Script:
- Type plain hyphens `-` not em dashes `—`
- Type straight quotes `'` `"` not curly `'` `'` `"` `"`
- Type `...` not `…`
- Avoid bullets `•`, arrows `→`, accented letters in identifiers
- Reject any AI-generated `.c` file that contains non-ASCII before writing it

The Mod Creator's pre-write linter at `desktop/sidecar/_enscript_lint.py` enforces this. Reading or producing `.c` files outside that path → manually verify ASCII-only before commit.
