#!/usr/bin/env python3
"""Normalize Playwright a11y snapshots and diff two of them.

Normalization rules (intentionally minimal — 3 rules):
  R1: strip refs/cursor attributes and URL values
  R2: mask numbers, dates, times, hex ids
  R3: drop known-volatile lines (status words, metrics, notifications)

Diff: set-based added/removed lines after normalization.
Usage: snapdiff.py <old.yml> <new.yml>
"""
import re
import sys


def normalize(path):
    lines = []
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip().startswith("-"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        # R1: strip refs and attributes
        s = re.sub(r"\s*\[ref=[^\]]+\]", "", s)
        s = re.sub(r"\s*\[cursor=pointer\]", "", s)
        s = re.sub(r"\s*\[(checked|disabled|active|selected)\]", r" [STATE]", s)
        s = re.sub(r"^-\s*/url:.*$", "", s)
        if not s or s == "-":
            continue
        # R2: mask volatile values
        s = re.sub(r"\b\d{4,}\b", "<NUM>", s)                       # long numbers / ids
        s = re.sub(r"\d+(\.\d+)?\s*(MiB|GiB|MB|GB|RCUs?)\b", "<NUM>", s)
        s = re.sub(r"\$\d[\d,]*(\.\d+)?", "<PRICE>", s)
        s = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", "<TIME>", s)
        s = re.sub(r"\b\d+\b", "<N>", s)                            # remaining small ints
        # R3: drop known-volatile content lines
        if re.search(r"(Creating|Active|Deleting|Notifications?\b|Request Units|Total Connection|capacity|spend)", s, re.I):
            continue
        lines.append(s)  # content only — indentation intentionally dropped
    return lines


def main():
    old, new = normalize(sys.argv[1]), normalize(sys.argv[2])
    old_set, new_set = set(old), set(new)
    added = [l for l in new if l not in old_set]
    removed = [l for l in old if l not in new_set]
    # dedupe while keeping order
    seen = set()
    added = [l for l in added if not (l in seen or seen.add(l))]
    seen = set()
    removed = [l for l in removed if not (l in seen or seen.add(l))]
    print(f"--- {sys.argv[1]} ({len(old)} normalized lines)")
    print(f"+++ {sys.argv[2]} ({len(new)} normalized lines)")
    if not added and not removed:
        if old != new:
            # same content, different order -> relocation
            import difflib
            od = [l for l in difflib.unified_diff(old, new, lineterm="", n=0) if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
            print(f"ORDER CHANGED ({len(od)} positional line changes):")
            for l in od[:20]:
                print(l)
        else:
            print("NO DIFF")
        return
    # dialog appearing/covering makes the diff huge: surface it first
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
