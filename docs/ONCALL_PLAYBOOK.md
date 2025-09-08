# On-Call Playbook

## Contacts
- Primary on-call: @sre-oncall
- Secondary: @sre-backup
- App owners: @team-api
- Pager channel: #alerts

## SLOs
- Availability: 99.9% (28d)
- Latency: p95 < 2s, p99 < 5s

## First Steps for Alerts
1. Acknowledge in Alertmanager.
2. Check Grafana overview dashboard.
3. Open runbook matching the alert.
4. Check recent deploys and feature flags.

## Escalation Policy
- If not mitigated in 15 minutes for critical, escalate to secondary.
- If customer impact is ongoing after 30 minutes, page incident commander.

## Communication
- Update status channel every 15 minutes.
- Record incident timeline.
- Open postmortem for SEV-1/SEV-2.

## Tools
- Grafana, Prometheus, Loki (if enabled), Jaeger
- Kubernetes dashboard / kubectl
