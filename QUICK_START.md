# Quick Start Guide - SKIP Server with OpenTelemetry

## Prerequisites
- Docker and Docker Compose installed
- External Splunk server accessible
- Network connectivity between containers and Splunk

## Quick Setup

### 1. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your Splunk details
nano .env
```

Required variables:
- `SPLUNK_HEC_ENDPOINT`: Your Splunk HEC endpoint
- `SPLUNK_HEC_TOKEN`: Your Splunk HEC token

### 2. Start Services
```bash
# Make script executable (Linux/Mac)
chmod +x manage_otel.sh

# Start everything
./manage_otel.sh start
```

### 3. Access Services
- **SKIP Server**: http://localhost:8080
- **OTEL Metrics**: http://localhost:8888/metrics
- **Splunk**: Configure your external Splunk server

### 4. Validate Setup
```bash
# Check service status
./manage_otel.sh status

# View logs
./manage_otel.sh logs skip    # Skip Server logs
./manage_otel.sh logs otel    # OTEL Collector logs
```

## Troubleshooting

### Common Issues

**1. Splunk Connection Failed**
```bash
# Check connectivity
curl -k $SPLUNK_HEC_ENDPOINT/services/collector/health

# Verify HEC token
curl -k -H "Authorization: Splunk $SPLUNK_HEC_TOKEN" $SPLUNK_HEC_ENDPOINT/services/collector/health
```

**2. No Data in Splunk**
- Verify HEC is enabled in Splunk
- Check index permissions
- Validate token permissions

**3. OTEL Collector Issues**
```bash
# Check collector logs
./manage_otel.sh logs otel

# Validate configuration
./manage_otel.sh validate
```

## Splunk Searches

### View All SKIP Server Data
```spl
index=main sourcetype=otel_logs OR sourcetype=otel_traces OR sourcetype=otel_metrics
| eval service_name=coalesce('service.name', service_name)
| search service_name="skip-server"
| sort _time desc
```

### Monitor Errors
```spl
index=main sourcetype=otel_logs service_name="skip-server" level=ERROR
| sort _time desc
```

### Track HTTP Requests
```spl
index=main sourcetype=otel_traces service_name="skip-server" span_kind=server
| eval duration_ms='duration.ns'/1000000
| stats count avg(duration_ms) as avg_duration by operation_name
```

## Development

### Adding Custom Traces
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@app.route('/api/custom')
def custom_endpoint():
    with tracer.start_as_current_span("custom_operation") as span:
        span.set_attribute("custom.attribute", "value")
        # Your code here
        return result
```

### Adding Custom Metrics
```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
request_counter = meter.create_counter("custom_requests_total")

def increment_counter():
    request_counter.add(1, {"endpoint": "/api/custom"})
```

## Production Considerations

1. **Security**: Use proper authentication and SSL/TLS
2. **Performance**: Monitor collector resource usage
3. **Retention**: Configure appropriate data retention policies
4. **Monitoring**: Set up alerts for service health
5. **Scaling**: Consider OTEL Collector scaling for high throughput