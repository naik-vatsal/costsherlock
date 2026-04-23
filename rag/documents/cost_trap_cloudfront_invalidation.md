# Cost Trap: CloudFront Cache Invalidation Costs

CloudFront cache invalidations remove files from edge caches before their TTL expires. The first 1,000 invalidation paths per month are free; each additional path costs $0.005. At scale or with automation that triggers invalidations per-deploy, this adds up fast.

## Pricing

| Invalidations per Month | Price per Path |
|------------------------|----------------|
| First 1,000 paths       | $0.00 (free)   |
| Over 1,000 paths        | $0.005/path    |

A wildcard invalidation (`/*`) counts as **1 path**, not as the number of files invalidated. A path like `/images/*` also counts as 1 path.

## The Automation Trap

CI/CD pipelines that invalidate specific file paths on each deploy:
- 5 deploys/day × 500 paths invalidated per deploy = 2,500 paths/day
- Monthly: 75,000 paths
- Free tier: 1,000
- Billed paths: 74,000 × $0.005 = **$370/month** in invalidation costs

A common root cause: the pipeline was written with specific file paths rather than `/*`, and the file list grew over time without anyone noticing the cost impact.

## Wildcard vs Specific Path Cost

If the same deploy invalidates 500 specific CSS/JS files:
- 500 paths per deploy × 20 deploys/month = 10,000 paths
- After free tier: 9,000 × $0.005 = $45/month

If rewritten as `/*`:
- 1 path per deploy × 20 deploys/month = 20 paths total
- All within free tier: **$0/month**

The wildcard approach is faster, simpler, and free. The trade-off is temporarily serving slightly stale content for files that didn't change — usually acceptable with proper versioned asset filenames.

## Versioned Asset Strategy (Eliminates Invalidations)
The best practice is fingerprinted/hashed asset filenames (e.g., `main.a3f9d8.css`). New deploys publish new filenames; old files expire naturally via TTL. No invalidations needed:
- Invalidation cost: $0
- Cache hit rates remain high
- No stale content risk

## CloudTrail Correlation

`CreateInvalidation` events in CloudTrail show who triggered invalidations and how many paths. A spike in these events from a deployment pipeline or a human user correlates directly with the cost increase.

A `CreateInvalidation` with `Paths.Quantity = 500` 20 times a day is a strong signal of over-specific automated invalidation.
