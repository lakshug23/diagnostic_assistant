#!/bin/bash

# MedSAGE Quick Start Guide
# Run this script to start MedSAGE in production mode

echo "🏥 Starting MedSAGE Diagnostic Assistant..."
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please ensure .env is configured."
    exit 1
fi

echo "✅ Environment configuration found"

# Start the system
echo "🚀 Starting MedSAGE containers..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to initialize..."
sleep 15

# Check health
echo "🔍 Checking system health..."
if curl -f http://localhost:5001/health > /dev/null 2>&1; then
    echo ""
    echo "🎉 MedSAGE is now running successfully!"
    echo ""
    echo "📱 Access Points:"
    echo "   • Main Application: http://localhost:5001"
    echo "   • Via Nginx Proxy: http://localhost"
    echo "   • Health Check: http://localhost:5001/health"
    echo ""
    echo "🛑 To stop MedSAGE: docker-compose down"
    echo "📊 View logs: docker-compose logs -f"
    echo "📈 Container status: docker-compose ps"
else
    echo "⚠️  System may still be starting. Check status with: docker-compose ps"
    echo "📋 View logs with: docker-compose logs -f"
fi
# For testing
FLASK_ENV=testing
DATABASE_NAME=medsage_test_db

# For development  
FLASK_ENV=development
DATABASE_NAME=medsage_db

# For production
FLASK_ENV=production
DATABASE_NAME=medsage_production