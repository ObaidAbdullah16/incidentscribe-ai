# RB-03: ECS tasks keep stopping (crash loop / failed health checks)

Applies to: ECS Fargate or EC2 services whose running count keeps dropping, deployments that never finish.

## Symptoms
- ECS service events: "has stopped N running tasks", "is unable to consistently start tasks successfully".
- Deployment circuit breaker triggered a rollback.
- RunningTaskCount below DesiredTaskCount.

## Likely causes
- Container exits on start: missing environment variable or secret, bad config, migration failure.
- Out of memory (exit code 137) because the task memory is too small.
- Health check failing: wrong path, app listens on a different port, slow startup without a grace period.
- Image pull errors: wrong tag, ECR permissions, no route to ECR (no NAT / no public IP / no VPC endpoint).

## Diagnose
1. `aws ecs describe-tasks --cluster <c> --tasks <stopped-task>` and read `stoppedReason` and container `exitCode`.
2. Read the task's CloudWatch logs for the last lines before exit.
3. Exit 137 = OOM kill; CannotPullContainerError = image/network; ResourceInitializationError = secrets/SSM access.

## Mitigate
- Roll back to the last working task definition.
- Raise memory, add a health check grace period, fix the missing secret.

## Escalate
SEV2 if capacity is reduced but serving; SEV1 if the service has zero healthy tasks.
