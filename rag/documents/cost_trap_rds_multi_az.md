# Cost Trap: Accidentally Enabling RDS Multi-AZ

RDS Multi-AZ deploys a synchronous standby replica in a second Availability Zone. It doubles the instance cost immediately and the standby instance is not available for reads. Accidentally enabling Multi-AZ on a non-critical or development database is a straightforward way to double your RDS bill overnight.

## The Immediate Cost Impact

Multi-AZ pricing is exactly 2× the single-AZ instance price:

| Instance         | Single-AZ    | Multi-AZ     | Monthly Increase |
|------------------|-------------|-------------|-----------------|
| db.t3.medium     | $49.64/mo   | $99.28/mo   | +$49.64         |
| db.m5.xlarge     | $249.66/mo  | $499.32/mo  | +$249.66        |
| db.r5.2xlarge    | $700.80/mo  | $1,401.60/mo| +$700.80        |
| db.r5.4xlarge    | $1,401.60/mo| $2,803.20/mo| +$1,401.60      |

The storage is also replicated, though storage pricing is per-GB for the actual data (AWS manages the replication overhead).

## Common Accidental Triggers

1. **Terraform misconfiguration**: `multi_az = true` set globally in a module that's applied to dev/staging
2. **RDS console checkbox**: The "Multi-AZ deployment" option is prominently displayed and easy to click accidentally during instance modification
3. **AWS defaults**: Some RDS creation workflows default to Multi-AZ for "production" presets
4. **Automated failover test**: Enabling Multi-AZ for a failover test, then forgetting to disable after the test

The CloudTrail event is `ModifyDBInstance` with `MultiAZ: true` in the request parameters.

## Enabling Multi-AZ on a Running Instance

When Multi-AZ is enabled on a running instance, AWS:
1. Takes a snapshot of the primary
2. Creates the standby from the snapshot
3. Establishes synchronous replication

This process can take 10–30 minutes for large databases and causes a brief performance impact (I/O freeze) when the standby is synchronized. The billing change is immediate upon `ModifyDBInstance` completion.

## When Multi-AZ Is Actually Worth It
Multi-AZ provides automatic failover in under 2 minutes for production databases. Appropriate for:
- Production databases where 2-minute RTO matters
- Financial systems, user authentication databases
- RDS instances backing customer-facing applications

**Not appropriate for**: dev/staging environments, analytics databases, batch processing databases.

## Remediation
Disable Multi-AZ via console or `modify-db-instance --no-multi-az`. Disabling is also disruptive (brief failover during the conversion) so plan for a maintenance window.
