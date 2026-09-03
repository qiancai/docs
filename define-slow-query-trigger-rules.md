---
title: Configure Trigger Rules for Slow Queries
summary: Define the trigger rules for slow query logs.
---

# Configure Trigger Rules for Slow Queries


<CustomContent platform="tidb-cloud">

This document describes how to use [`tidb_slow_log_rules`](/system-variables.md#tidb_slow_log_rules-new-in-v856) to define the trigger rules for slow queries displayed in [**Slow Query**](/tidb-cloud/tune-performance.md#slow-query) page in the TiDB Cloud console.

[`tidb_slow_log_rules`](/system-variables.md#tidb_slow_log_rules-new-in-v856) supports multi-dimensional metric combinations. It is suitable for "targeted sampling" and "problem reproduction" of slow queries, enabling you to filter target statements based on specific metric combinations.

</CustomContent>

<CustomContent platform="tidb">

This document describes how to use [`tidb_slow_log_rules`](/system-variables.md#tidb_slow_log_rules-new-in-v856) to define the trigger rules for slow query logs.

[`tidb_slow_log_rules`](/system-variables.md#tidb_slow_log_rules-new-in-v856) supports multi-dimensional metric combinations. It is suitable for "targeted sampling" and "problem reproduction" of slow query logs, enabling you to filter target statements based on specific metric combinations.

For TiDB Self-Managed, the triggering behavior of slow query logs depends on the configuration of `tidb_slow_log_rules`:

- If `tidb_slow_log_rules` is not set, slow query log triggering still relies on [`tidb_slow_log_threshold`](/system-variables.md#tidb_slow_log_threshold) (in milliseconds).
- If `tidb_slow_log_rules` is set, the configured rules take precedence, and [`tidb_slow_log_threshold`](/system-variables.md#tidb_slow_log_threshold) will be ignored.

</CustomContent>

For more information about meanings, diagnostic value, and background information of each field, see the [Fields description](#fields-description).

## Unified rule syntax and type constraints

- Rule capacity and separation: `SESSION` and `GLOBAL` each support a maximum of 10 rules. A single session can have up to 20 active rules. Rules are separated by `;`.
- Condition format: each condition uses the format `field_name:value`. Multiple conditions within a single rule are separated by `,`.
- Field and scope: field names are case-insensitive (underscores and other characters are preserved). `SESSION` rules do not support `Conn_ID`. Only `GLOBAL` rules support `Conn_ID`.
- Matching semantics:
    - Numeric fields are matched using `>=`. String and boolean fields are matched using equality (`=`).
    - Matching for `DB` and `Resource_group` is case-insensitive.
    - Explicit operators such as `>`, `<`, and `!=` are not supported.

Type constraints are as follows:

- Numeric types (`int64`, `uint64`, `float64`) uniformly require `>= 0`. Negative values will result in a parsing error.
    - `int64`: the maximum value is `2^63-1`.
    - `uint64`: the maximum value is `2^64-1`.
    - `float64`: the general upper limit is approximately `1.79e308`. Currently, parsing is done using Go's `ParseFloat`. While `NaN`/`Inf` can be parsed, they might lead to rules that are always true or always false. It is not recommended to use them.
- `bool`: supports `true`/`false`, `1`/`0`, and `t`/`f` (case-insensitive).
- `string`: currently does not support strings containing the separators `,` (condition separator) or `;` (rule separator), even with quotes (single or double). Escaping is not supported.
- Duplicate fields: if the same field is specified multiple times in a single rule, the last occurrence takes effect.

## Supported fields

For detailed field descriptions, diagnostic meanings, and background information, see the [field descriptions in `identify-slow-queries`](/identify-slow-queries.md#fields-description).

Unless otherwise noted, the fields in the following table follow the general matching and type rules described in [Unified rule syntax and type constraints](#unified-rule-syntax-and-type-constraints). This table lists only the currently supported field names, types, units, and a few rule-specific notes. It does not repeat each field's semantic meaning.

| Field name                            | Type     | Unit   | Notes                          |
| -------------------------------------- | -------- | ------ | ------------------------------ |
| `Conn_ID`                             | `uint`   | count  | Supported only in `GLOBAL` rules |
| `Session_alias`                       | `string` | none   | -                              |
| `DB`                                  | `string` | none   | Case-insensitive when matched  |
| `Exec_retry_count`                    | `uint`   | count  | -                              |
| `Query_time`                          | `float`  | second | -                              |
| `Parse_time`                          | `float`  | second | -                              |
| `Compile_time`                        | `float`  | second | -                              |
| `Rewrite_time`                        | `float`  | second | -                              |
| `Optimize_time`                       | `float`  | second | -                              |
| `Wait_TS`                             | `float`  | second | -                              |
| `Is_internal`                         | `bool`   | none   | -                              |
| `Digest`                              | `string` | none   | -                              |
| `Plan_digest`                         | `string` | none   | -                              |
| `Num_cop_tasks`                       | `int`    | count  | -                              |
| `Mem_max`                             | `int`    | bytes  | -                              |
| `Disk_max`                            | `int`    | bytes  | -                              |
| `Write_sql_response_total`            | `float`  | second | -                              |
| `Succ`                                | `bool`   | none   | -                              |
| `Resource_group`                      | `string` | none   | Case-insensitive when matched  |
| `KV_total`                            | `float`  | second | -                              |
| `PD_total`                            | `float`  | second | -                              |
| `Unpacked_bytes_sent_tikv_total`      | `int`    | bytes  | -                              |
| `Unpacked_bytes_received_tikv_total`  | `int`    | bytes  | -                              |
| `Unpacked_bytes_sent_tikv_cross_zone` | `int`    | bytes  | -                              |
| `Unpacked_bytes_received_tikv_cross_zone`    | `int` | bytes  | -                          |
| `Unpacked_bytes_sent_tiflash_total`          | `int` | bytes  | -                          |
| `Unpacked_bytes_received_tiflash_total`      | `int` | bytes  | -                          |
| `Unpacked_bytes_sent_tiflash_cross_zone`     | `int` | bytes  | -                          |
| `Unpacked_bytes_received_tiflash_cross_zone` | `int` | bytes  | -                          |
| `Process_time`                        | `float`  | second | -                              |
| `Backoff_time`                        | `float`  | second | -                              |
| `Total_keys`                          | `uint`   | count  | -                              |
| `Process_keys`                        | `uint`   | count  | -                              |
| `cop_mvcc_read_amplification`         | `float`  | ratio  | Ratio value (`Total_keys / Process_keys`) |
| `Prewrite_time`                       | `float`  | second | -                              |
| `Commit_time`                         | `float`  | second | -                              |
| `Write_keys`                          | `uint`   | count  | -                              |
| `Write_size`                          | `uint`   | bytes  | -                              |
| `Prewrite_region`                     | `uint`   | count  | -                              |

## Effective behavior and matching order

- Rule update behavior: every execution of `SET [SESSION|GLOBAL] tidb_slow_log_rules = '...'` overwrites the existing rules in that scope instead of appending to them.
- Rule clearing behavior: `SET [SESSION|GLOBAL] tidb_slow_log_rules = ''` clears the rules in the corresponding scope.
- If the current session has any applicable `tidb_slow_log_rules`, such as `SESSION` rules, `GLOBAL` rules for the current `Conn_ID`, or generic global rules without `Conn_ID`, the output of slow query logs is determined by rule matching results, and `tidb_slow_log_threshold` is no longer used.
- If the current session has no applicable rules, for example when both `SESSION` and `GLOBAL` rules are empty, or only `GLOBAL` rules that do not match the current `Conn_ID` are configured, slow query logging still depends on `tidb_slow_log_threshold`. Note that the unit is milliseconds.
- If you still want to use SQL execution time as a condition for writing slow query logs, use `Query_time` in the rule and note that the unit is seconds.
- Rule matching logic:
    - Multiple rules are combined with `OR`, while multiple field conditions within a single rule are combined with `AND`.
    - `SESSION`-scope rules are matched first. If none matches, TiDB then matches `GLOBAL` rules for the current `Conn_ID`, followed by generic `GLOBAL` rules without `Conn_ID`.
- `SHOW VARIABLES LIKE 'tidb_slow_log_rules'` and `SELECT @@SESSION.tidb_slow_log_rules` return the `SESSION` rule text, or an empty string if unset. `SELECT @@GLOBAL.tidb_slow_log_rules` returns the `GLOBAL` rule text.

## Examples

- Standard format (`SESSION` scope):

    ```sql
    SET SESSION tidb_slow_log_rules = 'Query_time: 0.5, Is_internal: false';
    ```

- Invalid format (`SESSION` scope does not support `Conn_ID`):

    ```sql
    SET SESSION tidb_slow_log_rules = 'Conn_ID: 12, Query_time: 0.5, Is_internal: false';
    ```

- Global rule (applies to all connections):

    ```sql
    SET GLOBAL tidb_slow_log_rules = 'Query_time: 0.5, Is_internal: false';
    ```

- Global rules for specific connections (applied separately to the two connections `Conn_ID:11` and `Conn_ID:12`):

    ```sql
    SET GLOBAL tidb_slow_log_rules = 'Conn_ID: 11, Query_time: 0.5, Is_internal: false; Conn_ID: 12, Query_time: 0.6, Process_time: 0.3, DB: db1';
    ```

## Recommendations

- `tidb_slow_log_rules` is designed to replace the single-threshold approach. It supports combinations of multi-dimensional metric conditions, enabling more flexible and fine-grained control over slow query logging.

- In a well-provisioned test environment with 1 TiDB node (16 CPU cores, 48 GiB memory) and 3 TiKV nodes (each with 16 CPU cores and 48 GiB memory), repeated sysbench tests show that performance impact remains small when multi-dimensional slow query log rules generate millions of slow log entries within 30 minutes. However, when the log volume reaches tens of millions, TPS drops significantly and latency increases noticeably. Therefore, if business workload is high or CPU and memory resources are close to their limits, configure `tidb_slow_log_rules` carefully to avoid log flooding caused by overly broad rules. If you need to limit the log output rate, use [`tidb_slow_log_max_per_sec`](/system-variables.md#tidb_slow_log_max_per_sec-new-in-v856) to throttle it and reduce the impact on business performance.