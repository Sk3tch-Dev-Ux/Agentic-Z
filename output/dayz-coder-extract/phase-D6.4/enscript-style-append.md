
---

## Compile-time gotchas (learned the hard way)

These rules don't show up in vanilla DayZ source code — they show up when the parser refuses to compile something a reasonable-looking script tried to do. Every entry below has cost a real session. The Mod Creator's pre-write linter (`desktop/sidecar/_enscript_lint.py`) enforces them automatically; document them here so every other DayZ agent + future contributor knows the rules without having to re-discover them.

### Source files MUST be ASCII-only

The Enforce Script parser does NOT tolerate non-ASCII characters anywhere in a `.c` file — including inside string literals AND inside comments. Em dashes, smart quotes, ellipsis characters, non-breaking spaces, Unicode arrows, accented letters: all break the parser.

The failure mode is confusing: an em dash inside a string literal produces `Expected ',' or ')'` pointing at the *whole string* (not the offending character), because the file is read as Windows-1252 and the UTF-8 bytes for `—` (E2 80 94) become mojibake (`â€"`) that doesn't lex as anything meaningful.

| Bad | Good |
|---|---|
| `// Hello — world` | `// Hello - world` |
| `Print("a—b");` | `Print("a-b");` |
| `Print("done…");` | `Print("done...");` |
| `Print("'quoted'");` (curly) | `Print("'quoted'");` (straight) |

When generating Enforce Script from natural-language inputs, agents/LLMs MUST emit ASCII-only output. Don't trust the model's default; the rule has to be explicit.

### Multi-line function-call argument lists are unreliable

The parser doesn't reliably handle expressions split across lines inside `(...)`. Specifically: a long string concatenation that spans two lines inside a `Print(...)` call produces the same `Expected ',' or ')'` error as the encoding case above, and the error points at the first string literal — making it look like an encoding issue when it's actually a continuation issue.

```c
// BAD — splits the argument expression across two lines
Print("[Mod] Heals "
    + Constants.HEAL_AMOUNT + " HP on complete.");

// GOOD — build the message on a single line via a temp variable
string msg = "[Mod] Heals " + Constants.HEAL_AMOUNT + " HP on complete.";
Print(msg);

// ALSO GOOD — single-line if it fits
Print("[Mod] Heals " + Constants.HEAL_AMOUNT + " HP on complete.");
```

The temp-variable form is preferred for any concatenation that's wide enough to want wrapping. It's also more debuggable — you can `Print(msg)` and inspect the value mid-construction.

### Verify vanilla class names BEFORE writing `modded class`

Confidently writing `modded class SalineBag_Full { ... }` when the real vanilla class is `SalineBag` (no `_Full` suffix) produces `Unknown type 'X'` at compile time. Saline bags don't have an `_Empty/_Full` paired-class structure the way blood bags do — saline tracks state via `Quantity` on a single class. This is a class of bug that ONLY shows up when extending vanilla, and the LLM that writes the code doesn't know which paired-state assumptions are valid until it checks.

Rule: before writing any `modded class X { ... }`, verify X exists in vanilla. The unified `dayz-coder` agent and the Mod Creator have `search_vanilla` and `search_dayz_source` tools for this. Use them. If a search returns no hits, X almost certainly doesn't exist — pick a different (real) class to extend.

The agent-memory under `.claude/agent-memory/dayz-coder/` accumulates per-project hallucination patterns over time. The `_enscript_lint.py` linter at write_file time catches the structural issues; the agent-memory captures the specific class-name mistakes ("for THIS user's saline mod, the class is `SalineBag` not `SalineBag_Full`") so the same mistake isn't made twice.

### `modded class X : Parent {...}` is wrong (still)

Documented elsewhere in this guide as the #1 cause of "my modded class isn't running" — the inheritance clause is silently ignored. The pre-write linter rejects it explicitly.
