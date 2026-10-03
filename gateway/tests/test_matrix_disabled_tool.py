"""The custom-harness dimension must switch off a tool the base ACTUALLY HAS.

A tool id that matches nothing in a runtime is dropped on the way through and disables nothing, so
`disabled_tool_unused` is then vacuously true: the row passes a check that is not running. That is
what the single hardcoded `WebSearch` did on eleven of the twenty bases — the six found by the
2026-09-28 sweep and the five added on 2026-10-02, which spell theirs `web_search` / `websearch`.

This test holds `scripts/support-matrix/custom-harness.mjs`'s DISABLED_TOOL table to the gateway's
own `_BASE_CATALOG`, so the next base whose tool ids drift fails HERE rather than quietly going
vacuous in a column nobody re-reads. It is the same arrangement test_console_placeholders.py uses
for the console's model lists: one source of truth, and a test that says so.
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("HR_BACKING", "local")
import app as A  # noqa: E402

MJS = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "support-matrix" / "custom-harness.mjs"
# Tools the stamp task itself needs — it reads a skill, runs its script through a shell and reports
# the line it printed. Switching one of these off would fail the task instead of testing the policy,
# which is a different (and useless) measurement.
_NEEDED = {"shell", "bash", "terminal", "runcommands", "runshellcommand", "exec",
           "read", "readfile", "readfiles", "write", "writefile", "skill"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _table() -> dict:
    src = MJS.read_text()
    body = re.search(r"const DISABLED_TOOL = \{(.*?)\n\};", src, re.S).group(1)
    out = {}
    for m in re.finditer(r"^\s*'?([A-Za-z0-9_-]+)'?:\s*(null|'([^']*)')", body, re.M):
        out[m.group(1)] = None if m.group(2) == "null" else m.group(3)
    return out


def _bases() -> list:
    src = MJS.read_text()
    default = re.search(r"const BASES = \(process\.env\.BASES \|\| '([^']+)'\)", src).group(1)
    return default.split(",")


def test_every_base_the_dimension_runs_has_an_entry():
    table = _table()
    missing = [b for b in _bases() if b not in table]
    assert not missing, f"no disabled tool chosen for: {missing}"


def test_every_chosen_tool_is_one_that_base_really_has():
    table = _table()
    for base, tool in table.items():
        if tool is None:
            continue
        cat = A._BASE_CATALOG[base]
        have = {_norm(t) for t, _label in cat["tools"]}
        assert _norm(tool) in have, (
            f"{base}: the dimension disables {tool!r}, which is not in its catalog "
            f"({sorted(t for t, _ in cat['tools'])}) — the check would pass vacuously")


def test_no_base_switches_off_a_tool_the_task_needs():
    for base, tool in _table().items():
        if tool is not None:
            assert _norm(tool) not in _NEEDED, (
                f"{base}: disabling {tool!r} would fail the stamp task rather than test the policy")


def test_a_base_with_nothing_to_spare_is_null_rather_than_quietly_passing():
    # aider's catalog is one tool, Shell, and the task needs it. The honest answer is that this
    # dimension cannot test the policy there — not a pass.
    table = _table()
    assert table.get("aider", "unset") is None
    assert len([t for t in A._BASE_CATALOG["aider"]["tools"]]) == 1


def test_the_judge_compares_names_rather_than_matching_substrings():
    # The old judge was /websearch/i, which does not match `web_search` at all and would match
    # `search_websearch_history` if one existed. The rule is: ignore case and separators, compare
    # the whole name.
    src = MJS.read_text()
    assert "const sameTool =" in src
    # it survives only in the comment that explains why it went
    assert "/websearch/i" not in re.sub(r"^\s*//.*$", "", src, flags=re.M)
    # and it is the comparison both halves of the claim use
    assert "sameTool(t, off_tool)" in src


def test_a_base_with_no_tool_to_disable_is_not_counted_as_a_pass():
    src = MJS.read_text()
    assert "const toolOk = off_tool === null || (rec.tool_disabled_stored && rec.disabled_tool_unused);" in src
    assert "rec.disabled_tool = off_tool;" in src   # the row says WHICH tool, or the claim is unreadable
