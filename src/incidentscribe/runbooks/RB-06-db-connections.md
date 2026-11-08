# RB-06: Database connections exhausted

Applies to: "too many clients", "remaining connection slots are reserved", connection pool timeouts.

## Symptoms
- DatabaseConnections near max_connections; app errors acquiring connections; latency spikes.

## Likely causes
- More app instances/Lambdas than the pool sizing assumed (autoscaling or a Lambda burst).
- Connection leak (connections not returned to the pool).
- Idle-in-transaction sessions.

## Diagnose
1. `SELECT usename, application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3 ORDER BY 4 DESC;`
2. Compare app replica count x pool size with max_connections.
3. Look for `idle in transaction` sessions and their age.

## Mitigate
- Put RDS Proxy or PgBouncer in front; lower per-instance pool size; cap Lambda concurrency.
- Terminate idle-in-transaction sessions older than N minutes; set idle_in_transaction_session_timeout.

## Escalate
SEV2; SEV1 if new requests cannot get a connection at all.
