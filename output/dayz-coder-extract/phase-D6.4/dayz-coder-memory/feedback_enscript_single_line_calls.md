---
name: feedback_enscript_single_line_calls
description: Multi-line expressions inside function-call argument lists break Enforce Script's parser. Build into a typed local variable first, then pass the variable.
type: feedback
---

Don't split function-call argument expressions across multiple lines. The Enforce Script parser doesn't reliably handle continuations inside `(...)`.

```c
// BAD
Print("[Mod] Heals "
    + Constants.HEAL_AMOUNT + " HP on complete.");

// GOOD
string msg = "[Mod] Heals " + Constants.HEAL_AMOUNT + " HP on complete.";
Print(msg);
```

**Why:** Real session 2026-05-04 — the Mod Creator generated a multi-line `Print()` call. The parser produced `Expected ',' or ')', not a '<the first string literal content>'` — same shape of error as the em-dash issue, which made it look like a duplicate problem. It wasn't; collapsing to a single line + temp variable fixed it.

The error message is misleading because it points at the prior line's string content, not the line break or the trailing `+` that triggered the parser confusion. Easy to miss.

**How to apply:** Whenever a function call's argument is wide enough to want line-wrapping, build the value into a typed local variable on its own line first, then pass the variable.

This is also better practice for debugging: you can `Print(msg);` and inspect intermediate values mid-construction. The temp-variable pattern is the canonical Enforce Script idiom for long expressions.

The pre-write linter at `desktop/sidecar/_enscript_lint.py` catches lines that start with `+`/`-`/`*`/`/`/`,` while inside an unclosed `(` and rejects them with this fix recipe.
