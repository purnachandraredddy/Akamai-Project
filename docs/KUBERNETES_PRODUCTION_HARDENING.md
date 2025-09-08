# Kubernetes Production Hardening Guide

## Overview

This document outlines the comprehensive Kubernetes production hardening implemented for the Rick & Morty API, including multi-stage builds, HPA, PDB, Ingress, resource management, topology spread, security policies, and readiness gates.

## 🐳 Multi-Stage Docker Build

### Features
- **Builder Stage**: Compiles dependencies and creates virtual environment
- **Production Stage**: Minimal runtime image with security hardening
- **Development Stage**: Includes development tools and hot reload

### Security Features
- Non-root user (appuser:1000)
- Read-only root filesystem
- Minimal attack surface
- Proper signal handling with dumb-init

### File: `Dockerfile.multi-stage`

## 📊 Horizontal Pod Autoscaler (HPA)

### Configuration
- **Min Replicas**: 3
- **Max Replicas**: 20
- **CPU Target**: 70% utilization
- **Memory Target**: 80% utilization
- **Custom Metrics**: Request rate, response time, error rate

### Scaling Behavior
- **Scale Up**: 50% or 4 pods per minute
- **Scale Down**: 10% or 2 pods per minute
- **Stabilization**: 60s up, 300s down

### File: `k8s/hpa-advanced.yaml`

## 🛡️ Pod Disruption Budget (PDB)

### Multiple PDB Strategies
1. **Min Available**: 2 pods
2. **Percentage**: 50% of pods
3. **Max Unavailable**: 1 pod

### Benefits
- Ensures high availability during updates
- Prevents service disruption
- Configurable availability levels

### File: `k8s/pdb-advanced.yaml`

## 🌐 Advanced Ingress Configuration

### Features
- **TLS Termination**: Automatic SSL certificates
- **Rate Limiting**: 100 requests/minute
- **Security Headers**: XSS, CSRF, Content Security Policy
- **Admin Access**: Restricted to internal networks
- **Health Checks**: Proper timeout configurations

### Security Headers
```yaml
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'
```

### File: `k8s/ingress-advanced.yaml`

## 💾 Resource Management

### Resource Requests
- **CPU**: 500m
- **Memory**: 512Mi
- **Ephemeral Storage**: 1Gi

### Resource Limits
- **CPU**: 1000m
- **Memory**: 1Gi
- **Ephemeral Storage**: 2Gi

### Benefits
- Predictable resource allocation
- Prevents resource starvation
- Enables proper scheduling

## 🗺️ Topology Spread & Anti-Affinity

### Topology Spread Constraints
- **Hostname**: Max skew of 1
- **Zone**: Max skew of 1
- **Scheduling**: DoNotSchedule if unsatisfiable

### Anti-Affinity Rules
- **Preferred**: Spread across hosts and zones
- **Weight**: 100 for hosts, 50 for zones
- **Node Affinity**: Prefer worker nodes

### Benefits
- High availability across failure domains
- Load distribution
- Fault tolerance

## 🔒 Network Security

### NetworkPolicy Features
- **Ingress**: Restricted to ingress-nginx and monitoring
- **Egress**: Allowed to database, cache, external APIs
- **DNS**: Required for service discovery
- **Default Deny**: All other traffic blocked

### Security Zones
- **Public**: Ingress traffic only
- **Internal**: Service-to-service communication
- **External**: Outbound API calls

### File: `k8s/network-policy.yaml`

## 🔐 Security Policies

### Seccomp Profile
- **Default Action**: SCMP_ACT_ERRNO
- **Allowed Syscalls**: Essential system calls only
- **Architecture**: x86_64, x86, x32

### AppArmor Profile
- **Network Access**: Allowed
- **File Operations**: Restricted to app directory
- **Capabilities**: Denied dangerous capabilities
- **Process Operations**: Limited to necessary operations

### File: `k8s/security-policies.yaml`

## ✅ Readiness Gates

### External Dependency Checks
- **Rick & Morty API**: Health check endpoint
- **Database**: Connection validation
- **Redis**: Cache connectivity
- **Jaeger**: Tracing service availability

### Implementation
- **Script-based**: Bash script with curl checks
- **Configurable**: Environment-based URL configuration
- **Monitoring**: Continuous health validation

### File: `k8s/readiness-gates.yaml`

## 🚀 Deployment Strategy

### Rolling Updates
- **Max Unavailable**: 1 pod
- **Max Surge**: 1 pod
- **Strategy**: RollingUpdate

### Health Checks
- **Liveness**: `/health/live`
- **Readiness**: `/health/ready`
- **Startup**: `/health/live` with longer timeout

### Graceful Shutdown
- **Termination Grace Period**: 60 seconds
- **Signal Handling**: SIGTERM, SIGINT
- **Resource Cleanup**: Database and cache connections

## 📈 Monitoring & Observability

### Metrics
- **Prometheus**: Custom metrics endpoint
- **ServiceMonitor**: Automatic scraping
- **HPA Metrics**: CPU, memory, custom metrics

### Logging
- **Fluentd**: Log aggregation
- **Structured Logging**: JSON format
- **Log Rotation**: Size-based rotation

### Tracing
- **Jaeger**: Distributed tracing
- **OpenTelemetry**: Instrumentation
- **Request Tracking**: End-to-end visibility

## 🔧 Configuration Management

### Secrets
- **Database URL**: Encrypted storage
- **Redis URL**: Secure configuration
- **API Keys**: Admin access tokens
- **TLS Certificates**: Automatic renewal

### ConfigMaps
- **Application Config**: Environment variables
- **Security Profiles**: Seccomp, AppArmor
- **Readiness Scripts**: Health check logic

## 🎯 Best Practices

### Security
1. **Least Privilege**: Minimal required permissions
2. **Defense in Depth**: Multiple security layers
3. **Regular Updates**: Keep images and dependencies current
4. **Audit Logging**: Track all access and changes

### Performance
1. **Resource Limits**: Prevent resource exhaustion
2. **Horizontal Scaling**: Handle traffic spikes
3. **Caching**: Reduce external API calls
4. **Connection Pooling**: Efficient database usage

### Reliability
1. **Health Checks**: Comprehensive monitoring
2. **Circuit Breakers**: Fail-fast patterns
3. **Graceful Shutdown**: Clean resource cleanup
4. **Rolling Updates**: Zero-downtime deployments

## 🚨 Troubleshooting

### Common Issues
1. **Resource Limits**: Check pod resource usage
2. **Network Policies**: Verify traffic flow
3. **Security Policies**: Check seccomp/AppArmor logs
4. **Readiness Gates**: Validate external dependencies

### Debugging Commands
```bash
# Check pod status
kubectl get pods -l app=rick-morty-api

# View pod logs
kubectl logs -l app=rick-morty-api

# Check resource usage
kubectl top pods -l app=rick-morty-api

# Verify network policies
kubectl describe networkpolicy rick-morty-api-network-policy

# Check HPA status
kubectl get hpa rick-morty-api-hpa
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] Resource limits configured
- [ ] Security policies applied
- [ ] Network policies tested
- [ ] Health checks validated
- [ ] Readiness gates configured

### Deployment
- [ ] Rolling update strategy
- [ ] Graceful shutdown tested
- [ ] Monitoring configured
- [ ] Logging enabled
- [ ] Tracing active

### Post-Deployment
- [ ] HPA scaling tested
- [ ] PDB behavior verified
- [ ] Security policies enforced
- [ ] Performance metrics collected
- [ ] Alerting configured

## 🔄 Continuous Improvement

### Monitoring
- Track performance metrics
- Monitor security events
- Analyze error patterns
- Optimize resource usage

### Updates
- Regular security patches
- Dependency updates
- Configuration tuning
- Performance optimization

This comprehensive hardening ensures the Rick & Morty API is production-ready with enterprise-grade security, reliability, and observability.
