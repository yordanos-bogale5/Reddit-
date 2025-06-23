# 🤖 Reddit Automation Dashboard

A comprehensive Reddit automation and analytics platform built with React, FastAPI, and PostgreSQL. This tool provides intelligent Reddit account management, automated posting, engagement tracking, and advanced analytics for Reddit marketing and community management.

## ✨ Features

### 🎯 Core Automation Features
- **🚀 Automated Posting & Commenting** - Schedule and automate Reddit posts and comments
- **📊 Karma Growth Tracking** - Monitor and optimize karma growth across accounts
- **🎯 Subreddit Analytics** - Deep insights into subreddit performance and targeting
- **⏰ Activity Scheduling** - Smart scheduling with human behavior simulation
- **🛡️ Safety Monitoring** - Real-time account health and safety alerts

### 📈 Analytics & Insights
- **📋 Engagement Logs** - Detailed activity tracking and performance metrics
- **🏥 Account Health Dashboard** - Monitor account status, bans, and trust scores
- **📊 Success Rate Tracking** - Track and optimize automation success rates
- **📤 Data Export & Reporting** - Export analytics data in multiple formats

### 🧠 Advanced Features
- **🤖 NLP Comment Quality Control** - AI-powered content quality analysis
- **👤 Human Behavior Simulation** - Realistic posting patterns and timing
- **🔧 Customization Settings** - Flexible automation rules and preferences
- **🔐 OAuth2 Account Management** - Secure Reddit account integration

## 🛠️ Tech Stack

- **Frontend**: React 18 + Tailwind CSS + Recharts
- **Backend**: FastAPI + Python 3.12
- **Database**: PostgreSQL 15 + SQLAlchemy
- **Task Queue**: Celery + Redis
- **Reddit API**: PRAW (Python Reddit API Wrapper)
- **AI/NLP**: Transformers, spaCy, NLTK, VADER Sentiment
- **Containerization**: Docker + Docker Compose

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose (recommended)
- Reddit API credentials

### 🔧 Installation

#### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/reddit-tool.git
   cd reddit-tool
   ```

2. **Set up environment variables**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your Reddit API credentials
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

#### Option 2: Manual Setup

1. **Clone and setup backend**
   ```bash
   git clone https://github.com/yourusername/reddit-tool.git
   cd reddit-tool/backend

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Setup environment
   cp .env.example .env
   # Edit .env with your credentials

   # Initialize database
   python setup_db.py

   # Start backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Setup frontend** (in new terminal)
   ```bash
   cd reddit-tool/frontend

   # Install dependencies
   npm install

   # Start frontend
   npm start
   ```

3. **Setup Redis & PostgreSQL**
   ```bash
   # Using Docker for services only
   docker run -d -p 6379:6379 redis:7
   docker run -d -p 5432:5432 -e POSTGRES_USER=reddituser -e POSTGRES_PASSWORD=redditpass -e POSTGRES_DB=redditdb postgres:15
   ```

## 🔑 Configuration

### Reddit API Setup

1. **Create Reddit App**
   - Go to https://www.reddit.com/prefs/apps
   - Click "Create App" or "Create Another App"
   - Choose "web app"
   - Set redirect URI to: `http://localhost:8000/auth/reddit/callback`

2. **Configure Environment Variables**
   ```env
   # Reddit API
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=YourApp/1.0 by YourUsername

   # Database
   DATABASE_URL=postgresql://reddituser:redditpass@localhost:5432/redditdb

   # Redis
   REDIS_URL=redis://localhost:6379/0

   # Security
   SECRET_KEY=your-secret-key-here
   ```

## 🎮 Usage Guide

### 🤖 Reddit Actions Test Form

The easiest way to get started is with our interactive test form:

1. **Access the test form**: http://localhost:3000/test-form
2. **Connect Reddit Account**:
   - Click "Connect Reddit Account"
   - Authorize the application
   - Your account will be saved for future use

3. **Test Post Submission**:
   - Select your connected account
   - Choose a subreddit (recommended: `test`, `testingground4bots`)
   - Enter post title and body
   - Leave URL empty for text posts
   - Click "Submit Post"

4. **Test Comment Submission**:
   - Find a Reddit post ID from any post URL
   - Enter the post ID and your comment text
   - Submit the comment

### 📊 Main Dashboard

Access the full dashboard at http://localhost:3000:

- **Dashboard**: Overview of all accounts and activities
- **Karma Reports**: Track karma growth and trends
- **Engagement Logs**: View detailed activity history
- **Activity Schedule**: Set up automated posting schedules
- **Subreddit Analytics**: Analyze subreddit performance
- **Account Health**: Monitor account safety and status
- **Settings**: Configure automation preferences

## 🧪 Testing

### Backend Tests
```bash
cd backend
python -m pytest
# Or run specific test files
python test_karma.py
python test_engagement.py
python test_automation.py
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 📚 API Documentation

- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Key API Endpoints

- `POST /reddit/submit-post` - Submit Reddit posts
- `POST /reddit/submit-comment` - Submit Reddit comments
- `GET /analytics/karma/{account_id}` - Get karma analytics
- `GET /analytics/engagement/{account_id}` - Get engagement data
- `POST /automation/schedule-task` - Schedule automation tasks
- `GET /health/account/{account_id}` - Get account health status

## 🔒 Security & Safety

- **Rate Limiting**: Built-in Reddit API rate limiting
- **Account Health Monitoring**: Real-time safety alerts
- **Human Behavior Simulation**: Realistic activity patterns
- **Content Quality Control**: NLP-powered content analysis
- **OAuth2 Security**: Secure Reddit account integration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and legitimate marketing purposes only. Users are responsible for complying with Reddit's Terms of Service and API guidelines. Always respect community rules and Reddit's content policy.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/reddit-tool/issues)
- **Documentation**: Check the `/docs` folder for detailed guides
- **Reddit API**: [PRAW Documentation](https://praw.readthedocs.io/)

## 🎯 Roadmap

- [ ] Advanced ML-based content optimization
- [ ] Multi-platform social media integration
- [ ] Advanced sentiment analysis dashboard
- [ ] Automated A/B testing for posts
- [ ] Enhanced human behavior simulation
- [ ] Mobile app development

---

**Made with ❤️ for the Reddit community**
