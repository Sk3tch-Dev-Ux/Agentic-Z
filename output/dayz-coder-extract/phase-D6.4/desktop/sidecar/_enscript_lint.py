"""Pre-write Enforce Script linter for the Mod Creator.

Run on every `.c` file BEFORE write_file commits to disk. If errors are found
the tool_result returned to Claude tells it exactly what's wrong, and Claude
rewrites the file in the same Mod Creator run — no second compile cycle, no
user staring at a "Compile error" dialog.

The rules encoded here come from real Mod Creator failures. Each one
references the failure mode it prevents.

Add a new rule by:
  1. Add a function `_check_<name>(content, errors) -> None`
  2. Call it from `lint_enscript_source()`
  3. Update the canonical doc at .claude/skills/_shared/enscript-style.md so
     other agents (and future devs) learn from the same lesson.
"""
import re
from typing import Optional


# Bytes that look like ASCII but aren't (the "smart quote" / em dash family).
# Listed individually so error messages can name them specifically.
SMART_PUNCTUATION = {
    "—": ("em dash", "use a plain hyphen `-` or `--`"),
    "–": ("en dash", "use a plain hyphen `-`"),
    "‘": ("left single curly quote", "use straight `'`"),
    "’": ("right single curly quote / apostrophe", "use straight `'`"),
    "“": ("left double curly quote", "use straight `\"`"),
    "”": ("right double curly quote", "use straight `\"`"),
    "…": ("ellipsis", "use `...`"),
    "•": ("bullet", "use `*` or `-`"),
    " ": ("non-breaking space", "use a regular space"),
    "→": ("right arrow", "use `->`"),
}


def _check_ascii_only(content: str, errors: list) -> None:
    """Rule 1: Enforce Script's parser breaks on non-ASCII characters even
    inside string literals. The mojibake of an em dash (UTF-8 E2 80 94) read
    as Windows-1252 produces "Expected ',' or ')'" parse errors that point at
    the WHOLE STRING, not the offending character — confusing to debug.
    Reject any non-ASCII at write time.
    """
    for line_num, line in enumerate(content.splitlines(), start=1):
        for col, char in enumerate(line, start=1):
            if ord(char) > 127:
                hint = SMART_PUNCTUATION.get(char,
                    (f"non-ASCII character", "use plain ASCII"))
                name, fix = hint
                errors.append(
                    f"line {line_num}, col {col}: {name} ({char!r}, U+{ord(char):04X}). "
                    f"Enforce Script's parser breaks on non-ASCII even in strings. "
                    f"Fix: {fix}."
                )
                break  # one error per line is enough


# Lines ending with these tokens are continuations the parser may not handle
# inside a function-call argument list.
_CONTINUATION_END = re.compile(r"[\+\-\*/,]\s*$")
# Open paren followed by a string literal that doesn't close on this line.
_OPEN_CALL_WITH_OPEN_STRING = re.compile(r'\b\w+\s*\(\s*"[^"]*$')


_LEADING_CONTINUATION = re.compile(r"^\s*[\+\-\*/,]")


def _check_no_multiline_call_args(content: str, errors: list) -> None:
    """Rule 2: Enforce Script's parser doesn't reliably handle expressions
    that span multiple lines INSIDE function-call argument lists. Symptom:
    "Expected ',' or ')'" pointing at the first string literal of a Print()
    call when the call is split across lines.

    Detection: track open-paren depth across lines. If a line is non-empty
    and starts with a continuation operator (`+`, `-`, `*`, `/`, `,`) while
    we're still inside an unclosed `(`, that's the broken pattern.

    The fix Claude should apply: build the value into a `string` (or other
    typed) variable on its own line, then pass that variable to the call.
    """
    lines = content.splitlines()
    depth = 0
    for i, raw in enumerate(lines):
        # If we're already inside an open call AND this line starts with a
        # continuation operator, flag it.
        if depth > 0 and _LEADING_CONTINUATION.match(raw):
            errors.append(
                f"line {i+1}: continues a `(...)` argument list across lines. "
                f"Enforce Script's parser breaks on this — produces \"Expected "
                f"',' or ')'\" pointing at the prior line's string. Build the "
                f"value into a typed local first, then pass the variable. "
                f"Example: `string msg = \"a\" + foo + \"b\"; Print(msg);` "
                f"instead of `Print(\"a\" + foo + \"b\");` split across lines."
            )
            # Don't double-report once flagged; advance past this depth window.
            depth = 0
            continue
        # Track depth across the rest of the file. Naive — doesn't handle parens
        # inside string literals, but that's fine for the common case.
        # Strip line comments first so `(` / `)` inside `//` don't count.
        s = raw
        if "//" in s:
            s = s[: s.index("//")]
        depth += s.count("(") - s.count(")")
        if depth < 0:
            depth = 0  # stray `)` — ignore


_MODDED_WITH_INHERITANCE = re.compile(
    r"^\s*modded\s+class\s+\w+\s*:\s*\w",
    re.MULTILINE,
)


def _check_modded_class_no_inheritance(content: str, errors: list) -> None:
    """Rule 3: `modded class X : Parent {...}` is wrong. The inheritance
    clause is silently ignored — modded class already inherits from the
    original. Including the clause makes the code misleading.

    EnScript style guide (`.claude/skills/_shared/enscript-style.md`) calls
    this out as the #1 cause of "my modded class isn't running" silent bugs.
    """
    for m in _MODDED_WITH_INHERITANCE.finditer(content):
        line_num = content.count("\n", 0, m.start()) + 1
        errors.append(
            f"line {line_num}: `modded class` declaration has an inheritance "
            f"clause. Drop the `: Parent` part — modded class already inherits "
            f"from the original."
        )


def lint_enscript_source(content: str, path: Optional[str] = None) -> list:
    """Run all rules. Returns a list of human-readable error strings.
    Empty list means the file is OK to write.

    Only call this on `.c` files (Enforce Script). Configs (`.cpp`),
    layouts (`.layout`), and others have different rules and shouldn't be
    forced through this checker.
    """
    errors: list = []
    if path and not path.endswith(".c"):
        return errors  # only lint Enforce Script
    _check_ascii_only(content, errors)
    _check_no_multiline_call_args(content, errors)
    _check_modded_class_no_inheritance(content, errors)
    return errors


# Quick self-test (run with `python _enscript_lint.py`)
if __name__ == "__main__":
    cases = [
        ("ASCII-only OK",
         "modded class SalineBag\n{\n    void Foo() { Print(\"hi\"); }\n}\n",
         0),
        ("em dash in comment",
         "// SalineHealing — header\nclass X {}\n",
         1),
        ("em dash in string",
         "Print(\"a — b\");\n",
         1),
        ("multi-line Print",
         "void F()\n{\n  Print(\"a \"\n    + foo + \" b\");\n}\n",
         1),
        ("modded class with inheritance",
         "modded class PlayerBase : ManBase\n{\n}\n",
         1),
    ]
    fail = 0
    for label, src, expected in cases:
        errs = lint_enscript_source(src, path="test.c")
        ok = len(errs) == expected
        marker = "[OK]" if ok else "[FAIL]"
        print(f"{marker} {label}: expected {expected} errors, got {len(errs)}")
        if not ok:
            fail += 1
            for e in errs:
                print(f"        - {e}")
    raise SystemExit(fail)
