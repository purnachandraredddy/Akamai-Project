# Admin Authentication for Cache Endpoints

This document describes the admin authentication system for cache management endpoints.

## Overview

The `/cache/*` endpoints are protected with admin authentication to prevent unauthorized access to cache management operations. This includes cache warming, metrics, and health checks.

## Authentication Methods

### 1. API Key Authentication (Primary)

**Header**: `x-admin-key`

**Configuration**: Set via `ADMIN_API_KEY` environment variable

**Example**:
```bash
curl -H "x-admin-key: your-secure-admin-api-key" \
     -X POST "http://localhost:8000/cache/warm?endpoint=character"
```

### 2. mTLS (Internal Operations)

For internal operations, use the dedicated admin service:

**Service**: `rick-morty-admin-service` (ClusterIP only)
**Network Policy**: Restricted to `ops` namespace only

**Example**:
```bash
# From ops namespace pod
curl -H "x-admin-key: your-secure-admin-api-key" \
     -X GET "http://rick-morty-admin-service:8000/cache/metrics"
```

### 3. Ingress Allowlist + Basic Auth (Alternative)

For external access with IP restrictions:

```yaml
nginx.ingress.kubernetes.io/whitelist-source-range: 203.0.113.0/24
nginx.ingress.kubernetes.io/auth-type: basic
nginx.ingress.kubernetes.io/auth-secret: cache-admin-basic
nginx.ingress.kubernetes.io/auth-realm: "Restricted"
```

## Protected Endpoints

| Endpoint | Method | Description | Rate Limit |
|----------|--------|-------------|------------|
| `/cache/warm` | POST | Warm cache for endpoint | 5/minute |
| `/cache/metrics` | GET | Get cache metrics | None |
| `/cache/health` | GET | Get cache health | None |

## Security Features

### 1. API Key Validation
- Required for all cache endpoints
- Validated against configured `ADMIN_API_KEY`
- Returns 401 for missing/invalid keys
- Returns 503 if admin key not configured

### 2. Rate Limiting
- Cache warming limited to 5 requests/minute
- Uses SlowAPI with IP-based limiting
- Returns 429 when exceeded

### 3. No-Cache Headers
All admin responses include:
```
Cache-Control: no-store, no-cache, must-revalidate, private
Pragma: no-cache
Expires: 0
```

### 4. Documentation Exclusion
- Cache endpoints excluded from OpenAPI schema
- Not visible in Swagger UI
- Hidden from public documentation

## Configuration

### Environment Variables

```bash
# Required for admin authentication
ADMIN_API_KEY=your-secure-admin-api-key-here

# Cache settings
CACHE_L1_TTL=120
CACHE_L2_TTL=600
CACHE_L1_MAX_SIZE=500
CACHE_MAX_REFRESH_CONCURRENCY=5
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rick-morty-admin-secret
type: Opaque
data:
  admin-api-key: <base64-encoded-key>
```

Generate secure key:
```bash
kubectl create secret generic rick-morty-admin-secret \
  --from-literal=admin-api-key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml
```

## Usage Examples

### Cache Warming
```bash
# Warm character cache
curl -H "x-admin-key: your-key" \
     -X POST "http://localhost:8000/cache/warm?endpoint=character"

# Warm with parameters
curl -H "x-admin-key: your-key" \
     -X POST "http://localhost:8000/cache/warm?endpoint=character&params=%7B%22status%22%3A%22alive%22%7D"
```

### Get Metrics
```bash
curl -H "x-admin-key: your-key" \
     -X GET "http://localhost:8000/cache/metrics"
```

### Health Check
```bash
curl -H "x-admin-key: your-key" \
     -X GET "http://localhost:8000/cache/health"
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Admin API key required"
}
```

### 401 Invalid Key
```json
{
  "detail": "Invalid admin API key"
}
```

### 503 Service Unavailable
```json
{
  "detail": "Admin authentication not configured"
}
```

### 429 Rate Limited
```json
{
  "detail": "Rate limit exceeded: 5 per 1 minute"
}
```

## Security Best Practices

1. **Rotate Keys Regularly**: Use Kubernetes secret rotation
2. **Use Strong Keys**: Generate with `openssl rand -base64 32`
3. **Restrict Access**: Use NetworkPolicies for internal access
4. **Monitor Usage**: Check logs for authentication attempts
5. **Defense in Depth**: Combine API key + mTLS for internal ops

## Monitoring

### Metrics
- Authentication failures tracked in logs
- Rate limiting metrics available
- Cache operation metrics exposed

### Alerts
- Failed authentication attempts
- Rate limit violations
- Admin key configuration issues

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check `ADMIN_API_KEY` is set
   - Verify header name is `x-admin-key`
   - Ensure key matches exactly

2. **503 Service Unavailable**
   - Admin key not configured
   - Check environment variables

3. **429 Rate Limited**
   - Too many requests
   - Wait for rate limit window to reset

### Debug Commands

```bash
# Check if admin key is configured
kubectl get secret rick-morty-admin-secret -o yaml

# View pod environment
kubectl exec -it <pod-name> -- env | grep ADMIN_API_KEY

# Check logs for auth failures
kubectl logs <pod-name> | grep "Admin"
```

## Implementation Details

### Code Structure
- `app/security.py`: Authentication logic
- `app/api.py`: Cache router with auth dependency
- `app/config.py`: Admin key configuration
- `k8s/admin-secret.yaml`: Kubernetes secret template
- `k8s/admin-service.yaml`: Internal admin service

### Dependencies
- FastAPI security utilities
- SlowAPI for rate limiting
- Kubernetes secrets for key management

This authentication system provides robust security for cache management operations while maintaining ease of use for authorized administrators.
