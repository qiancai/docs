"""Shared Markdown/SQL parsing for the tidb-doc-e2e-test harness.

Single source of truth for: fenced-code-block extraction, SQL block
classification (statements / transcript / output-table), transcript parsing,
expected-result-table parsing, statement typing. Used by both
scan-sql-blocks.py (inventory) and run-sql-test.py (execution) so the two can
never disagree about what a block is.
"""
import re

FENCE_LINE_RE = re.compile(r"^\s*```(\S*)\s*$")
TRANSCRIPT_RX = re.compile(r"^\s*mysql>", re.M)
TRANSCRIPT_PROMPT = re.compile(r"^\s*mysql>\s?(.*)$")
TRANSCRIPT_CONT = re.compile(r"^\s*->\s?(.*)$")
TABLE_LINE_RX = re.compile(r"^\s*(\+[-+]+\+|\|.*\|)\s*$", re.M)
STATEMENT_START_RX = re.compile(
    r"^\s*(SELECT|INSERT|CREATE|ALTER|DROP|SET|SHOW|UPDATE|DELETE|WITH|USE|"
    r"BEGIN|COMMIT|ROLLBACK|ADMIN|EXPLAIN|VALUES|REPLACE|TRUNCATE|RENAME|"
    r"DESC|DESCRIBE|GRANT|REVOKE|ANALYZE|BACKUP|RESTORE|DO)\b", re.I | re.M)
NONDETERMINISTIC = re.compile(
    r"\b(RANDOM_BYTES|UUID|RAND|NOW|CURDATE|CURTIME|CURRENT_TIMESTAMP|"
    r"CONNECTION_ID|SLEEP)\s*\(", re.I)
EXPECTED_ERROR_RX = re.compile(r"ERROR\s+(\d+)\s*\((\w+)\)\s*:?\s*(.*)")
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
    """Line-based toggle parser: handles ```lang+x tags and indented fences.
    Returns [(lang, content, start_line, end_line)] with 1-based line numbers."""
    blocks, in_block, lang, buf, start = [], False, "", [], 0
    for ln, line in enumerate(text.splitlines(), 1):
        m = FENCE_LINE_RE.match(line)
        if m:
            if in_block:
                blocks.append((lang, "\n".join(buf), start, ln))
                in_block, buf = False, []
            else:
                in_block, lang, start = True, m.group(1).lower(), ln
        elif in_block:
            buf.append(line)
    return blocks


def is_output_table(content):
    return bool(TABLE_LINE_RX.search(content)) and not STATEMENT_START_RX.search(content)


def is_transcript(content):
    return bool(TRANSCRIPT_RX.search(content))


def classify_block(content):
    """-> 'statements' | 'transcript' | 'output-table'"""
    if is_transcript(content):
        return "transcript"
    if is_output_table(content):
        return "output-table"
    return "statements"


def parse_transcript(content):
    """Parse a mysql> transcript block into [(sql, output_text)] pairs."""
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


def parse_expected(out):
    """Parse a doc output block into {'header': [...], 'rows': [[...]]} or None."""
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


def parse_expected_error(text):
    """Parse 'ERROR 1146 (42S02): Table ... doesn't exist' ->
    {'code': '1146', 'sqlstate': '42S02', 'message': '...'} or None."""
    m = EXPECTED_ERROR_RX.search(text)
    if not m:
        return None
    return {"code": m.group(1), "sqlstate": m.group(2), "message": m.group(3).strip()}


def stmt_types(sql):
    types = {name for name, rx in STMT_RE.items() if rx.search(sql)}
    return types or {"other"}


def norm_cell(s):
    return re.sub(r"\s+", " ", s).strip()


def tables_equal(expected, actual, compare_header=True):
    """Exact comparison: header (normalized cells) + rows."""
    if compare_header:
        eh = [norm_cell(c) for c in expected["header"]]
        ah = [norm_cell(c) for c in actual["header"]]
        if eh != ah:
            return False, "header"
    if expected["rows"] != actual["rows"]:
        return False, "rows"
    return True, None
