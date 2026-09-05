#!/usr/bin/env python3
"""Execute SQL examples from a docs Markdown file against a live TiDB(Cloud)
instance and compare with the expected outputs written in the doc.

Usage: run-sql-test.py <file.md> [--host 127.0.0.1] [--port 4000] [--user root]

Design notes (from review-driven fixes):
- ONE persistent mysql connection per file: session state (USE, session
  variables, transactions) carries across blocks, matching how a reader
  follows a doc. mysql runs with --force so one bad block does not abort the
  rest; per-block errors are drained from stderr via select().
- Blocks tagged ```sql that actually contain a result table (+---...---+
  or | rows) or a mysql> transcript are treated as expected output, not
  executed.
- Non-deterministic statements (RANDOM_BYTES, UUID, NOW, ...) are downgraded
  to weak assertions (row count only).
- Auth: set MYSQL_PWD, or pass --password (avoid on shared machines).
"""
import argparse
import os
import re
import subprocess
import sys

FENCE = re.compile(r"^\s*```(\S*)\s*$")
NONDETERMINISTIC = re.compile(
    r"\b(RANDOM_BYTES|UUID|RAND|NOW|CURDATE|CURTIME|CURRENT_TIMESTAMP|"
    r"CONNECTION_ID|SLEEP)\s*\(", re.I)
# a ```sql block that actually holds a result table (mislabeled output)
LOOKS_LIKE_TABLE = re.compile(r"^\s*(\+[-+]+\+|\|.*\|)\s*$", re.M)
TRANSCRIPT_PROMPT = re.compile(r"^\s*mysql>\s?(.*)$", re.M)
TRANSCRIPT_CONT = re.compile(r"^\s*->\s?(.*)$")


def parse_transcript(content):
    """Parse a mysql> transcript block into [(sql, expected_table)] pairs.

    Statements follow 'mysql>' prompts (continuation lines start with '->');
    everything between statements is the previous statement's output, from
    which a result table is extracted when present ('Query OK' etc. simply
    means no table expectation).
    """
    pairs, cur_sql, cur_out = [], [], []
    for line in content.splitlines():
        m = TRANSCRIPT_PROMPT.match(line)
        if m:
            if cur_sql:
                pairs.append(("\n".join(cur_sql), "\n".join(cur_out)))
            cur_sql, cur_out = [m.group(1)], []
            continue
        c = TRANSCRIPT_CONT.match(line)
        if c and cur_sql and not cur_out:
            cur_sql.append(c.group(1))
            continue
        if cur_sql:
            cur_out.append(line)
    if cur_sql:
        pairs.append(("\n".join(cur_sql), "\n".join(cur_out)))
    return pairs


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
    lines = out.splitlines()
    if not any(re.match(r"^\s*\+[-+]+\+\s*$", l) for l in lines):
        return None
    rows = []
    for l in lines:
        ls = l.strip()
        if ls.startswith("+") or not ls.startswith("|"):
            continue
        rows.append([c.strip() for c in ls.strip("|").split("|")])
    if len(rows) >= 2:
        return {"header": rows[0], "rows": rows[1:]}
    return None


class MySQLSession:
    """One mysql invocation for the whole file: session state (USE, session
    variables, transactions) carries across blocks, matching how a reader
    follows a doc.

    All blocks are sent in ONE write with BEGIN markers, then stdout is split
    per block. (Incremental pipes do not work here: mysql block-buffers its
    stdout when it is not a tty.) Statement errors go to stderr with an
    "at line N" suffix; line offsets are used to attribute errors to blocks.
    """

    def __init__(self, host, port, user, password):
        env = dict(os.environ)
        if password:
            env["MYSQL_PWD"] = password
        ssl = "--ssl-mode=REQUIRED" if host not in ("127.0.0.1", "localhost") else "--ssl-mode=PREFERRED"
        self.cmd = ["mysql", "-h", host, "-P", str(port), "-u", user,
                    "--batch", "--raw", "--binary-as-hex", "--force", ssl]
        self.env = env

    def execute_all(self, sql_blocks):
        marker = "<<<BLOCK>>>"
        combined = []
        block_lines = []  # input line number where each block's SQL starts
        for sql in sql_blocks:
            combined.append(f"SELECT '{marker}' AS __m;")
            block_lines.append(sum(l.count("\n") + 1 for l in combined) + 1)
            combined.append(sql)
        combined.append(f"SELECT '{marker}' AS __m;")
        p = subprocess.run(self.cmd, input="\n".join(combined), capture_output=True,
                           text=True, timeout=300, env=self.env)
        # connection-level failure: no markers at all -> nothing executed
        n_markers = p.stdout.count(marker)
        if n_markers < len(sql_blocks) + 1:
            detail = (p.stderr.strip().splitlines() or ["mysql exited abnormally"])[0]
            raise RuntimeError(
                f"mysql run failed (exit {p.returncode}, {n_markers}/{len(sql_blocks)+1} markers): {detail}")
        # split stdout on marker result sets (header line "__m" + value line)
        segments, cur = [], []
        for line in p.stdout.splitlines():
            if marker in line:
                segments.append("\n".join(cur).strip("\n"))
                cur = []
            elif line.strip() == "__m":
                continue
            else:
                cur.append(line)
        segments.append("\n".join(cur).strip("\n"))
        # segments: [before-first-marker, block0, block1, ..., after-last-marker]
        per_block = segments[1:-1]
        # attribute stderr errors to blocks via "at line N"
        per_err = [[] for _ in sql_blocks]
        for line in p.stderr.splitlines():
            m = re.search(r"at line (\d+)", line)
            if m:
                ln = int(m.group(1))
                for i, start in enumerate(block_lines):
                    end = block_lines[i + 1] if i + 1 < len(block_lines) else 10**9
                    if start <= ln < end:
                        per_err[i].append(line)
                        break
                else:
                    per_err[-1].append(line)
            elif line.strip():
                per_err[-1].append(line)
        return list(zip(per_block, per_err))


def parse_actual(text):
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return {"header": [], "rows": []}
    return {"header": lines[0].split("\t"), "rows": [l.split("\t") for l in lines[1:]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="4000")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default=None)
    args = ap.parse_args()

    password = args.password or os.environ.get("MYSQL_PWD")
    blocks = code_blocks(open(args.file, encoding="utf-8").read())

    # build the execution plan: statement blocks, transcript blocks, and
    # mislabeled output blocks (result tables tagged as sql)
    plan = []
    for i, (lang, content) in enumerate(blocks):
        if lang not in ("sql", "mysql"):
            continue
        if TRANSCRIPT_PROMPT.search(content):
            pairs = parse_transcript(content)
            if not pairs:
                # keep plan alignment with a no-op; reported as NOT-COVERED
                plan.append({"sql": "DO 0;", "expected": None,
                             "note": "NOT-COVERED: unparsable transcript block"})
            for sql, out in pairs:
                plan.append({"sql": sql.strip(), "expected": parse_expected(out),
                             "note": "transcript"})
            continue
        if LOOKS_LIKE_TABLE.search(content) and not re.search(r"^\s*(SELECT|INSERT|CREATE|ALTER|DROP|SET|SHOW|UPDATE|DELETE|WITH|USE|BEGIN|COMMIT|ADMIN|EXPLAIN|VALUES)\b", content, re.I | re.M):
            # mislabeled expected-output block: attach to previous statement
            if plan and plan[-1]["expected"] is None:
                plan[-1]["expected"] = parse_expected(content)
            continue
        expected = None
        if i + 1 < len(blocks) and blocks[i + 1][0] in ("", "text", "output"):
            expected = parse_expected(blocks[i + 1][1])
        plan.append({"sql": content.strip(), "expected": expected})

    session = MySQLSession(args.host, args.port, args.user, password)
    results = []
    try:
        outcomes = session.execute_all([item["sql"] for item in plan])
        if len(outcomes) != len(plan):
            raise RuntimeError(f"result/plan mismatch: {len(outcomes)} vs {len(plan)}")
    except Exception as e:
        for idx, item in enumerate(plan):
            results.append({"n": idx + 1, "sql": item["sql"].replace("\n", " ")[:90],
                            "status": "ENV-BLOCKED", "detail": str(e)})
        outcomes = None
    if outcomes is not None:
        for idx, (item, (out, err_lines)) in enumerate(zip(plan, outcomes)):
            sql, expected = item["sql"], item["expected"]
            entry = {"n": idx + 1, "sql": sql.replace("\n", " ")[:90]}
            note = item.get("note", "")
            if note.startswith("NOT-COVERED"):
                entry.update(status="NOT-COVERED", detail=note)
            elif re.search(r"ERROR \d+", "\n".join(err_lines)):
                entry.update(status="FAIL", detail=err_lines[-1])
            elif expected is None:
                entry.update(status="SMOKE-PASS", detail="no expected output; executed OK")
            else:
                actual = parse_actual(out)
                if NONDETERMINISTIC.search(sql):
                    ok = len(actual["rows"]) == len(expected["rows"])
                    entry.update(status="WEAK-PASS" if ok else "FAIL",
                                 detail="nondeterministic; row count %d vs %d"
                                        % (len(actual["rows"]), len(expected["rows"])))
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
