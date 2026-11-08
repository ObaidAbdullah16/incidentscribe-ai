# RB-09: Kubernetes pods OOMKilled or in CrashLoopBackOff

Applies to: pod restarts, OOMKilled, CrashLoopBackOff, KubePodCrashLooping alerts.

## Symptoms
- `kubectl get pods` shows restarts increasing, status CrashLoopBackOff, last state OOMKilled (exit 137).

## Likely causes
- Memory limit too low for the workload, memory leak, traffic spike.
- Missing ConfigMap/Secret or failing dependency at startup; failing liveness probe restarts a slow app.

## Diagnose
1. `kubectl describe pod <pod>` - last state, exit code, events.
2. `kubectl logs <pod> --previous`.
3. Grafana: container_memory_working_set_bytes vs the limit over time.

## Mitigate
- Raise the memory limit (and request) to observed peak + 30%; roll back a leaking release.
- Fix probes: add a startupProbe, lengthen initialDelaySeconds.

## Escalate
SEV2 if replicas are below the PodDisruptionBudget minimum; SEV1 if all replicas are down.
