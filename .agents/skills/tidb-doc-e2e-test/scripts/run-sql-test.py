#!/usr/bin/env python3
"""Execute SQL examples from a docs Markdown file (or a case plan) against a
live TiDB/TiDB Cloud instance and compare with documented expectations.

Usage:
  run-sql-test.py <file.md> [options]
  run-sql-test.py --case-plan plan.json [options]

Harness vocabulary (kept neutral — the agent assigns the final verdict):
  execution: completed | error | refused | blocked
  assertion: {type: exact|exact-unordered|row-count|smoke|expected-error,
              result: match | mismatch | none}
This script never claims DOC-DISCREPANCY/PASS — that is the agent's job.

Key properties:
- Mutation policy is enforced HERE, not in the prompt: --mutation-policy
  read-only (default) refuses DDL/DML/global writes; sandbox allows writes on
  disposable environments; unrestricted allows everything. Global settings and
  user management additionally require --allow-global-setting.
- One mysql invocation per test case; session state (USE, session variables,
  transactions) carries across blocks within a case. With --case-plan, each
  case gets a FRESH connection (cross-case isolation).
- Expected errors are first-class: a doc output block containing
  "ERROR 1146 (42S02): ..." makes the preceding statement an expected-error
  assertion. Case plans may specify error_code / error_contains explicitly.
- mysql> transcript blocks are parsed into executable statements.
- Result-table blocks mislabeled as ```sql are treated as expected output.

Auth: set MYSQL_PWD, or pass --password (avoid on shared machines).
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from markdown_sql import (code_blocks, classify_block, parse_transcript,
                          parse_expected, parse_expected_error, stmt_types,
                          NONDETERMINISTIC, tables_equal, norm_cell)

WRITE_RX = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE|RENAME|"
    r"GRANT|REVOKE|ANALYZE|BACKUP|RESTORE|IMPORT|LOAD\s+DATA)\b", re.I | re.M)
GLOBAL_RX = re.compile(
    r"(^\s*SET\s+(GLOBAL|@@global\.)|^\s*(CREATE|ALTER|DROP)\s+(USER|ROLE)\b|"
    r"^\s*(GRANT|REVOKE)\b)", re.I | re.M)


def mutation_risk(sql):
    """-> 'read' | 'write' | 'global'"""
    if GLOBAL_RX.search(sql):
        return "global"
    if WRITE_RX.search(sql):
        return "write"
    return "read"


def allowed_by_policy(risk, policy, allow_global):
    if policy == "unrestricted":
        return True
    if risk == "read":
        return True
    if risk == "global":
        return allow_global
    return policy == "sandbox"  # write


class MySQLCase:
    """One mysql invocation per case: all blocks sent in ONE write with
    markers, stdout split per block (mysql block-buffers non-tty stdout, so
    incremental pipes do not work). Errors are attributed via 'at line N'."""

    def __init__(self, host, port, user, password):
        env = dict(os.environ)
        if password:
            env["MYSQL_PWD"] = password
        ssl = "--ssl-mode=REQUIRED" if host not in ("127.0.0.1", "localhost") else "--ssl-mode=PREFERRED"
        self.cmd = ["mysql", "-h", host, "-P", str(port), "-u", user,
                    "--batch", "--raw", "--binary-as-hex", "--force", ssl]
        self.env = env

    def run_case(self, sql_blocks):
        marker = "<<<BLOCK>>>"
        combined, block_lines = [], []
        for sql in sql_blocks:
            combined.append(f"SELECT '{marker}' AS __m;")
            block_lines.append(sum(l.count("\n") + 1 for l in combined) + 1)
            # always terminate the block: docs/case plans may omit the final ';',
            # otherwise the statement bleeds into the next marker
            combined.append(sql.rstrip() + "\n;")
        combined.append(f"SELECT '{marker}' AS __m;")
        p = subprocess.run(self.cmd, input="\n".join(combined), capture_output=True,
                           text=True, timeout=300, env=self.env)
        n_markers = p.stdout.count(marker)
        if n_markers < len(sql_blocks) + 1:
            detail = (p.stderr.strip().splitlines() or ["mysql exited abnormally"])[0]
            raise RuntimeError(
                f"mysql run failed (exit {p.returncode}, {n_markers}/{len(sql_blocks)+1} markers): {detail}")
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
        per_block = segments[1:-1]
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


def plan_from_markdown(path):
    """Blocks -> plan items: {sql, expected(table|None), expected_error(dict|None),
    note}. Transcripts expand to one item per statement; mislabeled result tables
    and ERROR output blocks attach to the previous statement."""
    blocks = code_blocks(open(path, encoding="utf-8").read())
    plan = []

    def attach_output(content):
        if not plan:
            return
        last = plan[-1]
        err = parse_expected_error(content)
        if err and last["expected"] is None and last["expected_error"] is None:
            last["expected_error"] = err
        elif last["expected"] is None and last["expected_error"] is None:
            last["expected"] = parse_expected(content)

    for i, (lang, content, start, end) in enumerate(blocks):
        if lang not in ("sql", "mysql"):
            continue
        kind = classify_block(content)
        if kind == "transcript":
            pairs = parse_transcript(content)
            if not pairs:
                plan.append({"sql": "DO 0;", "expected": None, "expected_error": None,
                             "note": "NOT-COVERED: unparsable transcript block"})
            for sql, out in pairs:
                err = parse_expected_error(out)
                plan.append({"sql": sql.strip(),
                             "expected": None if err else parse_expected(out),
                             "expected_error": err, "note": "transcript"})
            continue
        if kind == "output-table":
            attach_output(content)
            continue
        expected, expected_error = None, None
        if i + 1 < len(blocks) and blocks[i + 1][0] in ("", "text", "output"):
            nxt = blocks[i + 1][1]
            expected_error = parse_expected_error(nxt)
            if not expected_error:
                expected = parse_expected(nxt)
        plan.append({"sql": content.strip(), "expected": expected,
                     "expected_error": expected_error, "note": ""})
    return plan


def plan_from_case_file(path):
    """Case plan JSON: {'cases': [{'id', 'source_lines', 'items': [{'sql',
    'expected_header', 'expected_rows', 'expected_error_code',
    'expected_error_contains', 'assertion'}]}]} -> (cases, plan-with-case-idx)"""
    data = json.load(open(path, encoding="utf-8"))
    cases, plan = [], []
    for ci, case in enumerate(data.get("cases", [])):
        cases.append({"id": case.get("id", f"case-{ci+1}"), "n_items": len(case.get("items", []))})
        for item in case.get("items", []):
            expected = None
            if "expected_rows" in item:
                expected = {"header": item.get("expected_header", []),
                            "rows": item["expected_rows"]}
            expected_error = None
            if "expected_error_code" in item:
                expected_error = {"code": str(item["expected_error_code"]),
                                  "sqlstate": item.get("expected_error_sqlstate"),
                                  "message": item.get("expected_error_contains", "")}
            plan.append({"sql": item["sql"], "expected": expected,
                         "expected_error": expected_error,
                         "assertion": item.get("assertion"),
                         "note": "", "case": ci})
    return cases, plan


def judge(item, out, err_lines):
    """-> (execution, assertion_type, assertion_result, detail)"""
    err = "\n".join(err_lines)
    err_m = re.search(r"ERROR (\d+) \((\w+)\)", err)

    if item.get("note", "").startswith("NOT-COVERED"):
        return "completed", "none", "none", item["note"]

    if item["expected_error"]:
        exp = item["expected_error"]
        if not err_m:
            return "completed", "expected-error", "mismatch", \
                f"expected ERROR {exp['code']} but statement succeeded"
        code, sqlstate = err_m.group(1), err_m.group(2)
        if code == exp["code"] or (exp.get("sqlstate") and sqlstate == exp["sqlstate"]):
            if exp.get("message") and exp["message"] not in err:
                return "completed", "expected-error", "mismatch", \
                    f"error code matches but message differs: {err.strip()[:120]}"
            return "completed", "expected-error", "match", f"got documented ERROR {code}"
        return "completed", "expected-error", "mismatch", \
            f"expected ERROR {exp['code']}, got ERROR {code}: {err.strip()[:120]}"

    if err_m:
        return "error", "none", "none", err.strip().splitlines()[-1][:200]

    if item["expected"] is None:
        return "completed", "smoke", "none", "no expected output; executed OK"

    actual = parse_actual(out)
    atype = item.get("assertion") or \
        ("row-count" if NONDETERMINISTIC.search(item["sql"]) else "exact")
    if atype == "row-count":
        ok = len(actual["rows"]) == len(item["expected"]["rows"])
        return "completed", "row-count", "match" if ok else "mismatch", \
            "row count %d vs %d" % (len(actual["rows"]), len(item["expected"]["rows"]))
    if atype == "exact-unordered":
        ok = sorted(map(tuple, actual["rows"])) == sorted(map(tuple, item["expected"]["rows"]))
        return "completed", "exact-unordered", "match" if ok else "mismatch", \
            "row sets %s" % ("match" if ok else "differ")
    ok, where = tables_equal(item["expected"], actual,
                             compare_header=bool(item["expected"]["header"]))
    if ok:
        return "completed", "exact", "match", "%d row(s) + header match" % len(actual["rows"])
    return "completed", "exact", "mismatch", \
        f"{where} differ: expected %r got %r" % (
            item["expected"]["header"] if where == "header" else item["expected"]["rows"],
            actual["header"] if where == "header" else actual["rows"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--case-plan", help="JSON case plan; each case runs on a fresh connection")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="4000")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default=None)
    ap.add_argument("--mutation-policy", choices=["read-only", "sandbox", "unrestricted"],
                    default="read-only",
                    help="read-only refuses writes; sandbox allows DDL/DML on disposable envs; "
                         "unrestricted allows everything (still see --allow-global-setting)")
    ap.add_argument("--allow-global-setting", action="store_true",
                    help="allow SET GLOBAL / user management even under sandbox")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    if not args.file and not args.case_plan:
        ap.error("need a markdown file or --case-plan")

    password = args.password or os.environ.get("MYSQL_PWD")

    if args.case_plan:
        cases, plan = plan_from_case_file(args.case_plan)
    else:
        plan = plan_from_markdown(args.file)
        cases = [{"id": os.path.basename(args.file), "n_items": len(plan)}]

    # policy screening happens BEFORE anything executes
    for item in plan:
        risk = mutation_risk(item["sql"])
        if not allowed_by_policy(risk, args.mutation_policy, args.allow_global_setting):
            item["refused"] = f"{risk} statement refused by --mutation-policy {args.mutation_policy}"

    session = MySQLCase(args.host, args.port, args.user, password)
    results, blocked_exc = [], None
    if args.case_plan:
        outcomes = [None] * len(plan)
        try:
            for ci, case in enumerate(cases):
                idxs = [i for i, it in enumerate(plan) if it.get("case") == ci]
                batch_res = session.run_case([plan[i]["sql"] for i in idxs])
                for i, r in zip(idxs, batch_res):
                    outcomes[i] = r
        except Exception as e:
            blocked_exc = e
    else:
        try:
            outcomes = session.run_case([item["sql"] for item in plan])
            if len(outcomes) != len(plan):
                raise RuntimeError(f"result/plan mismatch: {len(outcomes)} vs {len(plan)}")
        except Exception as e:
            blocked_exc = e

    for idx, item in enumerate(plan):
        entry = {"n": idx + 1, "sql": item["sql"].replace("\n", " ")[:90]}
        if blocked_exc is not None:
            entry.update(execution="blocked", assertion={"type": "none", "result": "none"},
                         detail=str(blocked_exc))
        elif item.get("refused"):
            entry.update(execution="refused", assertion={"type": "none", "result": "none"},
                         detail=item["refused"])
        else:
            out, err_lines = outcomes[idx]
            ex, atype, aresult, detail = judge(item, out, err_lines)
            entry.update(execution=ex, assertion={"type": atype, "result": aresult},
                         detail=detail)
        if item.get("note"):
            entry["note"] = item["note"]
        results.append(entry)

    if args.json:
        print(json.dumps({"file": args.file or args.case_plan,
                          "mutation_policy": args.mutation_policy,
                          "results": results}, indent=2))
    else:
        n_ok = sum(1 for r in results
                   if r["execution"] == "completed" and r["assertion"]["result"] != "mismatch")
        src = args.file or args.case_plan
        print(f"# {src}: {n_ok}/{len(results)} items OK (policy={args.mutation_policy})\n")
        for r in results:
            a = r["assertion"]
            tag = r["execution"].upper() if r["execution"] != "completed" else \
                (a["result"].upper() + (f" {a['type']}" if a["type"] != "none" else "")
                 if a["result"] != "none" else f"EXEC-OK {a['type']}")
            print(f"[{tag}] #{r['n']} {r['sql']}")
            print(f"    -> {r['detail']}")
    n_bad = sum(1 for r in results
                if r["execution"] in ("error", "blocked") or r["assertion"]["result"] == "mismatch")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
