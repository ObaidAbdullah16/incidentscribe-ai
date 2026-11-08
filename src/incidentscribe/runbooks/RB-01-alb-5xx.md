# RB-01: Load balancer 5xx errors spike

Applies to: ALB / API Gateway / nginx returning HTTP 500, 502, 503, 504 to users.

## Symptoms
- HTTPCode_ELB_5XX_Count or HTTPCode_Target_5XX_Count alarm, error rate above SLO, users see "Bad Gateway".
- 502/503 from the load balancer itself usually means no healthy targets; 500 from targets means application errors.

## Likely causes
- A bad deploy (new task definition, config or feature flag) - check whether errors started at a deploy.
- Targets failing health checks (crash loop, wrong port, dependency down) so the target group is empty.
- Downstream dependency failing: database, cache, third-party API timeouts.
- Capacity: CPU or memory saturation, too few tasks for the traffic.

## Diagnose
1. Compare error start time with the last deployment (ECS service events, GitHub Actions deploy runs).
2. `aws elbv2 describe-target-health --target-group-arn <tg>` - are targets healthy?
3. Split ELB_5XX vs Target_5XX: ELB 502/503 = no healthy target, Target 500 = application bug.
4. Read application logs for stack traces around the start time (CloudWatch Logs Insights: `fields @timestamp, @message | filter level="ERROR"`).

## Mitigate
- If a deploy caused it: roll back to the previous task definition / image (ECS circuit breaker; in ShipIt: `scripts/rollback.sh` or Control -> rollback).
- If targets are unhealthy: scale out, or fix the health check path/port.
- If a dependency is down: enable the degraded mode / feature flag, fail fast with timeouts.

## Escalate
SEV1 if more than 5% of requests fail for 5 minutes on a customer-facing service; page the service owner.
