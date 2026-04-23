# Understanding Your AWS Bill

The AWS bill is organized by service, usage type, and pricing dimension. Knowing how to read it — and which numbers actually matter — is the foundation of any cost investigation.

## Bill Structure

AWS billing has three layers:
1. **Payer account** — the consolidated bill total
2. **Linked accounts** — individual accounts in an AWS Organization
3. **Service line items** — EC2, S3, RDS, Lambda, etc.

Within each service, charges appear by **Usage Type**, which encodes the region and the type of resource:
- `USE1-BoxUsage:m5.xlarge` — m5.xlarge instance in us-east-1
- `USE1-EBS:VolumeUsage.gp3` — gp3 EBS storage in us-east-1
- `USE1-NatGateway-Bytes` — NAT Gateway data in us-east-1

The region prefix codes: USE1 = us-east-1, USE2 = us-east-2, USW2 = us-west-2, EUW1 = eu-west-1.

## Blended vs Unblended Rates

**Unblended rate**: the actual rate charged for that specific usage — either on-demand, reserved, or spot. This is what you actually pay.

**Blended rate**: AWS averages RI discounts across the organization's accounts. A blended rate for m5.xlarge might be $0.130/hr if 70% of usage is RI-covered ($0.089/hr) and 30% is on-demand ($0.192/hr).

For cost attribution, **unblended rates** give a more accurate picture of what each team's actual resources cost.

## Cost Explorer vs Billing Console

**Billing Console**: Shows final invoice totals, credits applied, taxes. Look here for the bottom-line bill.

**Cost Explorer**: Interactive tool for slicing by service, account, region, tag, and time. Look here for anomaly investigation. Granularity: hourly (90 days), daily (13 months), monthly (38 months).

## Key Cost Explorer Views for Investigation

1. **Service view**: Which services changed? Sort by "Change from prior period"
2. **Usage Type view**: Within a service, which specific resource type spiked?
3. **Tag view**: Which team, project, or environment drove the increase? (Requires tagging)
4. **Linked Account view**: Which AWS account in the organization drove the increase?

## AWS Cost and Usage Report (CUR)
The CUR provides line-item detail at 1-hour granularity exported to S3 as CSV or Parquet. It includes:
- `lineItem/UnblendedCost` — actual cost
- `lineItem/UsageAmount` — quantity of usage
- `lineItem/ResourceId` — specific resource ARN
- `resourceTags` — cost allocation tags

Querying CUR with Athena costs $5/TB scanned. For large organizations, CUR is the only way to get per-resource cost attribution.
