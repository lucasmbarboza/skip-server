#!/bin/bash

# SKIP Server OpenTelemetry Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_error ".env file not found!"
        print_status "Creating .env from template..."
        cp .env.example .env 2>/dev/null || echo "Please create .env file manually"
        exit 1
    fi
}

# Start external Splunk
start_splunk() {
    print_header "Starting External Splunk"
    if docker-compose -f docker-compose_splunk.yml ps | grep -q "Up"; then
        print_warning "Splunk already running"
    else
        print_status "Starting Splunk..."
        docker-compose -f docker-compose_splunk.yml up -d
        print_status "Waiting for Splunk to be ready..."
        sleep 30
        print_status "Splunk should be available at: http://localhost:8000"
        print_status "Default credentials: admin/my_passsword"
    fi
}

# Start OTEL stack
start_otel() {
    print_header "Starting OpenTelemetry Stack"
    check_env_file
    
    print_status "Building and starting SKIP Server + OTEL Collector..."
    docker-compose -f docker-compose_otel.yml up --build -d
    
    print_status "Waiting for services to be ready..."
    sleep 10
    
    print_status "Services started!"
    print_status "Skip Server: http://localhost:8080"
    print_status "OTEL Metrics: http://localhost:8888/metrics"
}

# Stop all services
stop_all() {
    print_header "Stopping All Services"
    
    print_status "Stopping OTEL stack..."
    docker-compose -f docker-compose_otel.yml down
    
    print_status "Stopping Splunk..."
    docker-compose -f docker-compose_splunk.yml down
    
    print_status "All services stopped"
}

# Show logs
show_logs() {
    print_header "Service Logs"
    
    case $1 in
        "skip"|"skip-server")
            docker-compose -f docker-compose_otel.yml logs -f skip_server
            ;;
        "otel"|"collector")
            docker-compose -f docker-compose_otel.yml logs -f otel-collector
            ;;
        "splunk")
            docker-compose -f docker-compose_splunk.yml logs -f splunk
            ;;
        *)
            echo "Available log options: skip, otel, splunk"
            ;;
    esac
}

# Check status
check_status() {
    print_header "Service Status"
    
    print_status "OTEL Stack:"
    docker-compose -f docker-compose_otel.yml ps
    
    echo ""
    print_status "Splunk:"
    docker-compose -f docker-compose_splunk.yml ps
    
    echo ""
    print_status "Testing connectivity..."
    
    # Test Skip Server
    if curl -s http://localhost:8080/health > /dev/null; then
        print_status "✅ Skip Server responding"
    else
        print_warning "❌ Skip Server not responding"
    fi
    
    # Test OTEL Collector
    if curl -s http://localhost:8888/metrics > /dev/null; then
        print_status "✅ OTEL Collector metrics available"
    else
        print_warning "❌ OTEL Collector not responding"
    fi
    
    # Test Splunk
    if curl -s http://localhost:8000 > /dev/null; then
        print_status "✅ Splunk UI accessible"
    else
        print_warning "❌ Splunk not accessible"
    fi
}

# Validate configuration
validate_config() {
    print_header "Configuration Validation"
    
    check_env_file
    
    print_status "Checking OTEL Collector config..."
    if [ -f otel-collector-config.yaml ]; then
        print_status "✅ OTEL Collector config found"
    else
        print_error "❌ OTEL Collector config missing"
    fi
    
    print_status "Checking Splunk config..."
    if [ -d splunk_config ]; then
        print_status "✅ Splunk config directory found"
    else
        print_warning "❌ Splunk config directory missing"
    fi
    
    print_status "Environment variables:"
    echo "SPLUNK_HEC_ENDPOINT: ${SPLUNK_HEC_ENDPOINT:-not set}"
    echo "SPLUNK_HEC_TOKEN: ${SPLUNK_HEC_TOKEN:-not set}"
    echo "OTEL_SERVICE_NAME: ${OTEL_SERVICE_NAME:-not set}"
}

# Main script logic
case $1 in
    "start")
        start_splunk
        sleep 5
        start_otel
        ;;
    "stop")
        stop_all
        ;;
    "restart")
        stop_all
        sleep 2
        start_splunk
        sleep 5
        start_otel
        ;;
    "logs")
        show_logs $2
        ;;
    "status")
        check_status
        ;;
    "validate")
        validate_config
        ;;
    "splunk")
        start_splunk
        ;;
    "otel")
        start_otel
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|validate|splunk|otel}"
        echo ""
        echo "Commands:"
        echo "  start     - Start Splunk + OTEL stack"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  logs      - Show logs (skip|otel|splunk)"
        echo "  status    - Check service status"
        echo "  validate  - Validate configuration"
        echo "  splunk    - Start only Splunk"
        echo "  otel      - Start only OTEL stack"
        exit 1
        ;;
esac