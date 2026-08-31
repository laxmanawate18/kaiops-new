# Runbook: High Latency / Slow Responses

## Symptoms

- p95/p99 response times exceed SLO thresholds on one or more services.
- Users report slowness; synthetic monitoring flags long page/API times.
- Latency alerts fire without a corresponding error-rate increase (errors often rise later as timeouts accumulate).
- Queues back up; thread pools and connection pools fill.

## Diagnosis Steps

1. Establish when it started and what changed:
   - Compare latency graphs against deploy timeline, config changes, and traffic patterns.
   - Distinguish gradual degradation (leak/growth) vs. step change (deploy/config/infra event).
2. Break down where time goes:
   - Use traces (OpenTelemetry/Jaeger/Tempo) to find the slowest span: app compute, DB query, cache call, or downstream API.
3. Check database health:
   - Connection pool utilization — saturation here is a classic cause. Look for pool wait time metrics.
   - Slow query log; missing indexes after schema/data growth; lock contention; replication lag affecting read paths.
4. Check cache effectiveness:
   - Hit ratio drop? Evictions spike? TTL expiry storms (thundering herd on mass expiry)?
   - Cold cache after a Redis restart causes temporary latency spikes — expect recovery as the cache warms.
5. Check resource saturation:
   - CPU throttling (cgroup limits), GC pauses (JVM full-GC storms), memory pressure, network throughput caps.
   - `kubectl top pods` and node-level metrics; check for noisy neighbors.
6. Check downstream dependencies: a slow dependency propagates latency even when your service is healthy. Apply timeout/budget analysis.
7. Rule out retry storms: excessive retries amplify load and latency — check retry counts and backoff settings.

## Remediation

- **DB pool exhaustion:** raise pool size modestly, fix leaked connections, optimize the top slow queries, add read replicas for read-heavy paths.
- **Cache misses:** warm the cache, tune TTLs with jitter to avoid expiry storms, add a stale-while-revalidate layer.
- **CPU/GC saturation:** scale horizontally or raise CPU limits; tune GC settings; profile hot code paths.
- **Slow dependency:** enforce strict timeouts with circuit breakers, cache dependency responses, or degrade gracefully.
- **Traffic surge:** scale out (HPA) and/or enable load shedding for non-critical traffic.
- Verify recovery on p95/p99 charts, not just averages — tail latency matters most to users.

## Escalation

- Escalate to the DBA/platform team for database-level issues (locks, failover, storage IOPS).
- Escalate to the dependency owner with trace evidence showing time spent in their service.
- If SLO burn rate is high or VIP customers are impacted, declare an incident and keep stakeholders updated every 30 minutes.
