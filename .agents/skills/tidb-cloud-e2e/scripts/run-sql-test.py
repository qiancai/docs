#!/usr/bin/env python3
"""Execute SQL examples from a docs Markdown file against a live TiDB(Cloud)
instance and compare with the expected outputs written in the doc.

Usage: run-sql-test.py <file.md> [--host 127.0.0.1] [--port 4000] [--user root]

- SQL blocks run in document order against the same instance (state shared).
- A following fenced block that looks like a result table is treated as the
  expected output and compared cell-by-cell.
- Non-deterministic statements (RANDOM_BYTES, UUID, NOW, ...) are downgraded
  to weak assertions (row count only).
- Requires the mysql client; set MYSQL_PWD or use --ask-pass for password auth.
"""
import argparse
import re
import subprocess
import sys

FENCE = re.compile(r"^\s*```(\S*)\s*$")
NONDETERMINISTIC = re.compile(
    r"\b(RANDOM_BYTES|UUID|RAND|NOW|CURDATE|CURTIME|CURRENT_TIMESTAMP|"
    r"CONNECTION_ID|SLEEP)\s*\(", re.I)


def code_blocks(text):
    blocks, in_block, lang, buf = [], False, "", []
    for line in text.splitlines():
        m = FENCE.match(line)
        if m:
            if in_block:
                blocks.append((lang, "\n".join(buf)))
                in_block, buf = False, []
            else:
                in_block, lang = True, m.group(1).lower()
        elif in_block:
            buf.append(line)
    return blocks


def parse_expected(out):
    """Parse a doc output block into {'rows': [[cell,...],...]} or None."""
    lines = out.splitlines()
    if not any(re.match(r"^\s*\+[-+]+\+\s*$", l) for l in lines):
        return None  # not a table output
    rows = []
    for l in lines:
        ls = l.strip()
        if ls.startswith("+") or not ls.startswith("|"):
            continue
        cells = [c.strip() for c in ls.strip("|").split("|")]
        rows.append(cells)
    if len(rows) >= 2:
        return {"header": rows[0], "rows": rows[1:]}
    return None


def run_sql(sql, host, port, user, password):
    cmd = ["mysql", "-h", host, "-P", str(port), "-u", user,
           "--batch", "--raw", "--binary-as-hex", "-e", sql]
    if password:
        cmd.insert(1, "-p" + password)
    env = None
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    return p.returncode, p.stdout, p.stderr


def parse_actual(tsv):
    lines = [l for l in tsv.splitlines() if l.strip()]
    if not lines:
        return {"header": [], "rows": []}
    return {"header": lines[0].split("\t"), "rows": [l.split("\t") for l in lines[1:]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="4000")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default=None,
                    help="prefer the MYSQL_PWD env var over this flag")
    args = ap.parse_args()

    import os
    password = args.password or os.environ.get("MYSQL_PWD")

    text = open(args.file, encoding="utf-8").read()
    blocks = code_blocks(text)
    results = []
    for i, (lang, content) in enumerate(blocks):
        if lang not in ("sql", "mysql"):
            continue
        sql = content.strip()
        expected = None
        if i + 1 < len(blocks) and blocks[i + 1][0] in ("", "text", "output"):
            expected = parse_expected(blocks[i + 1][1])
        rc, out, err = run_sql(sql, args.host, args.port, args.user, password)
        entry = {"n": len(results) + 1, "sql": sql.replace("\n", " ")[:90]}
        if rc != 0:
            entry.update(status="ERROR", detail=err.strip().splitlines()[-1] if err.strip() else "unknown")
        elif expected is None:
            entry.update(status="SMOKE-PASS", detail="no expected output; executed OK")
        else:
            actual = parse_actual(out)
            if NONDETERMINISTIC.search(sql):
                ok = len(actual["rows"]) == len(expected["rows"])
                entry.update(status="WEAK-PASS" if ok else "FAIL",
                             detail="nondeterministic; row count %d vs %d" % (len(actual["rows"]), len(expected["rows"])))
            elif actual["rows"] == expected["rows"]:
                entry.update(status="PASS", detail="%d row(s) match" % len(actual["rows"]))
            else:
                entry.update(status="FAIL",
                             detail="expected %r got %r" % (expected["rows"], actual["rows"]))
        results.append(entry)

    npass = sum(1 for r in results if r["status"] in ("PASS", "WEAK-PASS", "SMOKE-PASS"))
    print(f"# {args.file}: {npass}/{len(results)} blocks OK\n")
    for r in results:
        print(f"[{r['status']}] #{r['n']} {r['sql']}")
        print(f"    -> {r['detail']}")
    sys.exit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()
