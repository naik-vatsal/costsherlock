# CloudWatch Metrics Pricing

CloudWatch metrics fall into two categories: standard (free, published by AWS) and custom (paid, published by your application). Costs scale with the number of unique metric time series.

## Pricing

| Dimension                          | Price                  |
|------------------------------------|------------------------|
| Standard metrics (EC2, RDS, etc.)  | Free                   |
| Custom metrics (first 10,000)      | $0.30/metric/month     |
| Custom metrics (next 240,000)      | $0.09/metric/month     |
| Custom metrics (over 250,000)      | $0.02/metric/month     |
| Detailed Monitoring (EC2)          | $0.014/metric/month    |
| GetMetricStatistics API calls      | $0.01/1,000 requests   |
| Metric Streams                     | $0.003/1,000 metrics   |
| Dashboard (first 3)                | Free                   |
| Dashboard (4th and beyond)         | $3/month each          |
| Alarm (standard)                   | $0.10/alarm/month      |
| Alarm (high-resolution)            | $0.30/alarm/month      |

## Custom Metric Cost Examples

**Small application publishing 5 custom metrics:**
- 5 × $0.30 = $1.50/month — negligible

**Microservices architecture with 500 services × 10 metrics each = 5,000 metrics:**
- 5,000 × $0.30 = $1,500/month

**Kubernetes cluster with high-cardinality metrics (pod + namespace + cluster = many dimensions):**
- 50 nodes × 200 container metrics × 10 label dimensions = 100,000 unique time series
- First 10,000: $3,000
- Next 90,000 × $0.09: $8,100
- **Total: $11,100/month for metrics alone**

High-cardinality label dimensions are the main cost trap. Each unique combination of dimension values creates a separate billable metric. Adding a `user_id` dimension to a metric used by 10,000 users creates 10,000 separate metrics.

## EC2 Detailed Monitoring
Standard EC2 monitoring publishes metrics at 5-minute intervals (free). Detailed Monitoring enables 1-minute intervals:
- 7 metrics per instance (CPU, network, disk, etc.) × $0.014 = $0.098/instance/month
- For 100 instances: $9.80/month — usually worth it for production

## Embedded Metrics Format (EMF)
Applications using AWS EMF to extract metrics from log data pay CloudWatch Logs ingestion rates ($0.50/GB) rather than per-metric custom metric rates. For high-cardinality workloads, EMF can be significantly cheaper than PutMetricData API calls.
