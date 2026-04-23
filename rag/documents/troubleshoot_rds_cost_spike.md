# Troubleshooting RDS Cost Spikes

RDS cost spikes have four main causes: instance class changes, Multi-AZ activation, storage growth, or RI expiry. Each leaves a distinct fingerprint in CloudTrail and Cost Explorer.

## Step 1: Categorize the Increase

Cost Explorer → filter Service: RDS → group by Usage Type:
- `InstanceUsage:db.r5.2xlarge` — instance hours, look for class change
- `Multi-AZUsage:db.r5.2xlarge` — Multi-AZ instances (note "Multi-AZ" prefix)
- `RDS:GP2-Storage-Bytes` — storage in GB-hours
- `RDS:BackupUsage` — backup storage overage

If the cost doubled and `Multi-AZUsage` appeared where only `InstanceUsage` existed before, Multi-AZ was enabled.

## Step 2: Multi-AZ Accidentally Enabled

**Check:** RDS console → instance → Configuration → Multi-AZ = Yes
**CloudTrail signal:** `ModifyDBInstance` with `multiAZ: true` in requestParameters
**Cost impact:** Exact doubling of instance cost. db.r5.2xlarge: +$700.80/month
**Who did it:** CloudTrail `userIdentity.arn` on the `ModifyDBInstance` event

Remediation: `modify-db-instance --no-multi-az` during maintenance window.

## Step 3: Instance Class Upgrade

**Check:** CloudTrail for `ModifyDBInstance` with `dbInstanceClass` parameter changed
**Cost impact:** db.t3.medium ($49.64) → db.r5.2xlarge ($700.80) = +$651.16/month (13× increase)

Look for the IAM principal who executed the modification and whether it was authorized.

## Step 4: RI Expiry (On-Demand Rate Now Applies)

**Check:** RDS console → Reserved Instances → check expiry dates
**Cost Explorer signal:** `InstanceUsage` cost increases while no `ModifyDBInstance` CloudTrail events
**Cost impact:** db.r5.2xlarge RI → on-demand: +$333.47/month per instance

## Step 5: Storage Autoscaling Growth

**Check:** RDS console → instance → Storage → Current allocated storage
**CloudTrail signal:** `ModifyDBInstance` with `allocatedStorage` increasing (triggered by autoscaling, not a human)
**Cost impact:** $0.115/GB-month × storage increase; 1 TB growth = +$115/month

Storage cannot be reduced without manual snapshot/restore. Address the data growth cause first.

## Step 6: Backup Retention Period Increase

**Check:** RDS console → instance → Maintenance & backup → Backup retention period
**CloudTrail signal:** `ModifyDBInstance` with `backupRetentionPeriod` increased (e.g., 7 → 35 days)
**Cost impact:** 5× more backup data = backup storage overage charges at $0.095/GB-month for data beyond 100% of DB size

## Step 7: Read Replica Added

**Check:** RDS console → instance → Replicas tab
**CloudTrail signal:** `CreateDBInstanceReadReplica`
**Cost impact:** Each read replica is a full billable instance at the same class price as primary
