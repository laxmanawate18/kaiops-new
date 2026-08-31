# Runbook: OOMKilled Pod Crash Loop

## Symptoms

- Pod enters `CrashLoopBackOff` with reason `OOMKilled` (exit code 137).
- `kubectl describe pod` shows `Last State: Terminated, Reason: OOMKilled`.
- Container memory usage climbs steadily until it hits the memory limit, then the container is killed.
- Alerts fire for pod restarts, missing endpoints, or degraded service latency.
- Node may show memory pressure if multiple pods are affected.

## Diagnosis Steps

1. Confirm the kill reason:
   - `kubectl get pod <pod> -n <ns> -o jsonpath='{.status.containerStatuses[0].lastState}'`
   - Look for `reason: OOMKilled` and note `exitCode: 137`.
2. Check configured limits vs. actual usage:
   - `kubectl top pod <pod> -n <ns>` for current usage.
   - Compare with `resources.limits.memory` in the pod spec.
3. Inspect historical memory trends in Grafana/Datadog (container_memory_working_set_bytes). Determine whether growth is:
   - A sudden spike (traffic surge, large payload, cache stampede).
   - A slow leak over hours/days (memory leak in application code or a library).
4. For JVM workloads, verify heap settings match container limits:
   - Ensure `-XX:MaxRAMPercentage` is set (e.g., 70–75%) instead of fixed `-Xmx` that ignores cgroup limits.
5. Review recent changes: new releases, dependency upgrades, increased batch sizes, or larger request payloads.
6. Check whether other replicas on the same node are also being killed — this can indicate a noisy-neighbor or node-level issue.

## Remediation

- **Immediate relief:** increase the memory limit (`resources.limits.memory`) and restart the deployment:
  - `kubectl set resources deploy/<name> -n <ns> --limits memory=2Gi`
  - Or roll out an updated manifest via GitOps.
- If a traffic spike caused it, scale horizontally: `kubectl scale deploy/<name> --replicas=<n>`.
- For JVM apps, set `-XX:MaxRAMPercentage=75.0` and enable `-XX:+ExitOnOutOfMemoryError` so failures are clean and observable.
- For suspected leaks, capture a heap profile (pprof for Go, heap dump + MAT for JVM) and attach to an incident ticket.
- Add/verify HPA on memory utilization so scaling happens before OOM.

## Escalation

- Escalate to the owning service team if a code-level leak is suspected; include memory graphs and heap profiles.
- Escalate to Platform team if limits cannot be raised due to node capacity — consider adding nodes or moving to larger instance types.
- If customer impact exceeds SLO, page the on-call incident commander.
