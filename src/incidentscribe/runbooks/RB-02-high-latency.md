# RB-02: High API latency (p95 / p99)

Applies to: TargetResponseTime, p95 latency, slow pages, SLO latency burn alerts.

## Symptoms
- p95 or p99 latency above threshold; error rate may still be normal.
- Timeouts at clients, queueing, request pile-up.

## Likely causes
- Slow database queries (missing index, lock contention, a large table scan after a data change).
- Cache misses or an evicted / restarted Redis cache.
- Noisy neighbour or CPU throttling (burstable instance out of CPU credits, container CPU limits).
- Garbage collection pauses, thread pool or connection pool exhaustion.
- Slow downstream API.

## Diagnose
1. Which endpoints are slow? Look at per-route latency, not the average.
2. Database: slow query log / Performance Insights top SQL, `pg_stat_activity` for waiting queries.
3. Check CPU credits (CPUCreditBalance) on t2/t3/t4g instances and CPU throttling on containers.
4. Check cache hit ratio and Redis evictions.

## Mitigate
- Scale out the service; add the missing index; increase cache TTL; temporarily shed non-critical traffic.
- Roll back if latency started with a deploy.

## Escalate
SEV2 when the latency SLO error budget burns faster than 2x for an hour; SEV1 if user requests time out.
