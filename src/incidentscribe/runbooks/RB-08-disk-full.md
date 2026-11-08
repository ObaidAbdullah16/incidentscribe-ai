# RB-08: Disk full on a server (EC2 / VM / node)

Applies to: disk usage above 90%, "No space left on device", inode exhaustion.

## Symptoms
- disk_used_percent alarm (CloudWatch agent), application write failures, crashed services, full /var/log.

## Likely causes
- Logs without rotation, core dumps, old Docker images and build caches, tmp files.
- Inodes exhausted by millions of small files.

## Diagnose
1. `df -h` and `df -i`; then `sudo du -xh / --max-depth=2 | sort -h | tail -20`.
2. `docker system df`; journal size `journalctl --disk-usage`.

## Mitigate
- Rotate/compress logs, `docker system prune -af` on build agents, clean tmp, vacuum the journal.
- Grow the EBS volume (online) and the filesystem (`growpart`, `resize2fs`/`xfs_growfs`).
- Ship logs to CloudWatch/Loki instead of local disk.

## Escalate
SEV2 when a production service cannot write; SEV3 for build agents.
