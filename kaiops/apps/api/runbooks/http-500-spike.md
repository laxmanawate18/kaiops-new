# Runbook: HTTP 500 Error Spike

## Symptoms

- Sudden rise in HTTP 5xx responses in load balancer / ingress / service dashboards.
- Error-rate alerts breach thresholds (e.g., >1% of requests returning 500).
- Users report broken pages, failed API calls, or partial data loads.
- May be isolated to one endpoint/service or appear across many services.

## Diagnosis Steps

1. Scope the blast radius:
   - Which service(s), endpoints, regions, and user cohorts see errors?
   - Use RED metrics (rate/errors/duration) per service and route.
2. Correlate with recent deployments:
   - `kubectl rollout history deploy/<name> -n <ns>`
   - Check deploy timestamps against the start of the error spike. A spike starting minutes after a rollout is strong evidence of a bad release.
3. Triage logs:
   - Grep error logs for the top exception types and stack traces: `kubectl logs deploy/<name> --since=15m | grep -i error | sort | uniq -c | sort -rn | head`.
   - Identify whether errors are uniform (systemic bug/config) or intermittent (dependency/timeouts).
4. Check upstream dependencies:
   - Database: connection pool exhaustion, lock contention, slow queries, failover events.
   - Cache: Redis/ElastiCache evictions, timeouts, cold cache after flush.
   - External APIs: rate limiting (429s upstream), auth token expiry, regional outages.
5. Inspect resource saturation: CPU throttling, OOM kills, disk full, or exhausted file descriptors on affected pods.
6. Check infrastructure events: node drains, autoscaler activity, ingress/LB config changes, certificate expiry.

## Remediation

- **Bad deploy:** roll back — `kubectl rollout undo deploy/<name> -n <ns>`. Rollback is almost always faster than forward-fixing under pressure.
- **Config/feature-flag regression:** disable the offending flag or revert the config change.
- **Dependency overload:** shed load (rate limit, circuit breakers), scale the dependency, or fail over to a healthy region/replica.
- **Resource saturation:** scale out replicas (`kubectl scale`) or raise limits; recycle unhealthy pods.
- Enable graceful degradation: serve cached/stale responses where possible while the root cause is fixed.
- Once error rates recover, keep the incident open until root cause is confirmed and a permanent fix is merged.

## Escalation

- Notify the owning team immediately with dashboards, sample stack traces, and the correlated deploy.
- Escalate to the dependency's owner if their service is the source (include evidence).
- If customer impact is broad or SLO burn is fast, declare an incident and engage the incident commander and comms channel.
