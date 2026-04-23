# Cost Trap: Debug Logging and CloudWatch Logs Ingestion

Enabling DEBUG-level logging in production is the most common cause of sudden, dramatic CloudWatch Logs cost spikes. A single configuration change can multiply log ingestion by 10–100× overnight.

## The Math of Log Levels

A typical production web service handling 500 requests/second:

| Log Level | Bytes/Request | GB/Day  | Monthly Ingestion | Monthly Cost      |
|-----------|---------------|---------|-------------------|-------------------|
| ERROR     | 50 bytes      | 2.1 GB  | 63 GB             | $31.50            |
| WARN      | 80 bytes      | 3.5 GB  | 105 GB            | $52.50            |
| INFO      | 200 bytes     | 8.6 GB  | 258 GB            | $129.00           |
| DEBUG     | 2,000 bytes   | 86.4 GB | 2,592 GB          | **$1,296.00**     |
| TRACE     | 5,000 bytes   | 216 GB  | 6,480 GB          | **$3,240.00**     |

Switching from INFO to DEBUG: +$1,167/month per service.

## Common Triggers in CloudTrail

Several CloudTrail events correlate with this cost trap:
- `UpdateFunctionConfiguration` — Lambda LOG_LEVEL environment variable changed to DEBUG
- `UpdateService` — ECS task definition updated with DEBUG log level
- `UpdateAppplicationConfiguration` — Elastic Beanstalk environment variable changed

## Lambda-Specific: X-Ray Tracing
Enabling X-Ray active tracing adds trace data alongside log data:
- X-Ray trace recording: $5.00 per 1M traces (first 100K free/month)
- Lambda service integration adds detailed subsegment data per invocation
- A service with 10M invocations/month: $47.50/month in X-Ray alone

## Cascade Effect: Storage Cost
Even after reverting log level to INFO, the DEBUG-period logs remain in CloudWatch storage at $0.03/GB-month. One week of DEBUG logging at 86.4 GB/day leaves:
- ~605 GB of debug logs in storage
- Storage cost: $18.15/month ongoing until retention policy expires the data
- With no retention policy: indefinite storage cost

## Remediation Steps

1. Identify the trigger: search CloudTrail for configuration change events in the 24 hours before the cost spike
2. Revert log level to INFO or ERROR immediately
3. Set a CloudWatch alarm on `IncomingBytes` metric for critical log groups
4. Enforce log retention policies of 7–30 days on all log groups
5. Consider log sampling in production for DEBUG statements (log 1% of debug messages)

Estimated monthly savings from fixing: $1,167–$3,111 per affected service.
