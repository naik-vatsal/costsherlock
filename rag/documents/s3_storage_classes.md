# S3 Storage Classes and Pricing

Amazon S3 offers multiple storage classes optimized for different access patterns. Choosing the wrong class — or failing to transition objects — is one of the most common sources of silent cost accumulation.

## Storage Class Prices (us-east-1, per GB-month)

| Storage Class              | Price/GB-month | Min Duration | Retrieval Fee     |
|---------------------------|----------------|--------------|-------------------|
| S3 Standard               | $0.023         | None         | None              |
| S3 Intelligent-Tiering    | $0.023 (active)| None         | None              |
| S3 Standard-IA            | $0.0125        | 30 days      | $0.01/GB          |
| S3 One Zone-IA            | $0.01          | 30 days      | $0.01/GB          |
| S3 Glacier Instant Retrieval | $0.004      | 90 days      | $0.03/GB          |
| S3 Glacier Flexible Retrieval| $0.0036     | 90 days      | $0.01/GB (bulk)   |
| S3 Glacier Deep Archive   | $0.00099       | 180 days     | $0.02/GB (bulk)   |

## Cost Comparison at Scale

For 100 TB of data stored for one year:
- Standard: 100,000 GB × $0.023 × 12 = **$27,600/year**
- Standard-IA (with moderate retrieval): ~$15,600/year
- Glacier Flexible: ~$4,320/year
- Deep Archive: ~$1,188/year

The gap between Standard and Deep Archive is 23×. Storing access logs or compliance archives in Standard rather than Deep Archive is pure waste.

## Intelligent-Tiering
Intelligent-Tiering monitors access patterns and automatically moves objects between frequent-access ($0.023/GB) and infrequent-access ($0.0125/GB) tiers. There is a monitoring fee of $0.0025 per 1,000 objects per month. For objects under 128 KB, Intelligent-Tiering is not cost-effective.

## Minimum Duration Charges
If you store an object in Standard-IA for 20 days then delete it, you are still charged for 30 days. Glacier Flexible charges for 90 days minimum. Deep Archive charges for 180 days. Storing short-lived temporary files in Glacier is more expensive than Standard.

## The Lifecycle Trap
Without a lifecycle policy, all objects default to S3 Standard forever. A 5 TB data lake growing at 200 GB/month with no lifecycle policy accumulates $27.60/month on day one growing to $193/month after 12 months — entirely in Standard pricing.
