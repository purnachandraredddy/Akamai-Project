# API Enhancements: Pagination, Idempotent Endpoints & Error Envelopes

This document describes the comprehensive API enhancements implemented for the Rick & Morty API, including pagination, idempotent endpoints, and consistent error envelopes.

## Overview

The API has been enhanced with:
- **Comprehensive Pagination**: Page-based pagination with configurable page sizes
- **Idempotent Endpoints**: Safe-to-retry GET operations with proper HTTP semantics
- **Consistent Error Envelopes**: Standardized error responses with proper HTTP status codes
- **Input Validation**: Comprehensive validation for all query parameters
- **Request Tracking**: Unique request IDs for tracing and debugging

## Pagination

### Pagination Parameters

All list endpoints support pagination with the following parameters:

| Parameter | Type | Default | Description | Validation |
|-----------|------|---------|-------------|------------|
| `page` | int | 1 | Page number (1-based) | ≥ 1 |
| `page_size` | int | 20 | Items per page | 1-100 |

### Pagination Response Format

```json
{
  "success": true,
  "data": {
    "data": [...],
    "meta": {
      "page": 1,
      "page_size": 20,
      "total_items": 150,
      "total_pages": 8,
      "has_next": true,
      "has_previous": false
    }
  },
  "request_id": "uuid-here",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Pagination Examples

```bash
# Get first page with default size
GET /api/v1/characters

# Get specific page with custom size
GET /api/v1/characters?page=3&page_size=10

# Pagination with filtering
GET /api/v1/characters?page=1&page_size=20&status=Alive&species=Human
```

## Idempotent Endpoints

### HTTP Method Usage

All endpoints use **GET** methods, making them idempotent and safe to retry:

| Endpoint | Method | Idempotent | Description |
|----------|--------|------------|-------------|
| `/` | GET | ✅ | API information |
| `/characters` | GET | ✅ | List characters with pagination |
| `/characters/{id}` | GET | ✅ | Get specific character |
| `/locations` | GET | ✅ | List locations with pagination |
| `/locations/{id}` | GET | ✅ | Get specific location |
| `/episodes` | GET | ✅ | List episodes with pagination |
| `/episodes/{id}` | GET | ✅ | Get specific episode |
| `/earth-humans` | GET | ✅ | Get Earth humans with pagination |
| `/health` | GET | ✅ | Health check |

### Idempotent Characteristics

- **Safe to Retry**: Multiple identical requests produce the same result
- **No Side Effects**: GET operations don't modify server state
- **Cacheable**: Responses can be cached by clients and proxies
- **Bookmarkable**: URLs can be bookmarked and shared

## Consistent Error Envelopes

### Error Response Format

All error responses follow a consistent structure:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "field": "field_name",
    "value": "invalid_value"
  },
  "request_id": "uuid-here",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### HTTP Status Codes

| Status Code | Error Code | Description | Example |
|-------------|------------|-------------|---------|
| 400 | `VALIDATION_ERROR` | Invalid input parameters | Invalid page size |
| 404 | `CHARACTER_NOT_FOUND` | Resource not found | Character ID doesn't exist |
| 404 | `LOCATION_NOT_FOUND` | Resource not found | Location ID doesn't exist |
| 404 | `EPISODE_NOT_FOUND` | Resource not found | Episode ID doesn't exist |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests | Rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Server error | Database connection failed |

### Error Examples

#### Validation Error (400)
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Page size cannot exceed 100",
    "field": "page_size",
    "value": 150
  },
  "request_id": "req-123",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

#### Not Found Error (404)
```json
{
  "success": false,
  "error": {
    "code": "CHARACTER_NOT_FOUND",
    "message": "Character with ID 999 not found"
  },
  "request_id": "req-123",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## Input Validation

### Character Filters

| Parameter | Type | Description | Validation |
|-----------|------|-------------|------------|
| `name` | string | Character name (partial match) | Optional |
| `status` | string | Character status | Must be: Alive, Dead, unknown |
| `species` | string | Character species | Optional |
| `type` | string | Character type | Optional |
| `gender` | string | Character gender | Must be: Male, Female, Genderless, unknown |

### Location Filters

| Parameter | Type | Description | Validation |
|-----------|------|-------------|------------|
| `name` | string | Location name (partial match) | Optional |
| `type` | string | Location type | Optional |
| `dimension` | string | Location dimension | Optional |

### Episode Filters

| Parameter | Type | Description | Validation |
|-----------|------|-------------|------------|
| `name` | string | Episode name (partial match) | Optional |
| `episode` | string | Episode code | Format: S##E## (e.g., S01E01) |

### Sorting Parameters

| Parameter | Type | Default | Description | Validation |
|-----------|------|---------|-------------|------------|
| `sort_by` | string | "id" | Field to sort by | Any valid field |
| `sort_order` | string | "asc" | Sort direction | Must be: asc, desc |

## Request Tracking

### Request ID

Every request and response includes a unique request ID for tracking:

- **Header**: `X-Request-ID` (optional, auto-generated if not provided)
- **Response**: Included in all success and error responses
- **Purpose**: Request tracing, debugging, and correlation

### Usage Examples

```bash
# With custom request ID
curl -H "X-Request-ID: my-request-123" \
     "http://localhost:8000/api/v1/characters?page=1&page_size=10"

# Auto-generated request ID
curl "http://localhost:8000/api/v1/characters?page=1&page_size=10"
```

## API Endpoints

### Root Endpoint

```bash
GET /
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Rick & Morty API",
    "version": "1.0.0",
    "endpoints": {
      "characters": "/characters",
      "locations": "/locations",
      "episodes": "/episodes",
      "earth_humans": "/earth-humans"
    },
    "features": {
      "pagination": "page, page_size parameters",
      "filtering": "name, status, species, type, gender",
      "sorting": "sort_by, sort_order parameters",
      "idempotent": "Safe to retry operations"
    }
  },
  "request_id": "uuid-here",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Characters Endpoint

```bash
GET /characters?page=1&page_size=20&status=Alive&sort_by=name&sort_order=asc
```

**Parameters:**
- Pagination: `page`, `page_size`
- Filters: `name`, `status`, `species`, `type`, `gender`
- Sorting: `sort_by`, `sort_order`

### Character by ID

```bash
GET /characters/{character_id}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Rick Sanchez",
    "status": "Alive",
    "species": "Human",
    "gender": "Male",
    "origin": {"name": "Earth (C-137)", "url": "..."},
    "location": {"name": "Earth (Replacement Dimension)", "url": "..."},
    "image": "https://...",
    "episode": ["https://...", "https://..."],
    "url": "https://...",
    "created": "2017-11-04T18:48:46.250Z"
  },
  "request_id": "uuid-here",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Earth Humans Endpoint

```bash
GET /earth-humans?page=1&page_size=20&sort_by=name&sort_order=asc&force_refresh=false
```

**Parameters:**
- Pagination: `page`, `page_size`
- Sorting: `sort_by`, `sort_order`
- Cache: `force_refresh` (boolean)

## Performance Considerations

### Pagination Limits

- **Maximum page size**: 100 items per page
- **Default page size**: 20 items per page
- **Recommended page size**: 20-50 items for optimal performance

### Caching

- **Database queries**: Cached with configurable TTL
- **External API calls**: Cached with refresh-ahead
- **Response caching**: HTTP cache headers for idempotent endpoints

### Rate Limiting

- **Default limit**: 100 requests per minute per IP
- **Configurable**: Via environment variables
- **Headers**: Rate limit information in response headers

## Best Practices

### Client Implementation

1. **Always handle pagination**: Check `has_next` and `has_previous`
2. **Use appropriate page sizes**: Balance performance vs. data needs
3. **Implement retry logic**: Idempotent endpoints are safe to retry
4. **Handle errors gracefully**: Check `success` field and error codes
5. **Use request IDs**: For debugging and support

### Error Handling

1. **Check success field**: Always verify `success: true`
2. **Handle specific error codes**: Implement specific logic for each error type
3. **Log request IDs**: Include in error logs for debugging
4. **Implement retry logic**: For 5xx errors with exponential backoff

### Performance Optimization

1. **Use appropriate page sizes**: Don't request more data than needed
2. **Cache responses**: Implement client-side caching for idempotent endpoints
3. **Use filtering**: Reduce data transfer with appropriate filters
4. **Monitor rate limits**: Respect rate limiting to avoid 429 errors

## Migration Guide

### From Legacy API

1. **Update pagination**: Replace offset/limit with page/page_size
2. **Handle new response format**: Wrap responses in success/error envelopes
3. **Update error handling**: Use new error codes and structure
4. **Add request tracking**: Include X-Request-ID headers

### Example Migration

**Before (Legacy):**
```bash
GET /characters?offset=0&limit=20
```

**After (Enhanced):**
```bash
GET /characters?page=1&page_size=20
```

**Response Format Change:**
```json
// Before
{
  "info": {...},
  "results": [...]
}

// After
{
  "success": true,
  "data": {
    "data": [...],
    "meta": {...}
  },
  "request_id": "uuid",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## Monitoring & Observability

### Metrics to Track

1. **Pagination usage**: Page sizes, total pages requested
2. **Error rates**: By error code and endpoint
3. **Response times**: By endpoint and page size
4. **Rate limiting**: 429 responses and retry patterns
5. **Request IDs**: For tracing and debugging

### Logging

- **Request/Response logging**: Include request IDs
- **Error logging**: Log error codes and context
- **Performance logging**: Track response times and pagination metrics

This enhanced API provides a robust, scalable, and user-friendly interface with comprehensive pagination, idempotent operations, and consistent error handling for production use.
