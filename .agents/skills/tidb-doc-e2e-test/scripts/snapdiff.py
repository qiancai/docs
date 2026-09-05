#!/usr/bin/env python3
"""Normalize two accessibility snapshots and diff them.

Accepts both snapshot formats:
  - Playwright MCP YAML ("- button \\"Create\\" [ref=...]:")
  - observe_page.py output ("- button \\"Create\\"", same shape without refs)

Denoising principles (from review):
  - Mask by UI CONTEXT, not by value shape. Only lines that are live metrics
    (current usage / current spend / chart values / notification badges) get
    their numbers masked. Limits, defaults, quotas, ports, and plan prices are
    documentation-relevant and are NEVER masked.
  - Only very long numbers (>=13 digits, i.e. resource IDs) are masked
    unconditionally; documented limits like 1048576 survive.
  - Control states stay verbatim: [checked] vs [checked|disabled] is a real
    change.

Diff: multiset-based (occurrence counts matter — a duplicated "Save" button
losing one copy is a change); if multisets are equal but sequences differ,
report ORDER CHANGED (relocation).
Usage: snapdiff.py <old> <new>
"""
import re
import sys
from collections import Counter

# contexts whose numeric content is a live metric, not a documented value
DYNAMIC_CONTEXT_RX = re.compile(
    r"(Current (usage|spend|Spend)|Request Units|Total Connection|"
    r"used this month|consumption|available (storage|quota))", re.I)
BADGE_RX = re.compile(
    r'^- (button|generic|StaticText)( "[^"]*")?\s*"?(Notifications?\s*\d*|Mark all as read)',
    re.I)


def normalize(path):
    lines = []
    with open(path, encoding="utf-8") as fh:
        raw_lines = fh.readlines()
    for raw in raw_lines:
        stripped = raw.rstrip("\n").strip()
        if not stripped.startswith("-"):
            continue
        s = stripped
        s = re.sub(r"\s*\[ref=[^\]]+\]", "", s)
        s = re.sub(r"\s*\[cursor=pointer\]", "", s)
        s = re.sub(r"^-\s*/url:.*$", "", s)
        s = re.sub(r":\s*$", "", s)  # MCP YAML trailing colon for parent nodes
        if not s or s == "-":
            continue
        if BADGE_RX.match(s):
            continue
        # a line that IS a bare measurement (chart/grid cell) is never prose
        if re.match(r'^- (StaticText|generic|paragraph):?\s*"?\d+(\.\d+)?\s*(MiB|GiB|MB|GB|KB)"?\s*$', s):
            continue
        dynamic = bool(DYNAMIC_CONTEXT_RX.search(s))
        # resource IDs are environment-volatile in any context
        s = re.sub(r"\b\d{13,}\b", "<ID>", s)
        if dynamic:
            s = re.sub(r"\b\d+(\.\d+)?\s*(MiB|GiB|MB|GB|KB)\b", "<SIZE>", s)
            s = re.sub(r"\$\d[\d,]*(\.\d+)?", "<AMOUNT>", s)
            s = re.sub(r"\b\d+\b", "<N>", s)
        s = re.sub(r"\b[0-9a-f]{16,}\b", "<HEX>", s, flags=re.I)
        s = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?(\s*[AP]M)?\b", "<TIME>", s, flags=re.I)
        s = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", s)
        lines.append(s)
    return lines


def fmt(line, count):
    return f"{count}× {line.strip()}" if count > 1 else line.strip()


def main():
    old, new = normalize(sys.argv[1]), normalize(sys.argv[2])
    old_c, new_c = Counter(old), Counter(new)
    removed = [(l, old_c[l] - new_c.get(l, 0)) for l in old_c if old_c[l] > new_c.get(l, 0)]
    added = [(l, new_c[l] - old_c.get(l, 0)) for l in new_c if new_c[l] > old_c.get(l, 0)]
    print(f"--- {sys.argv[1]} ({len(old)} normalized lines)")
    print(f"+++ {sys.argv[2]} ({len(new)} normalized lines)")
    if not added and not removed:
        if old != new:
            import difflib
            od = [l for l in difflib.unified_diff(old, new, lineterm="", n=0)
                  if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
            print(f"ORDER CHANGED ({len(od)} positional line changes):")
            for l in od[:20]:
                print(l)
        else:
            print("NO DIFF")
        return
    dialog_hits = [l for l, _ in added + removed if "dialog" in l]
    if dialog_hits:
        print("DIALOG CHANGE:")
        for l, c in added + removed:
            if "dialog" in l:
                print(f"  {'+' if (l, c) in added else '-'} {fmt(l, c)}")
    for l, c in removed:
        print(f"- {fmt(l, c)}")
    for l, c in added:
        print(f"+ {fmt(l, c)}")
    print(f"\n{sum(c for _, c in removed)} removed, {sum(c for _, c in added)} added")


if __name__ == "__main__":
    main()
