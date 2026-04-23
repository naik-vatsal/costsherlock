# Troubleshooting CloudWatch Cost Spikes

CloudWatch costs span logs ingestion, metric storage, alarms, and dashboards. Spikes are almost always caused by log verbosity changes or new high-cardinality custom metrics.

## Step 1: Identify the Category

Cost Explorer → filter Service: CloudWatch → group by Usage Type:
- `DataProcessing-Bytes` — log ingestion at $0.50/GB
- `TimedStorage-ByteHrs` — log archival at $0.03/GB-month
- `MetricMonitorUsage` — custom metrics at $0.30/metric/month
- `AlarmMonitorUsage` — CloudWatch alarms
- `Insight-Queries-DataScanned` — Logs Insights query cost

Log ingestion (`DataProcessing-Bytes`) is responsible for 80%+ of unexpected CloudWatch bills.

## Step 2: Log Ingestion Volume Spike

**Check:** CloudWatch → Log Groups → sort by Incoming Bytes
**Signal:** One or more log groups with dramatically higher ingestion than baseline
**CloudTrail events to search (24 hrs before spike):**
- `UpdateFunctionConfiguration` — Lambda log level change
- `UpdateService` (ECS) — task definition with DEBUG logging
- `UpdateEnvironment` (Elastic Beanstalk) — log level env var
- `PutConfigurationSetDeliveryOptions` — SES or other service logging enabled

**Cost impact:** INFO → DEBUG: up to 10× ingestion increase = $2,070 vs $207/month for 500 req/s service

## Step 3: VPC Flow Logs Enabled on Busy VPC

**Check:** VPC console → Your VPCs → Flow Logs tab
**CloudTrail:** `CreateFlowLogs` event
**Cost impact:** A VPC handling 10 Gbps generates ~1 GB/minute of flow log data
- Sent to CloudWatch Logs: 1,440 GB/day × $0.50 = $720/day = **$21,600/month**
- Sent to S3 instead: $33.12/month storage

Always send VPC Flow Logs to S3, not CloudWatch Logs.

## Step 4: Custom Metric High Cardinality

**Check:** CloudWatch → Metrics → All metrics → custom namespaces
**Signal:** Custom metric count jumped from hundreds to thousands
**Cost impact:** 10,000 custom metrics × $0.30 = $3,000/month
**Root cause:** Application publishing metrics with user_id, session_id, or request_id as a dimension

## Step 5: CloudWatch Agent Misconfigured

**Check:** EC2 instances running CloudWatch Agent → configuration file
**Signal:** Agent collecting every log file including verbose application debug logs
**CloudTrail:** `PutParameter` to SSM Parameter Store (agent config often stored there)
**Fix:** Update agent config to collect only specific log files at appropriate verbosity

## Step 6: Logs Insights Expensive Query Pattern

**Check:** CloudWatch Logs Insights → Query history
**Signal:** Large GB-scanned per query or frequent scheduled queries
**Cost:** $0.005/GB scanned; querying 6 TB archive daily = $30/query × 10 queries = $300/day

Use `limit` and time range constraints in Insights queries to reduce data scanned.
