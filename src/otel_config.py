"""
OpenTelemetry configuration for SKIP Server
"""
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


def setup_otel(service_name: str = "skip-server", service_version: str = "1.0.0"):
    """
    Configure OpenTelemetry for the SKIP Server
    """

    # Get OTEL configuration from environment
    otel_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
    otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")

    # Create resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        "host.name": os.getenv("HOSTNAME", "unknown"),
    })

    # Setup tracing
    trace_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(trace_provider)

    # OTLP exporter for traces
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{otel_endpoint}/v1/traces",
        headers=_parse_headers(otel_headers) if otel_headers else None,
    )

    span_processor = BatchSpanProcessor(otlp_exporter)
    trace_provider.add_span_processor(span_processor)

    # Auto-instrument libraries (but not Flask - that will be done manually)
    try:
        RequestsInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        print("✅ Auto-instrumentation enabled for Requests and SQLAlchemy")
    except Exception as e:
        print(f"⚠️ Auto-instrumentation warning: {e}")

    print(f"✅ OpenTelemetry configured for {service_name}")
    print(f"📡 OTLP Endpoint: {otel_endpoint}")
    print("ℹ️ Logs are being sent via file and console handlers (not OTLP)")


def create_custom_log_handler():
    """
    Create a custom handler that also sends logs as trace events
    Only captures application logs, not OTEL internal logs
    """
    class OTELTraceLogHandler(logging.Handler):
        def emit(self, record):
            # Filter out OTEL internal logs and other noise
            if self._should_skip_log(record):
                return

            try:
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span("app_log") as span:
                    span.set_attribute("log.level", record.levelname)
                    span.set_attribute("log.message", record.getMessage())
                    span.set_attribute("log.logger", record.name)
                    span.set_attribute("log.timestamp", record.created)
                    span.set_attribute("log.application", "skip-server")
                    if hasattr(record, 'pathname'):
                        span.set_attribute("log.file", record.pathname)
                        span.set_attribute("log.line", record.lineno)
            except Exception:
                pass  # Don't break logging if OTEL fails

        def _should_skip_log(self, record):
            """
            Skip unwanted logs - only allow application and database logs
            """
            # Skip urllib3 HTTP connections to OTEL collector
            if record.name.startswith('urllib3.connectionpool'):
                return True

            # Skip OTEL internal logs
            if 'otel' in record.name.lower():
                return True

            # Skip HTTP requests to /v1/traces (OTEL internal)
            if '/v1/traces' in record.getMessage():
                return True

            # Skip specific OTEL messages
            if any(skip_msg in record.getMessage().lower() for skip_msg in [
                'post /v1/traces',
                'starting new http connection',
                'http://otel-collector'
            ]):
                return True

            # Skip Werkzeug (Flask internal web server) logs
            if record.name == 'werkzeug':
                return True

            # Allow only application and database related logs
            allowed_loggers = [
                '__main__',              # Main application logs
                'sqlalchemy',            # Database logs
                'mysql.connector',       # MySQL specific logs
                'pymysql',              # PyMySQL logs (if used)
            ]

            # Check if logger name starts with any allowed logger
            logger_allowed = False
            for allowed in allowed_loggers:
                if record.name.startswith(allowed):
                    logger_allowed = True
                    break

            # Skip if not in allowed loggers
            if not logger_allowed:
                return True

            # Don't skip - this is an application or database log
            return False

    return OTELTraceLogHandler()


def _parse_headers(headers_str: str) -> dict:
    """
    Parse OTEL headers string into dictionary
    Format: "key1=value1,key2=value2"
    """
    headers = {}
    if headers_str:
        for header in headers_str.split(","):
            if "=" in header:
                key, value = header.strip().split("=", 1)
                headers[key.strip()] = value.strip()
    return headers


def get_tracer(name: str):
    """
    Get a tracer instance
    """
    return trace.get_tracer(name)


def get_logger(name: str):
    """
    Get a logger instance
    """
    return logging.getLogger(name)


def instrument_flask_app(app):
    """
    Instrument Flask app after it's created
    """
    try:
        FlaskInstrumentor().instrument_app(app)
        print(f"✅ Flask app instrumented successfully")
    except Exception as e:
        print(f"⚠️ Flask instrumentation warning: {e}")
