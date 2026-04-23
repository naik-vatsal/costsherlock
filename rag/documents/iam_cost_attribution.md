# IAM Cost Attribution: Who Made the Change?

When a CloudTrail event caused a cost increase, the `userIdentity` field reveals who made the call. Understanding IAM identity types is critical for determining accountability and preventing recurrence.

## CloudTrail userIdentity Types

### IAMUser
A human or service account with permanent credentials:
```json
{
  "type": "IAMUser",
  "arn": "arn:aws:iam::123456789012:user/john.doe",
  "accountId": "123456789012",
  "userName": "john.doe"
}
```
Attribution: specific person. Check access key usage pattern — if john.doe doesn't normally run `CreateNatGateway`, investigate whether credentials were compromised.

### AssumedRole
A principal that assumed an IAM role (most common for automated systems):
```json
{
  "type": "AssumedRole",
  "arn": "arn:aws:sts::123456789012:assumed-role/terraform-role/terraform-session",
  "sessionContext": {
    "sessionIssuer": {
      "type": "Role",
      "arn": "arn:aws:iam::123456789012:role/terraform-role"
    }
  }
}
```
Attribution: which role + session name. Session name often includes the CI/CD pipeline name or human user who assumed it.

### AWSService
An AWS service acting on your behalf:
```json
{
  "type": "AWSService",
  "invokedBy": "autoscaling.amazonaws.com"
}
```
Attribution: the AWS service (e.g., Auto Scaling Group triggered `RunInstances`). Investigate the ASG configuration, not a specific user.

### Root
The root account user — high-risk indicator:
```json
{"type": "Root", "accountId": "123456789012"}
```
Root actions on infrastructure resources are unusual and should be investigated immediately.

## Mapping IAM Actions to Cost Events

| CloudTrail Principal | Likely Source | Investigation Path |
|---------------------|--------------|-------------------|
| IAM user in dev account | Human action | Check if authorized, escalate if not |
| `terraform-role` | Terraform pipeline | Review git commit that changed Terraform |
| `autoscaling.amazonaws.com` | ASG scale-out | Review scaling policies and CloudWatch alarms |
| `lambda.amazonaws.com` | Lambda execution | Review function code calling resource-creating APIs |
| `cloudformation.amazonaws.com` | CFN stack update | Review template change |

## Linking IAM to Cost Tags
Best practice: tag resources at creation time with the IAM principal ARN using CloudFormation or Terraform. This creates a direct link between Cost Explorer tag-based reports and the IAM user/role responsible for the resource.

Resource tagging on `RunInstances`:
```json
{"Key": "created-by", "Value": "arn:aws:iam::123456789012:user/john.doe"}
```
