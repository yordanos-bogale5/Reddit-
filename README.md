# Reddit Automation & Analytics Dashboard

## Features
- Reddit account automation (karma growth, engagement, analytics)
- Multi-account support
- FastAPI backend, React + Tailwind frontend
- PostgreSQL, Redis, Celery
- Dockerized for easy deployment

## Quick Start

1. **Clone the repo:**
   ```bash
   git clone <repo-url>
   cd reddit-tool
   ```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env` in `backend/` and fill in Reddit API credentials and secrets.

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

4. **Access the app:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/docs

## Directory Structure
- `backend/` - FastAPI, Celery, PRAW, PostgreSQL
- `frontend/` - React, Tailwind CSS

## Customization
- Configure automation and analytics in the dashboard UI.

## Exporting Data
- Use dashboard export buttons or API endpoints for CSV/JSON.

## NLP (Optional)
- Sentiment analysis via HuggingFace Transformers (toggle in settings).

## License
MIT # Reddit-
