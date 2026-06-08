---
title: Kernel Versioning for TiDB Cloud
summary: Learn about the versioning rules, format, and release notes for the TiDB X kernel compared to the standard TiDB kernel across different TiDB Cloud offerings.
---

# TiDB Cloud Kernel Versioning

This document describes the versioning rules for the underlying database kernels used across different TiDB Cloud plans: Starter, Essential, Premium, and Dedicated.

Based on your TiDB Cloud plan, your TiDB Cloud resources run on different TiDB kernels:

| Plan | Kernel | Architecture |
|------|--------|--------------|
| TiDB Cloud Starter, Essential, and Premium | TiDB X kernel | [TiDB X](/tidb-cloud/tidb-x-architecture.md) architecture (Cloud-native object storage backbone) |
| TiDB Cloud Dedicated | Standard TiDB kernel | Classic TiDB architecture (Dedicated compute and storage) |

Because the standard TiDB kernel and the TiDB X kernel follow different development and release cycles, they use different versioning schemes.

## TiDB X kernel versioning

TiDB Cloud Starter, Essential, and Premium instances run on the TiDB X kernel, whose release cadence and versioning is independent of TiDB Cloud console and control plane updates.

The TiDB X kernel uses a time-based versioning convention:

```text
TiDB-X-CLOUD.YYYYMM.x
```

For example:

```text
TiDB-X-CLOUD.202510.1
```

Where:

- `YYYYMM` represents the year and month of the baseline release. A more recent `YYYYMM` value indicates a newer kernel version.
- `x` represents patch number for a specific baseline release.

For example, `TiDB-X-CLOUD.202510.1` represents the first patch release for the TiDB X kernel baseline established in October 2025.

Because the TiDB X kernel follows its own release cycle, TiDB Cloud publishes dedicated TiDB X kernel release notes separately from the TiDB Self-Managed releases notes.

## TiDB kernel versioning

TiDB Cloud Dedicated clusters run on the standard TiDB kernel, whose version strictly aligns with TiDB Self-Managed releases (for example, v8.5.6 or v7.5.7).

To learn about features, improvements, and bug fixes included in a specific TiDB Cloud Dedicated kernel version, refer to the corresponding [TiDB Self-Managed release notes](/releases/release-notes.md).

## Comparison of TiDB X kernel and TiDB kernel versioning

| Item | TiDB X Kernel | TiDB Kernel |
|--------|--------|--------|
| **Used by** | TiDB Cloud Starter, Essential, Premium | TiDB Cloud Dedicated |
| **Version format** | `TiDB-X-CLOUD.YYYYMM.x` | `vX.Y.Z` (follows TiDB Self-Managed) |
| **Release cadence** | Independent | Follows TiDB Self-Managed |
| **Release notes** | Dedicated TiDB X release notes | TiDB Self-Managed release notes |

## FAQ

### Which kernel version is running on my TiDB Cloud Starter, Essential, or Premium instance?

You can view the kernel version on the instance overview page in the [TiDB Cloud console](https://tidbcloud.com/) for Starter, Essential, and Premium instances.

### Which kernel version is running on my TiDB Cloud Dedicated cluster?

You can view the kernel version on the cluster overview page in the [TiDB Cloud console](https://tidbcloud.com/) for TiDB Cloud Dedicated.

### Can I choose the TiDB X kernel version for my TiDB Cloud Starter, Essential, or Premium instance?

No. Although the kernel version is displayed for transparency, TiDB Cloud manages the complete kernel lifecycle.

TiDB Cloud provides validated default kernel versions for new instances and performs managed upgrades when appropriate. This approach helps ensure security, stability, compatibility, and access to the latest features and improvements without requiring manual intervention.

### Can I choose the TiDB kernel version for my TiDB Cloud Dedicated cluster?

Placeholder-for-answer.