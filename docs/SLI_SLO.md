# SLI/SLO for Rick & Morty API

## Service Overview
- Service: Rick & Morty API wrapper
- Critical paths: GET /api/v1/characters, /locations, /episodes
- Users: External clients

## SLOs
- Availability: 99.9% over 28 days for critical read endpoints
- Latency: p95 < 2s and p99 < 5s over 28 days
- Error budget: 0.1% (43m 12s/month)

## SLIs
- Availability SLI: 1 - (5xx requests / total requests)
- Latency SLI: histogram_quantile over http_request_duration_seconds_bucket
- Dependency SLI: External API success rate >= 99.5%
- Cache hit rate: >= 80%

## Measurement
- Source: Prometheus metrics exported by service
- Queries:
  - Availability: `1 - (sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))`
  - Latency p95: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
  - Dependency success: `1 - (sum(rate(external_api_calls_total{status="error"}[5m])) / sum(rate(external_api_calls_total[5m])))`
  - Cache hit rate: `sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))`

## Burn-rate Alerts
- Critical (fast burn): Trigger if burn-rate > 14x over 5m AND > 6x over 1h
- Warning (slow burn): Trigger if burn-rate > 3x over 1h AND > 1x over 6h
- Based on 28d, 99.9% availability SLO

## Cardinality Guardrails
- Avoid high-cardinality labels (e.g., user_id, request_id) in metrics
- Use endpoint templates (e.g., /api/v1/characters/{id})
- Drop noisy labels via metric_relabel_configs (see prometheus.yml)
- Set sample_limit per job

## Trace-Log Correlation
- Response headers: X-Request-ID, X-Trace-ID
- Logs include `req=<request_id> trace=<trace_id>` fields
- If tracing enabled, trace_id extracted from OpenTelemetry current span

## Reporting
- Grafana dashboards: availability, latency, error budget
- Weekly review of error budget and postmortems on burns > 30%

## Runbooks
- High error rate: docs/runbooks/high-error-rate.md
- High latency: docs/runbooks/high-latency.md
- Error budget burn: docs/runbooks/error-budget-burn.md
