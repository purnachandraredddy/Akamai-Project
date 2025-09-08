# Runbook: High Latency

Alert: HighLatency
Severity: warning

## Summary
p95 latency exceeded threshold.

## Triage
1. Confirm in Grafana latency panels (p95/p99).
2. Check request volume and saturation.
3. Inspect specific endpoints contributing to latency.

## Diagnostics
- PromQL:
  - p95: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
  - Endpoint latency: `topk(5, histogram_quantile(0.95, sum by (le, endpoint)(rate(http_request_duration_seconds_bucket[5m]))))`
- Review external API latency: `histogram_quantile(0.95, rate(external_api_duration_seconds_bucket[5m]))`
- DB latency: `histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m]))`

## Remediation
- Scale out replicas.
- Increase DB connection pool if starved.
- Add/adjust caching TTLs.
- Defer heavy batch jobs.

## Escalation
- App owner: @team-api
- SRE on-call: #sre-oncall
