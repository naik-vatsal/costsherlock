# Using AWS Cost Explorer Filters Effectively

Cost Explorer filters allow you to isolate exactly which resources, accounts, regions, or teams are responsible for a cost change. Effective use of filters is the core skill in AWS cost investigation.

## Primary Filter Dimensions

### Service
Filter to a single AWS service to isolate spend. When EC2 costs spike, use:
- Service = "Amazon Elastic Compute Cloud - Compute" for instance hours
- Service = "Amazon EC2" includes all sub-items (EBS, data transfer, NAT)

### Usage Type
The most granular built-in dimension. Examples:
- `BoxUsage:m5.xlarge` — on-demand m5.xlarge hours
- `SpotUsage:c5.2xlarge` — spot c5.2xlarge hours
- `EBS:VolumeUsage.gp3` — gp3 storage
- `NatGateway-Bytes` — NAT data processing
- `DataTransfer-Out-Bytes` — internet egress

Use Usage Type with "contains" filter: filter for "NatGateway" to see all NAT-related costs across regions.

### Linked Account
In an AWS Organization with 20 accounts, filter by account ID to isolate a team's spend:
- Account 123456789012 = data-team-prod

### Region
Filter by region when investigating whether a cost increase is region-specific. A spike only in eu-central-1 points to Europe deployment issues, not a global problem.

### Purchase Option
Separates On-Demand, Spot, Reserved Instance, and Savings Plans coverage:
- On-Demand spike + flat Reserved = RI expired or new unplanned resources
- Spot cost drop + On-Demand spike = Spot interruption, fell back to on-demand

### Tags
Cost Allocation Tags enable team/project/environment breakdowns:
- Tag: `Environment` = `production` to see only prod costs
- Tag: `Team` = `data-platform` to attribute costs to that team
- Tag: `Project` = `recommendation-engine` to track project-specific spend

Tags must be activated as Cost Allocation Tags in the Billing console before they appear in Cost Explorer (up to 24 hours delay).

## Grouping Strategies for Investigation

**Identify which service changed:** Group by Service, compare two date ranges
**Identify which instance type spiked:** Group by Usage Type, filter by EC2, compare periods
**Identify which team is responsible:** Group by Tag (Team), compare periods
**Identify which region:** Group by Region, compare periods

## Saved Reports
Cost Explorer supports saving filter/group configurations as reports. Save "Weekly EC2 On-Demand by Instance Type" and "Monthly S3 by Usage Type" as recurring reports for proactive monitoring.

## Anomaly Detection Integration
AWS Cost Anomaly Detection uses ML to alert on unusual spend patterns. Threshold: $X above expected, based on historical patterns. Anomaly root causes link directly back to Cost Explorer filtered views for investigation.
