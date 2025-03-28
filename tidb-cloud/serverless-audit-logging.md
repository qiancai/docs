---
title: TiDB Cloud Serverless Database Audit Logging
summary: Learn about how to audit a serverless cluster in TiDB Cloud.
---

# TiDB Cloud Serverless Database Audit Logging

TiDB Cloud Serverless provides you with a database audit logging feature to record a history of user access details (such as any SQL statements executed) in logs.

> **Note:**
>
> Currently, the database audit logging feature is only available upon request. To request this feature, click **?** in the lower-right corner of the [TiDB Cloud console](https://tidbcloud.com) and click **Request Support**. Then, fill in "Apply for TiDB Cloud Serverless database audit logging" in the **Description** field and click **Submit**.

To assess the effectiveness of user access policies and other information security measures of your organization, it is a security best practice to conduct a periodic analysis of the database audit logs.

The audit logging feature is disabled by default. To audit a cluster, you need to enable the audit logging.

## Enable audit logging

To enable the audit logging for a TiDB Cloud Serverless cluster, using the [TiDB Cloud CLI](/tidb-cloud/cli-reference.md)

```shell
ticloud serverless audit-log enable --cluster-id <cluster-id>
```

To disable the audit logging for a TiDB Cloud Serverless cluster, using the [TiDB Cloud CLI](/tidb-cloud/cli-reference.md)

```shell
ticloud serverless audit-log disable --cluster-id <cluster-id>
```


## Configure audit logging

### Redacted

TiDB Cloud Serverless redacts sensitive data in the audit logs by default. For example, the following SQL statement:

```sql 
INSERT INTO `test`.`users` (`id`, `name`, `password`) VALUES (1, 'Alice', '123456');
```

is redacted as follows:

```sql
INSERT INTO `test`.`users` (`id`, `name`, `password`) VALUES ( ... );
```

If you want to disable the redaction, using the [TiDB Cloud CLI](/tidb-cloud/cli-reference.md)

```shell
ticloud serverless audit-log config --cluster-id <cluster-id> --unredacted
```
