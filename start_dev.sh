#!/bin/bash

# Reddit Automation Dashboard - Development Startup Script
# This script helps you quickly start the development environment

echo "🤖 Reddit Automation Dashboard - Development Setup"
echo "=================================================="

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "❌ Environment file not found!"
    echo "📝 Please copy backend/.env.example to backend/.env and configure your Reddit API credentials"
    echo ""
    echo "Steps:"
    echo "1. cp backend/.env.example backend/.env"
    echo "2. Edit backend/.env with your Reddit API credentials"
    echo "3. Run this script again"
    exit 1
fi

echo "✅ Environment file found"

# Check if Docker is available
if command -v docker-compose &> /dev/null; then
    echo "🐳 Docker Compose detected - Starting with Docker..."
    echo ""
    echo "Starting services..."
    docker-compose up -d
    
    echo ""
    echo "🎉 Application started successfully!"
    echo ""
    echo "📱 Frontend: http://localhost:3000"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📚 API Docs: http://localhost:8000/docs"
    echo "🤖 Test Form: http://localhost:3000/test-form"
    echo ""
    echo "To stop the application, run: docker-compose down"
    
elif command -v python3 &> /dev/null && command -v npm &> /dev/null; then
    echo "🐍 Python and Node.js detected - Starting manually..."
    echo ""
    
    # Start Redis and PostgreSQL with Docker if available
    if command -v docker &> /dev/null; then
        echo "Starting Redis and PostgreSQL with Docker..."
        docker run -d --name redis-reddit -p 6379:6379 redis:7 2>/dev/null || echo "Redis container already running"
        docker run -d --name postgres-reddit -p 5432:5432 \
            -e POSTGRES_USER=reddituser \
            -e POSTGRES_PASSWORD=redditpass \
            -e POSTGRES_DB=redditdb \
            postgres:15 2>/dev/null || echo "PostgreSQL container already running"
        
        sleep 3
    fi
    
    # Setup backend
    echo "Setting up backend..."
    cd backend
    
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Initialize database
    echo "Initializing database..."
    python setup_db.py
    
    # Start backend in background
    echo "Starting backend server..."
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    
    cd ..
    
    # Setup frontend
    echo "Setting up frontend..."
    cd frontend
    
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install
    fi
    
    # Start frontend in background
    echo "Starting frontend server..."
    npm start &
    FRONTEND_PID=$!
    
    cd ..
    
    echo ""
    echo "🎉 Application started successfully!"
    echo ""
    echo "📱 Frontend: http://localhost:3000"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📚 API Docs: http://localhost:8000/docs"
    echo "🤖 Test Form: http://localhost:3000/test-form"
    echo ""
    echo "Press Ctrl+C to stop all services"
    
    # Wait for interrupt
    trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
    wait
    
else
    echo "❌ Required dependencies not found!"
    echo ""
    echo "Please install:"
    echo "- Docker & Docker Compose (recommended), OR"
    echo "- Python 3.12+ and Node.js 18+"
    echo ""
    echo "Then run this script again."
    exit 1
fi
