# Runbook: Error Budget Burn

Alerts: ErrorBudgetBurnCritical, ErrorBudgetBurnWarning

## Summary
Error budget is burning faster than acceptable for the 28d, 99.9% SLO.

## Triage
1. Confirm multi-window burn panels in Grafana.
2. Identify primary contributors (endpoints, namespaces, versions).
3. Correlate with deploys or traffic spikes.

## Diagnostics
- Fast window: 5m/1h burn queries inside alert rule.
- Error sources by endpoint: `topk(10, sum by (endpoint)(rate(http_requests_total{status_code=~"5.."}[5m])))`
- Latency correlation: p95 panels.

## Remediation
- Rollback or canary reduce.
- Apply feature flags to disable offending paths.
- Increase error handling and fallbacks (serve-stale, circuit breakers).

## Escalation
- App owner: @team-api
- SRE: #sre-oncall

## Postmortem
Open an incident postmortem if ≥30% of monthly budget is consumed.
