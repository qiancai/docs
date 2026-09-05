#!/usr/bin/env python3
"""Normalize two accessibility snapshots and diff them.

Accepts both snapshot formats:
  - Playwright MCP YAML ("- button \\"Create\\" [ref=...]:")
  - observe_page.py output ("- button \\"Create\\"", same shape without refs)

Normalization rules (kept deliberately narrow — denoising must never hide
documentation-relevant changes such as port numbers, defaults, or the
appearance/disappearance of a control):
  R1: strip refs/cursor attributes and URL values
  R2: mask only high-entropy values: long ids (>=6 digits), hex strings,
      prices, times, dates, usage sizes
  R3: drop only proven-volatile lines: notification badges and live metric
      chart values

Diff: set-based added/removed lines after normalization; if content sets are
equal but sequences differ, report ORDER CHANGED (relocation).
Usage: snapdiff.py <old> <new>
"""
import re
import sys


def normalize(path):
    lines = []
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        s = stripped
        s = re.sub(r"\s*\[ref=[^\]]+\]", "", s)
        s = re.sub(r"\s*\[cursor=pointer\]", "", s)
        s = re.sub(r"\s*\[(checked|disabled|active|selected)(\|[^\]]*)?\]", r" [STATE]", s)
        s = re.sub(r"^-\s*/url:.*$", "", s)
        s = re.sub(r":\s*$", "", s)  # MCP YAML trailing colon for parent nodes
        if not s or s == "-":
            continue
        # R2: mask only high-entropy values
        s = re.sub(r"\b\d{6,}\b", "<ID>", s)                        # instance ids, long numbers
        s = re.sub(r"\b[0-9a-f]{16,}\b", "<HEX>", s, flags=re.I)    # hex tokens
        s = re.sub(r"\$\d[\d,]*(\.\d+)?", "<PRICE>", s)             # prices
        s = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?(\s*[AP]M)?\b", "<TIME>", s, flags=re.I)
        s = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", s)
        s = re.sub(r"\b\d+(\.\d+)?\s*(MiB|GiB|MB|GB|KB)\b", "<SIZE>", s)  # usage meters
        # R3: drop proven-volatile lines only
        if re.match(r'^- (button|generic|StaticText)( ".*?")?\s*"?(Notifications?\s*\d*|Mark all as read)', s, re.I):
            continue
        if re.match(r'^- (StaticText|generic):?\s*"<SIZE>"\s*$', s):
            continue
        lines.append(s)
    return lines


def main():
    old, new = normalize(sys.argv[1]), normalize(sys.argv[2])
    old_set, new_set = set(old), set(new)
    added = [l for l in new if l not in old_set]
    removed = [l for l in old if l not in new_set]
    seen = set()
    added = [l for l in added if not (l in seen or seen.add(l))]
    seen = set()
    removed = [l for l in removed if not (l in seen or seen.add(l))]
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
    dialog_hits = [l for l in added + removed if "dialog" in l]
    if dialog_hits:
        print("DIALOG CHANGE:")
        for l in dialog_hits:
            sign = "+" if l in added else "-"
            print(f"  {sign} {l.strip()}")
    for l in removed:
        print(f"- {l.strip()}")
    for l in added:
        print(f"+ {l.strip()}")
    print(f"\n{len(removed)} removed, {len(added)} added")


if __name__ == "__main__":
    main()
