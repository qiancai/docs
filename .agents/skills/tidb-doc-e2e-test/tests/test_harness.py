#!/usr/bin/env python3
"""Unit/golden tests for the tidb-doc-e2e-test harness.

Invariants under test:
  1. The harness must never produce a stronger result than its evidence supports
     (header mismatches fail, connection failures are blocked, writes are refused).
  2. A normalization rule must never erase a documentation-relevant difference
     (ports, prices, limits, states, duplicate controls all survive).

Run: python3 -m unittest discover -s tests -v   (from the skill directory)
"""
import os
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

import markdown_sql as ms  # noqa: E402
import snapdiff  # noqa: E402


class TestMarkdownSqlParsing(unittest.TestCase):
    def test_indented_and_compound_fences(self):
        text = "intro\n    ```sql\n    SELECT 1;\n    ```\n```ebnf+diagram\nX ::=\n```\n```sql\nSELECT 2;\n```\n"
        blocks = ms.code_blocks(text)
        sqls = [c for l, c, _, _ in blocks if l == "sql"]
        self.assertEqual(len(sqls), 2)

    def test_transcript_parse(self):
        content = ("mysql> SHOW VARIABLES LIKE 'x';\n"
                   "+-------+\n| V     |\n+-------+\n| y     |\n+-------+\n"
                   "mysql> SET x = 1;\nQuery OK, 0 rows affected\n")
        pairs = ms.parse_transcript(content)
        self.assertEqual(len(pairs), 2)
        self.assertIn("SHOW VARIABLES", pairs[0][0])
        self.assertEqual(ms.parse_expected(pairs[0][1])["rows"], [["y"]])
        self.assertIsNone(ms.parse_expected(pairs[1][1]))

    def test_mislabeled_output_table(self):
        self.assertEqual(ms.classify_block("+---+\n| a |\n+---+\n| 1 |\n+---+"), "output-table")
        self.assertEqual(ms.classify_block("SELECT 1;\n"), "statements")
        self.assertEqual(ms.classify_block("mysql> SELECT 1;\n"), "transcript")

    def test_expected_error_parse(self):
        err = ms.parse_expected_error("ERROR 1146 (42S02): Table 'db.t' doesn't exist")
        self.assertEqual(err["code"], "1146")
        self.assertEqual(err["sqlstate"], "42S02")

    def test_header_comparison(self):
        exp = {"header": ["wrong"], "rows": [["1"]]}
        act = {"header": ["x"], "rows": [["1"]]}
        ok, where = ms.tables_equal(exp, act, compare_header=True)
        self.assertFalse(ok)
        self.assertEqual(where, "header")
        ok, _ = ms.tables_equal(exp, act, compare_header=False)
        self.assertTrue(ok)

    def test_header_cell_whitespace_normalized(self):
        exp = {"header": ["MD5('abc')"], "rows": [["9001"]]}
        act = {"header": ["MD5('abc')  "], "rows": [["9001"]]}
        ok, _ = ms.tables_equal(exp, act, compare_header=True)
        self.assertTrue(ok)


class TestMutationPolicy(unittest.TestCase):
    def test_risk_classification(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rst", os.path.join(SKILL_DIR, "scripts", "run-sql-test.py"))
        rst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rst)
        self.assertEqual(rst.mutation_risk("SELECT 1"), "read")
        self.assertEqual(rst.mutation_risk("CREATE TABLE t (id INT)"), "write")
        self.assertEqual(rst.mutation_risk("SET GLOBAL x = 1"), "global")
        self.assertEqual(rst.mutation_risk("SET @@global.x = 1"), "global")
        self.assertEqual(rst.mutation_risk("CREATE USER 'a'@'%'"), "global")
        # policies
        self.assertFalse(rst.allowed_by_policy("write", "read-only", False))
        self.assertTrue(rst.allowed_by_policy("write", "sandbox", False))
        self.assertFalse(rst.allowed_by_policy("global", "sandbox", False))
        self.assertTrue(rst.allowed_by_policy("global", "sandbox", True))
        self.assertTrue(rst.allowed_by_policy("global", "unrestricted", False))


class TestSnapdiff(unittest.TestCase):
    def _write(self, content):
        f = tempfile.NamedTemporaryFile("w", suffix=".snap", delete=False)
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def _norm(self, content):
        return snapdiff.normalize(self._write(content))

    def test_port_change_detected(self):
        old = self._norm('- paragraph: "PORT: 4000"\n')
        new = self._norm('- paragraph: "PORT: 3306"\n')
        self.assertNotEqual(old, new)

    def test_price_change_detected(self):
        old = self._norm('- StaticText "Spending Limit $0 / month"\n')
        new = self._norm('- StaticText "Spending Limit $100 / month"\n')
        self.assertNotEqual(old, new)

    def test_state_change_detected(self):
        old = self._norm('- switch "Encryption" [checked]\n')
        new = self._norm('- switch "Encryption" [checked|disabled]\n')
        self.assertNotEqual(old, new)

    def test_duplicate_control_count_matters(self):
        old = self._norm('- button "Save"\n- button "Save"\n- button "Cancel"\n')
        new = self._norm('- button "Save"\n- button "Cancel"\n')
        from collections import Counter
        self.assertNotEqual(Counter(old), Counter(new))

    def test_volatile_masked(self):
        old = self._norm('- StaticText "Current usage: 3.2 GiB"\n- generic: instance 10752744542676048868\n')
        new = self._norm('- StaticText "Current usage: 9.9 GiB"\n- generic: instance 20752744542676048869\n')
        self.assertEqual(old, new)

    def test_doc_relevant_limit_survives(self):
        old = self._norm('- StaticText "Storage limit: 5 GiB"\n- paragraph: maximum 1048576\n')
        new = self._norm('- StaticText "Storage limit: 10 GiB"\n- paragraph: maximum 1048576\n')
        self.assertNotEqual(old, new)  # limit change visible
        # but the 7-digit limit value is NOT masked away
        self.assertIn("1048576", old[1])


class TestScanSingleFile(unittest.TestCase):
    def test_single_file_inventory(self):
        md = "# t\n\n```sql\nSELECT 1;\n```\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(md)
            path = f.name
        self.addCleanup(os.unlink, path)
        out = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "scripts", "scan-sql-blocks.py"), path],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("1 SQL blocks", out.stdout)
        self.assertIn("lines", out.stdout)


if __name__ == "__main__":
    unittest.main()
