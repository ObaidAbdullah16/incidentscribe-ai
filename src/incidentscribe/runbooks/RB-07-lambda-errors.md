# RB-07: Lambda errors, throttles or timeouts

Applies to: Lambda Errors, Throttles, Duration near timeout, DLQ / failed event destinations.

## Symptoms
- Errors or Throttles metric above zero; async events going to the DLQ; API returning 502 from API Gateway.

## Likely causes
- Code exception after a deploy; missing permission (AccessDenied) after an IAM change.
- Timeouts from a slow dependency; cold starts in a VPC.
- Throttling: account concurrency limit reached or reserved concurrency too low.

## Diagnose
1. CloudWatch Logs Insights on the function: `filter @message like /ERROR|Task timed out/`.
2. Check ConcurrentExecutions vs the account limit; check reserved concurrency.
3. Check the last deployment and IAM policy changes (CloudTrail).

## Mitigate
- Roll back to the previous version/alias; add retries with backoff; raise timeout only if the dependency is healthy.
- Request a concurrency limit increase or rebalance reserved concurrency.

## Escalate
SEV2 for user-facing APIs; SEV3 for background processing with a DLQ.
