# Runbook: High Error Rate

Alert: HighErrorRate
Severity: critical

## Summary
The service is returning 5xx errors above threshold.

## Triage
1. Confirm alert details in Grafana (error rate panel) and Prometheus.
2. Check recent deploys or config changes.
3. Inspect application logs for exceptions; correlate with X-Request-ID / X-Trace-ID.

## Diagnostics
- PromQL:
  - Error rate: `sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
  - Hot endpoints: `topk(5, sum by (endpoint)(rate(http_requests_total{status_code=~"5.."}[5m])))`
- Check dependency health: `/health`, `/health/ready`.
- Review external API errors: `rate(external_api_calls_total{status="error"}[5m])`.

## Remediation
- Roll back recent deployment if correlated with spike.
- Increase replicas temporarily if saturation observed.
- Enable serve-stale if cache backend degraded.
- Throttle problematic endpoints with temporary rate limits.

## Escalation
- App owner: @team-api
- SRE on-call: #sre-oncall

## Postmortem
- Capture root cause, contributing factors, lessons learned, and action items.
