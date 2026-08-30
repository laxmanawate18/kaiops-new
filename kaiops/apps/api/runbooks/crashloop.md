# Runbook: CrashLoopBackOff — General Diagnosis

## Symptoms

- Pod status is `CrashLoopBackOff`; restart count increases continuously.
- `kubectl get pods` shows `RESTARTS` climbing with status `CrashLoopBackOff`.
- Service endpoints disappear; upstream services report connection refused or 503s.
- Readiness/liveness probe failure alerts fire alongside restart alerts.

## Diagnosis Steps

1. Get the crash reason and exit code:
   - `kubectl describe pod <pod> -n <ns>` → check `Last State: Terminated` for `Reason` and `ExitCode`.
   - Exit code 1 = app error, 137 = SIGKILL (check OOM), 139 = segfault, 143 = SIGTERM handling issue.
2. Read the logs from the *previous* crashed container:
   - `kubectl logs <pod> -n <ns> --previous`
   - Common findings: missing env vars, bad config file, failed DB migration, unresolvable dependency host.
3. Check probe configuration:
   - Liveness probe failing? Verify `initialDelaySeconds`, `periodSeconds`, `failureThreshold`, and the probe path/port actually exist.
   - A liveness probe that starts before the app is ready causes restart loops on slow-starting apps.
4. Validate config mounts:
   - `kubectl exec` into a healthy sibling pod (if any) or inspect the ConfigMap/Secret: `kubectl get cm <name> -o yaml`.
   - Missing keys or wrong mount paths cause immediate startup crashes.
5. Test dependencies from inside the cluster:
   - DNS: `nslookup <service>`; connectivity: `nc -zv <host> <port>`.
   - A hard dependency (DB, message broker, downstream API) that is down will crash apps that fail fast at boot.
6. Check recent deploys: `kubectl rollout history deploy/<name> -n <ns>`. A bad image tag or broken release is a frequent cause.
7. Review events: `kubectl get events -n <ns> --sort-by=.lastTimestamp | grep <pod>`.

## Remediation

- **Bad release:** roll back immediately — `kubectl rollout undo deploy/<name> -n <ns>`.
- **Config error:** fix the ConfigMap/Secret and restart: `kubectl rollout restart deploy/<name>`.
- **Probe misconfiguration:** raise `initialDelaySeconds`/`failureThreshold`, or switch to a startup probe for slow-booting apps.
- **Dependency outage:** add retry/backoff at startup so the app waits instead of crashing, and restore the dependency first.
- After remediation, watch restarts stop: `kubectl get pods -w`.

## Escalation

- Escalate to the service owner if logs point to application code defects.
- Escalate to Platform if node-level issues (image pull, runtime errors) are suspected.
- If the workload is customer-facing and impact exceeds SLO, open an incident and notify stakeholders.
