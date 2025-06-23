# Contributing to Reddit Automation Dashboard

Thank you for your interest in contributing to the Reddit Automation Dashboard! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Development Environment Setup

1. **Fork and Clone**
   ```bash
   git fork https://github.com/yourusername/reddit-tool.git
   git clone https://github.com/yourusername/reddit-tool.git
   cd reddit-tool
   ```

2. **Environment Setup**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your Reddit API credentials
   ```

3. **Start Development Environment**
   ```bash
   ./start_dev.sh
   ```

### Project Structure

```
reddit-tool/
├── backend/                 # FastAPI backend
│   ├── routers/            # API route handlers
│   ├── models.py           # SQLAlchemy database models
│   ├── reddit_service.py   # Reddit API integration
│   ├── engagement_service.py # Engagement tracking
│   ├── karma_service.py    # Karma analytics
│   ├── nlp_service.py      # NLP and sentiment analysis
│   ├── automation_*.py     # Automation logic
│   ├── safety_*.py         # Safety monitoring
│   └── test_*.py           # Backend tests
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── charts/         # Chart components
│   │   └── App.js          # Main app component
│   └── reddit-test-form.html # Standalone test form
├── docker-compose.yml      # Docker services
├── start_dev.sh           # Development startup script
└── README.md              # Project documentation
```

## 🛠️ Development Guidelines

### Code Style

**Backend (Python)**
- Follow PEP 8 style guidelines
- Use type hints where possible
- Add docstrings to all functions and classes
- Use meaningful variable and function names

**Frontend (JavaScript/React)**
- Use functional components with hooks
- Follow React best practices
- Use Tailwind CSS for styling
- Keep components small and focused

### Testing

**Backend Tests**
```bash
cd backend
python -m pytest
# Or run specific tests
python test_karma.py
python test_engagement.py
```

**Frontend Tests**
```bash
cd frontend
npm test
```

### Database Changes

When modifying database models:

1. Update `models.py`
2. Create Alembic migration:
   ```bash
   cd backend
   alembic revision --autogenerate -m "Description of changes"
   alembic upgrade head
   ```
3. Update test data if needed

## 📝 Contribution Process

### 1. Issue Creation

Before starting work:
- Check existing issues
- Create a new issue describing the feature/bug
- Wait for maintainer feedback before starting work

### 2. Branch Naming

Use descriptive branch names:
- `feature/add-advanced-analytics`
- `bugfix/fix-karma-calculation`
- `improvement/optimize-database-queries`

### 3. Commit Messages

Use conventional commit format:
```
type(scope): description

feat(analytics): add subreddit performance metrics
fix(reddit): resolve rate limiting issues
docs(readme): update installation instructions
```

### 4. Pull Request Process

1. **Create PR** with descriptive title and description
2. **Link related issues** using "Fixes #123" or "Closes #123"
3. **Add screenshots** for UI changes
4. **Ensure tests pass** and add new tests if needed
5. **Request review** from maintainers

## 🎯 Areas for Contribution

### High Priority
- [ ] Advanced ML-based content optimization
- [ ] Enhanced human behavior simulation
- [ ] Mobile-responsive design improvements
- [ ] Performance optimizations

### Medium Priority
- [ ] Additional chart types and visualizations
- [ ] More comprehensive test coverage
- [ ] API rate limiting improvements
- [ ] Better error handling and user feedback

### Low Priority
- [ ] Dark mode theme
- [ ] Additional export formats
- [ ] Internationalization (i18n)
- [ ] Advanced filtering options

## 🔒 Security Guidelines

- Never commit API keys or sensitive data
- Use environment variables for configuration
- Follow OWASP security best practices
- Report security vulnerabilities privately

## 📚 Resources

- [Reddit API Documentation](https://www.reddit.com/dev/api/)
- [PRAW Documentation](https://praw.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://reactjs.org/docs/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)

## 🤝 Community

- Be respectful and inclusive
- Help other contributors
- Follow the code of conduct
- Ask questions in issues or discussions

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to the Reddit Automation Dashboard! 🎉
