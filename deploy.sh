#!/bin/bash

# MedSAGE Deployment Script
# This script helps deploy the MedSAGE application in different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
BACKUP_DIR="backups"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking system requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env file not found. Copying from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warning "Please edit .env file with your configuration before continuing."
            exit 1
        else
            log_error ".env.example file not found. Please create environment configuration."
            exit 1
        fi
    fi
    
    log_success "All requirements met."
}

setup_directories() {
    log_info "Setting up directories..."
    
    # Create necessary directories
    mkdir -p logs uploads ssl $BACKUP_DIR
    
    # Set proper permissions
    chmod 755 logs uploads ssl $BACKUP_DIR
    
    log_success "Directories created successfully."
}

generate_ssl_certificates() {
    log_info "Checking SSL certificates..."
    
    if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
        log_warning "SSL certificates not found. Generating self-signed certificates for development..."
        
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem \
            -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=localhost"
        
        log_success "Self-signed SSL certificates generated."
        log_warning "For production, replace with proper SSL certificates from a CA."
    else
        log_success "SSL certificates found."
    fi
}

backup_data() {
    if [ "$1" = "true" ]; then
        log_info "Creating backup..."
        
        BACKUP_NAME="medsage_backup_$(date +%Y%m%d_%H%M%S)"
        BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
        
        mkdir -p "$BACKUP_PATH"
        
        # Backup MongoDB data
        if docker-compose ps mongodb | grep -q "Up"; then
            docker-compose exec -T mongodb mongodump --archive | gzip > "$BACKUP_PATH/mongodb_backup.gz"
            log_success "MongoDB backup created."
        fi
        
        # Backup uploads
        if [ -d "uploads" ]; then
            tar -czf "$BACKUP_PATH/uploads_backup.tar.gz" uploads/
            log_success "Uploads backup created."
        fi
        
        # Backup logs
        if [ -d "logs" ]; then
            tar -czf "$BACKUP_PATH/logs_backup.tar.gz" logs/
            log_success "Logs backup created."
        fi
        
        log_success "Backup completed: $BACKUP_PATH"
    fi
}

deploy_development() {
    log_info "Deploying in development mode..."
    
    # Build and start services
    docker-compose -f $DOCKER_COMPOSE_FILE build
    docker-compose -f $DOCKER_COMPOSE_FILE up -d
    
    log_success "Development deployment completed!"
    log_info "Application is available at: http://localhost:5000"
    log_info "MongoDB is available at: localhost:27017"
}

deploy_production() {
    log_info "Deploying in production mode..."
    
    # Validate production configuration
    if grep -q "change_me\|your-.*-here\|development" .env; then
        log_error "Production deployment detected default/development values in .env file."
        log_error "Please update all placeholder values before production deployment."
        exit 1
    fi
    
    # Build and start services
    docker-compose -f $DOCKER_COMPOSE_FILE build --no-cache
    docker-compose -f $DOCKER_COMPOSE_FILE up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check health
    if curl -f http://localhost:5001/health > /dev/null 2>&1; then
        log_success "Production deployment completed successfully!"
        log_info "Application is available at: http://localhost (HTTP) and https://localhost (HTTPS)"
    else
        log_error "Health check failed. Please check the logs."
        docker-compose logs app
        exit 1
    fi
}

deploy_monitoring() {
    log_info "Deploying with monitoring stack..."
    
    docker-compose --profile monitoring up -d
    
    log_success "Monitoring stack deployed!"
    log_info "Prometheus is available at: http://localhost:9090"
    log_info "Grafana is available at: http://localhost:3000 (admin/admin_password_change_me)"
}

stop_services() {
    log_info "Stopping services..."
    docker-compose down
    log_success "Services stopped."
}

cleanup() {
    log_info "Cleaning up..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    log_success "Cleanup completed."
}

show_logs() {
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

show_status() {
    log_info "Service Status:"
    docker-compose ps
    
    log_info "Health Check:"
    if curl -s http://localhost:5001/health | jq '.healthy' 2>/dev/null; then
        log_success "Application is healthy."
    else
        log_warning "Health check failed or service not responding."
    fi
}

# Main script logic
case "$1" in
    "dev"|"development")
        check_requirements
        setup_directories
        generate_ssl_certificates
        backup_data "$2"
        deploy_development
        ;;
    "prod"|"production")
        check_requirements
        setup_directories
        generate_ssl_certificates
        backup_data "$2"
        deploy_production
        ;;
    "monitor"|"monitoring")
        check_requirements
        setup_directories
        generate_ssl_certificates
        deploy_monitoring
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 5
        deploy_development
        ;;
    "cleanup")
        cleanup
        ;;
    "logs")
        show_logs "$2"
        ;;
    "status")
        show_status
        ;;
    "backup")
        backup_data "true"
        ;;
    *)
        echo "Usage: $0 {dev|prod|monitor|stop|restart|cleanup|logs|status|backup} [backup]"
        echo ""
        echo "Commands:"
        echo "  dev         - Deploy in development mode"
        echo "  prod        - Deploy in production mode"
        echo "  monitor     - Deploy with monitoring stack"
        echo "  stop        - Stop all services"
        echo "  restart     - Restart services"
        echo "  cleanup     - Clean up containers and volumes"
        echo "  logs [svc]  - Show logs (optionally for specific service)"
        echo "  status      - Show service status and health"
        echo "  backup      - Create backup of data"
        echo ""
        echo "Add 'backup' as second argument to create backup before deployment"
        echo "Example: $0 prod backup"
        exit 1
        ;;
esac
