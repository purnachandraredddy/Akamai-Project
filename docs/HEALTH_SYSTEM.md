# Health System Documentation

## Overview

The Rick & Morty API implements a comprehensive health system with liveness/readiness probes, circuit-breaker patterns, and graceful shutdown handling for production-grade reliability and observability.

## Health Endpoints

### 1. Liveness Probe (`/health/live`)

**Purpose**: Kubernetes liveness probe to determine if the application should be restarted.

**Behavior**:
- Returns `200` if application is alive and healthy
- Returns `503` if application is unhealthy and should be restarted
- Checks basic application health (uptime, shutdown status)

**Response Example**:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-02T19:25:51.481487",
  "checks": {
    "application": {
      "status": "healthy",
      "uptime_seconds": 11.246391,
      "start_time": "2025-09-02T19:25:40.235080",
      "shutdown_requested": false
    }
  }
}
```

### 2. Readiness Probe (`/health/ready`)

**Purpose**: Kubernetes readiness probe to determine if the application is ready to serve traffic.

**Behavior**:
- Returns `200` if application is ready to serve traffic
- Returns `503` if application is not ready (still starting up or unhealthy)
- Performs comprehensive health checks on all dependencies

**Response Example**:
```json
{
  "status": "degraded",
  "timestamp": "2025-09-02T19:25:57.378572",
  "checks": {
    "database": {
      "status": "unhealthy",
      "error": "Database connection failed"
    },
    "cache": {
      "status": "degraded",
      "l1_cache": {
        "entries": 0,
        "max_size": 500,
        "hits": 0,
        "misses": 0,
        "hit_ratio": 0,
        "evictions": 0
      },
      "l2_cache": {
        "available": false,
        "type": "unavailable"
      }
    },
    "external_api": {
      "status": "healthy",
      "response_time_ms": 197.6020336151123
    },
    "circuit_breakers": {
      "external_api": {
        "name": "external_api",
        "state": "closed",
        "failure_count": 0,
        "success_count": 1,
        "total_requests": 1,
        "failure_rate": 0.0
      }
    }
  }
}
```

### 3. Comprehensive Health Check (`/health`)

**Purpose**: Detailed health information for monitoring and debugging.

**Behavior**:
- Always returns `200` with detailed health information
- Combines liveness and readiness checks
- Provides comprehensive system status

### 4. Circuit Breaker Metrics (`/health/circuit-breakers`)

**Purpose**: Detailed metrics for all circuit breakers.

**Response Example**:
```json
{
  "circuit_breakers": {
    "external_api": {
      "name": "external_api",
      "state": "closed",
      "failure_count": 0,
      "success_count": 1,
      "total_requests": 1,
      "total_failures": 0,
      "total_successes": 1,
      "failure_rate": 0.0,
      "last_failure_time": null,
      "last_success_time": "2025-09-02T19:25:57.378551",
      "config": {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "success_threshold": 3,
        "timeout": 10
      }
    }
  },
  "timestamp": "2025-09-02T19:26:05.750473"
}
```

### 5. Graceful Shutdown (`/health/shutdown`)

**Purpose**: Initiate graceful shutdown for testing and manual shutdown.

**Behavior**:
- POST endpoint to initiate shutdown
- Sets shutdown flag and begins graceful shutdown process
- Useful for testing shutdown behavior

## Circuit Breaker Pattern

### Implementation

The system implements circuit breakers for external dependencies:

1. **External API Circuit Breaker**
   - Failure threshold: 5 failures
   - Recovery timeout: 60 seconds
   - Success threshold: 3 successes
   - Timeout: 10 seconds

2. **Database Circuit Breaker**
   - Failure threshold: 3 failures
   - Recovery timeout: 30 seconds
   - Success threshold: 2 successes
   - Timeout: 5 seconds

3. **Cache Circuit Breaker**
   - Failure threshold: 3 failures
   - Recovery timeout: 30 seconds
   - Success threshold: 2 successes
   - Timeout: 5 seconds

### States

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Circuit is open, failing fast without attempting the operation
- **HALF_OPEN**: Testing if the service is back, allowing limited requests

### Metrics

Each circuit breaker tracks:
- Current state
- Failure and success counts
- Total requests, failures, and successes
- Failure rate percentage
- Last failure and success times
- Configuration parameters

## Graceful Shutdown

### Signal Handling

The application handles the following signals:
- `SIGTERM`: Graceful shutdown (Kubernetes)
- `SIGINT`: Graceful shutdown (Ctrl+C)

### Shutdown Process

1. Signal received
2. Shutdown flag set
3. Health status changed to "shutting_down"
4. New requests rejected
5. Existing requests allowed to complete
6. Database connections closed
7. Cache connections closed
8. Application exits

### Kubernetes Integration

- `terminationGracePeriodSeconds: 60` - Allows 60 seconds for graceful shutdown
- Liveness probe will return 503 during shutdown
- Readiness probe will return 503 during shutdown

## Kubernetes Configuration

### Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### Termination Grace Period

```yaml
terminationGracePeriodSeconds: 60
```

## Health Status Levels

### Application Status

- **healthy**: Application is running normally
- **starting**: Application is still initializing (first 30 seconds)
- **degraded**: Some dependencies are unhealthy but application can serve traffic
- **unhealthy**: Critical dependencies are failing
- **shutting_down**: Application is in the process of shutting down

### Dependency Status

- **healthy**: Dependency is working normally
- **degraded**: Dependency has issues but is partially functional
- **unhealthy**: Dependency is completely unavailable

## Monitoring Integration

### Prometheus Metrics

The health system exposes metrics for:
- Circuit breaker states and counts
- Health check durations
- Application uptime
- Dependency health status

### Grafana Dashboards

Health metrics can be visualized in Grafana dashboards showing:
- Circuit breaker states over time
- Health check success/failure rates
- Application uptime and availability
- Dependency health trends

## Testing

### Manual Testing

```bash
# Test liveness probe
curl http://localhost:8000/health/live

# Test readiness probe
curl http://localhost:8000/health/ready

# Test comprehensive health
curl http://localhost:8000/health

# Test circuit breaker metrics
curl http://localhost:8000/health/circuit-breakers

# Test graceful shutdown
curl -X POST http://localhost:8000/health/shutdown
```

### Automated Testing

The system includes comprehensive test scripts:
- `test_health_system.py`: Tests all health endpoints
- Circuit breaker behavior testing
- Graceful shutdown testing

## Best Practices

### Production Deployment

1. **Configure appropriate timeouts** for health checks
2. **Set proper failure thresholds** based on your SLA requirements
3. **Monitor circuit breaker metrics** to detect issues early
4. **Use separate endpoints** for liveness and readiness probes
5. **Implement proper logging** for health check failures

### Monitoring

1. **Alert on circuit breaker state changes**
2. **Monitor health check response times**
3. **Track application uptime and availability**
4. **Set up dashboards** for health metrics visualization

### Troubleshooting

1. **Check circuit breaker states** when experiencing issues
2. **Review health check logs** for dependency failures
3. **Monitor graceful shutdown behavior** during deployments
4. **Verify Kubernetes probe configurations** match application behavior

## Security Considerations

- Health endpoints are public by default (no authentication required)
- In production, consider restricting access to health endpoints
- Circuit breaker metrics may contain sensitive information
- Graceful shutdown endpoint should be protected or removed in production

## Performance Impact

- Health checks are lightweight and fast
- Circuit breakers add minimal overhead
- Graceful shutdown ensures no data loss
- Monitoring metrics have negligible performance impact
