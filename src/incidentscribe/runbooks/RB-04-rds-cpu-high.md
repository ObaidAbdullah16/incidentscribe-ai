# RB-04: RDS CPU high / database slow

Applies to: RDS or Aurora CPUUtilization alarms, slow queries, high DB load.

## Symptoms
- CPUUtilization above 80% for several minutes, DBLoad above vCPU count, rising query latency.

## Likely causes
- A new query without an index (often from a recent release), or a missing ANALYZE after a bulk load.
- Reporting or batch job running in business hours.
- Connection storm after an app restart.
- Burstable instance (db.t3/db.t4g) out of CPU credits.

## Diagnose
1. Performance Insights / `pg_stat_statements`: top SQL by total time.
2. `SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE state <> 'idle';`
3. Check CPUCreditBalance for burstable classes.
4. Correlate with deploys and cron/batch schedules.

## Mitigate
- Kill or pause the runaway query/job (`SELECT pg_cancel_backend(pid);`).
- Add the missing index (CREATE INDEX CONCURRENTLY), move reports to a read replica.
- Scale the instance class up temporarily.

## Escalate
SEV2 if user-facing latency is affected; involve the DBA/owner before killing sessions you do not own.
