#!/usr/bin/env python3
"""Scan docs Markdown files, count SQL code blocks, and score automatability.

Usage: scan-sql-blocks.py [repo-root]   (defaults to current directory)
Output: per-directory aggregates + top files; writes files.csv next to the script output dir.

Used to plan reference-doc partitioning (see ref-tidb.md) and to prioritize
which docs to test first (exact > weak > smoke).
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

SCAN_DIRS = ["sql-statements", "functions-and-operators", "develop", "information-schema", "ai"]
ROOT_FILES_SKIP = re.compile(
    r"^(TOC|_index|_docHome|README|CONTRIBUTING|AGENTS|support|credits|"
    r".*-deployment\.md|scale-.*|upgrade-.*|deploy-.*|troubleshoot-.*|"
    r".*configuration-file\.md|command-line-flags.*|enable-tls.*|"
    r".*monitoring.*|alert-rules|tune-.*|release-.*)")

FENCE_LINE_RE = re.compile(r"^\s*```(\S*)\s*$")
OUT_HINT = re.compile(r"(Query OK|\+\-|\|.*\||ERROR \d+|Empty set|rows? in set)", re.M | re.I)
MYSQL_PROMPT = re.compile(r"^\s*mysql>", re.M)
ENV_KW = re.compile(
    r"(\bBACKUP\b|\bRESTORE\b|IMPORT INTO|LOAD DATA|TIFLASH|FLASHBACK|"
    r"s3://|local://|/tmp/|tiup |dumpling|changefeed)", re.I)
STMT_RE = {
    "select": re.compile(r"^\s*(SELECT|WITH|VALUES)\b", re.I | re.M),
    "show": re.compile(r"^\s*(SHOW|DESC|DESCRIBE)\b", re.I | re.M),
    "explain": re.compile(r"^\s*(EXPLAIN|TRACE)\b", re.I | re.M),
    "ddl": re.compile(r"^\s*(CREATE|ALTER|DROP|TRUNCATE|RENAME)\b", re.I | re.M),
    "dml": re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b", re.I | re.M),
    "set": re.compile(r"^\s*SET\b", re.I | re.M),
    "admin": re.compile(r"^\s*ADMIN\b", re.I | re.M),
    "txn": re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK|START TRANSACTION)\b", re.I | re.M),
}


def code_blocks(text):
    """Line-based toggle parser: handles ```lang+x tags and indented fences."""
    blocks, in_block, lang, buf = [], False, "", []
    for line in text.splitlines():
        m = FENCE_LINE_RE.match(line)
        if m:
            if in_block:
                blocks.append((lang, "\n".join(buf)))
                in_block, buf = False, []
            else:
                in_block, lang = True, m.group(1).lower()
        elif in_block:
            buf.append(line)
    return blocks


def stmt_types(sql):
    types = {name for name, rx in STMT_RE.items() if rx.search(sql)}
    return types or {"other"}


def analyze_file(path):
    text = open(path, encoding="utf-8").read()
    blocks = code_blocks(text)
    stats = Counter()
    types = Counter()
    env_hits = set()
    sql_idx = [i for i, (lang, _) in enumerate(blocks) if lang in ("sql", "mysql")]
    stats["sql_blocks"] = len(sql_idx)
    for i in sql_idx:
        content = blocks[i][1]
        has_out = bool(MYSQL_PROMPT.search(content))
        if not has_out and i + 1 < len(blocks):
            nlang, ncontent = blocks[i + 1]
            if nlang in ("", "text", "shell", "console", "output") and OUT_HINT.search(ncontent):
                has_out = True
        ts = stmt_types(content)
        for t in ts:
            types[t] += 1
        if has_out and ts <= {"select"}:
            stats["exact"] += 1
        elif has_out:
            stats["weak"] += 1
        else:
            stats["smoke"] += 1
        env_hits.update(ENV_KW.findall(content))
    if any(ENV_KW.search(c) for lang, c in blocks if lang in ("shell", "bash", "sh")):
        env_hits.add("shell-steps")
    score = stats["exact"] * 3 + stats["weak"] * 2 + stats["smoke"]
    return stats, types, sorted(env_hits), score


def single_file_mode(path):
    """Per-block inventory for one Markdown file: index, line range, language,
    statement types, env deps, and first content line — the input for
    reference-doc test-case partitioning."""
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    blocks = []
    in_block, lang, buf, start = False, "", [], 0
    for ln, line in enumerate(lines, 1):
        m = FENCE_LINE_RE.match(line)
        if m:
            if in_block:
                blocks.append((lang, "\n".join(buf), start, ln))
                in_block, buf = False, []
            else:
                in_block, lang, start = True, m.group(1).lower(), ln
        elif in_block:
            buf.append(line)
    n = 0
    for lang, content, start, end in blocks:
        if lang not in ("sql", "mysql"):
            continue
        n += 1
        first = next((l.strip() for l in content.splitlines() if l.strip()), "")
        kind = "output-table" if re.match(r"^\s*(\+[-+]+\+|\|.*\|)", content) else \
               "transcript" if TRANSCRIPT_RX.search(content) else "statements"
        types = "|".join(sorted(stmt_types(content))) if kind == "statements" else "-"
        env = "|".join(sorted(set(ENV_KW.findall(content)))) or "-"
        print(f"[{n}] lines {start}-{end}  {kind:<13} types={types:<28} env={env}")
        print(f"    {first[:100]}")
    print(f"\n{n} SQL blocks in {path}")


TRANSCRIPT_RX = re.compile(r"^\s*mysql>", re.M)


def main():
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        single_file_mode(sys.argv[1])
        return
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    targets = []
    for d in SCAN_DIRS:
        dpath = os.path.join(root, d)
        if os.path.isdir(dpath):
            targets += [os.path.join(d, f) for f in sorted(os.listdir(dpath))
                        if f.endswith(".md") and not f.startswith("_")]
    for f in sorted(os.listdir(root)):
        if f.endswith(".md") and not ROOT_FILES_SKIP.match(f) and not f.startswith("TOC"):
            targets.append(f)

    rows = []
    dir_agg = defaultdict(Counter)
    for rel in targets:
        stats, types, env, score = analyze_file(os.path.join(root, rel))
        if stats["sql_blocks"] == 0:
            continue
        rows.append({
            "file": rel, "sql_blocks": stats["sql_blocks"],
            "exact_cmp": stats["exact"], "weak_assert": stats["weak"],
            "smoke_only": stats["smoke"],
            "stmt_types": "|".join(f"{k}:{v}" for k, v in types.most_common()),
            "env_deps": "|".join(env), "score": score})
        d = os.path.dirname(rel) or "(root)"
        dir_agg[d].update({"files": 1, "sql_blocks": stats["sql_blocks"],
                           "exact": stats["exact"], "weak": stats["weak"],
                           "smoke": stats["smoke"], "score": score})
    rows.sort(key=lambda r: (-r["score"], r["file"]))

    outdir = os.path.join(root, ".tmp", "sql-block-stats")
    os.makedirs(outdir, exist_ok=True)
    if rows:
        with open(os.path.join(outdir, "files.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"total files with SQL: {len(rows)}  (csv: {outdir}/files.csv)")
    print(f"{'dir':<28}{'files':>6}{'sql':>6}{'exact':>7}{'weak':>6}{'smoke':>7}{'score':>8}")
    for d, c in sorted(dir_agg.items(), key=lambda kv: -kv[1]["score"]):
        print(f"{d:<28}{c['files']:>6}{c['sql_blocks']:>6}{c['exact']:>7}{c['weak']:>6}{c['smoke']:>7}{c['score']:>8}")
    print("\nTOP 20 files by automation score:")
    for r in rows[:20]:
        print(f"{r['score']:>5}  {r['file']:<62} sql={r['sql_blocks']:<3} exact={r['exact_cmp']:<3} weak={r['weak_assert']:<3} smoke={r['smoke_only']:<3} env={r['env_deps'] or '-'}")


if __name__ == "__main__":
    main()
