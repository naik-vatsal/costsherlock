# CloudTrail Event Types and Cost Correlation

CloudTrail records API calls made to AWS services. Understanding which events are mutating (create/modify/delete) vs read-only, and which events correlate with cost changes, is essential for cost anomaly investigation.

## Management Events vs Data Events

**Management Events (free, on by default):**
- Control-plane operations: creating, modifying, deleting resources
- Examples: `RunInstances`, `ModifyDBInstance`, `PutBucketLifecycleConfiguration`
- Always enabled in CloudTrail default trails

**Data Events (additional cost: $0.10 per 100,000 events):**
- Data-plane operations: S3 object reads/writes, Lambda invocations, DynamoDB item access
- Examples: `GetObject`, `PutObject`, `Invoke`
- Must be explicitly enabled per resource

## Mutating Events with Cost Impact

These CloudTrail events directly correlate with cost increases:

| Event Name | Service | Cost Implication |
|-----------|---------|-----------------|
| `RunInstances` | EC2 | New instance billing starts |
| `CreateNatGateway` | VPC | $0.045/hr + $0.045/GB begins |
| `ModifyDBInstance` | RDS | Class change or Multi-AZ activation |
| `PutBucketLifecycleConfiguration` | S3 | Policy change affecting transitions |
| `DeleteBucketLifecycle` | S3 | Objects stop transitioning to cheap tiers |
| `UpdateFunctionConfiguration` | Lambda | Memory, timeout, or log level change |
| `PutProvisionedConcurrencyConfig` | Lambda | Idle concurrency charges begin |
| `CreateDBInstanceReadReplica` | RDS | New instance at full price |
| `PutBucketVersioning` | S3 | Old versions start accumulating |
| `PutBucketAccelerateConfiguration` | S3 | Transfer acceleration charges begin |
| `CreateAutoScalingGroup` | EC2 | Fleet scaling begins |
| `UpdateAutoScalingGroup` | EC2 | Max capacity or policies changed |
| `ModifyInstanceAttribute` | EC2 | Instance type or config change |
| `CreateFunction20150331` | Lambda | New function, potential new charges |

## Event Structure for Investigation
Each CloudTrail event contains:
- `eventTime` — timestamp
- `eventName` — the API call
- `userIdentity.arn` — who made the call (IAM user, role, service)
- `requestParameters` — what they specified
- `responseElements` — what was created/modified
- `sourceIPAddress` — where the call came from

## Searching CloudTrail Effectively

CloudTrail Lake or CloudWatch Logs Insights query:
```sql
SELECT eventTime, eventName, userIdentity.arn, requestParameters
FROM cloudtrail_logs
WHERE eventName IN ('RunInstances', 'ModifyDBInstance', 'DeleteBucketLifecycle')
  AND eventTime BETWEEN '2024-01-15' AND '2024-01-16'
ORDER BY eventTime
```

The 14-day window before a cost anomaly is the most productive search window.
