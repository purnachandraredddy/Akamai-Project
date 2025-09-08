# Chaos Testing Plan

## Objectives
- Validate resiliency to dependency failures and node disruptions
- Verify circuit breakers, retries, and timeouts
- Confirm SLO adherence under stress

## Scenarios
1. External API latency spike and 5xx bursts
2. Redis unavailable / high latency
3. Database connection pool exhaustion
4. Pod eviction / node drain
5. Network partition between app and dependencies

## Tools
- LitmusChaos, Chaos Mesh, or Gremlin
- tc/netem for latency injection

## Metrics to Observe
- Error rate, p95 latency, saturation (CPU/mem)
- Circuit breaker states and retry counts
- Readiness/liveness probe behavior

## Pass Criteria
- Error-budget burn stays within acceptable limits
- Readiness flips to degraded but service remains available where designed
- No crash loops; graceful shutdown respected

## Notes
- Run in staging with realistic load
- Announce window; have rollback plan
- Capture findings and follow-up actions
