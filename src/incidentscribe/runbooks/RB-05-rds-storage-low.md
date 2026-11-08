# RB-05: RDS free storage space low

Applies to: FreeStorageSpace alarms on RDS/Aurora PostgreSQL or MySQL.

## Symptoms
- FreeStorageSpace dropping fast; at zero the database becomes read-only or stops.

## Likely causes
- Table or index bloat, a runaway log table, a long-running transaction blocking vacuum.
- Replication slots holding WAL (a dead logical replication consumer).
- Temporary files from huge sorts.

## Diagnose
1. Biggest tables: `SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_statio_user_tables ORDER BY 2 DESC LIMIT 10;`
2. Replication slots: `SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) FROM pg_replication_slots;`
3. Long transactions in `pg_stat_activity`.

## Mitigate
- Enable storage autoscaling or increase allocated storage (no downtime, but only once every 6 hours).
- Drop an abandoned replication slot, end the long transaction, archive or truncate the runaway table.

## Escalate
SEV1 below 5% free space on a production database.
