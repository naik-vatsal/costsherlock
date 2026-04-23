# Cost Trap: Unattached Elastic IP Addresses

Elastic IP addresses (EIPs) are free when attached to a running EC2 instance. The moment an EIP is not attached to a running instance — either detached, attached to a stopped instance, or just allocated — AWS charges $0.005/hr.

## Pricing

| EIP State                              | Hourly Charge  | Monthly Cost  |
|----------------------------------------|---------------|---------------|
| Attached to running EC2 instance       | $0.00          | $0.00         |
| Not attached to any instance           | $0.005/hr      | $3.65/month   |
| Attached to stopped EC2 instance       | $0.005/hr      | $3.65/month   |
| Attached to running instance in non-default VPC | $0.00 | $0.00   |
| Additional EIPs on same running instance| $0.005/hr     | $3.65/month   |

## Why This Adds Up

$3.65/month sounds trivial per EIP. In practice:

**Dev team of 20 engineers, each allocating 1–3 EIPs for testing:**
- 40 EIPs total, 50% detached at any time = 20 unattached EIPs
- Monthly cost: 20 × $3.65 = **$73/month**
- Annual: $876 for forgotten EIP allocations

**Post-EC2-termination orphaned EIPs:**
When an EC2 instance is terminated (not stopped), its associated EIP is automatically disassociated but NOT released. It reverts to "unattached" state and immediately starts billing at $0.005/hr.

A team terminating 5 test instances per week without releasing EIPs:
- After 1 month: ~20 unattached EIPs = $73/month
- After 6 months: ~120 unattached EIPs = $438/month (if not cleaned up)

## AWS Config Rule

`eip-attached` is an AWS Config managed rule that flags EIPs not attached to a running instance. Enable this rule to get alerts before costs accumulate.

## Detection

In Cost Explorer, filter "Service: EC2" + "Usage Type: ElasticIP:IdleAddress". Any non-zero value means you have unattached EIPs.

CLI to list all unattached EIPs:
```bash
aws ec2 describe-addresses \
  --query 'Addresses[?AssociationId==null].{IP:PublicIp,AllocationId:AllocationId}'
```

## Remediation

Release unneeded EIPs immediately: `aws ec2 release-address --allocation-id eipalloc-xxxxx`. Billing stops the moment the EIP is released. Add EIP release to instance termination runbooks and IaC teardown scripts.
