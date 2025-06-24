from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging
import os

from routers import accounts, automation, analytics, admin, nlp, safety, export, targeting, behavior, health, reddit_actions, discord_promotion, anti_detection
from database import create_tables
from error_handler import global_exception_handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Reddit Automation & Analytics Dashboard",
    description="A comprehensive Reddit automation and analytics platform",
    version="1.0.0"
)

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Creating database tables...")
    create_tables()
    logger.info("Database tables created successfully")

@app.get("/", summary="Health check")
def health_check():
    return {"status": "ok", "message": "Reddit Automation & Analytics Dashboard API"}

@app.get("/test-form", summary="Reddit Actions Test Form")
def get_test_form():
    """Serve the Reddit actions test form"""
    form_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "reddit-test-form.html")
    if os.path.exists(form_path):
        return FileResponse(form_path)
    else:
        return {"error": "Test form not found", "path": form_path}

@app.get("/callback", summary="Reddit OAuth callback (root level)")
def root_oauth_callback(code: str, state: str):
    """Handle Reddit OAuth callback at root level"""
    from fastapi import Depends
    from database import get_db
    from routers.accounts import handle_oauth_callback
    from sqlalchemy.orm import Session

    # This is a workaround - we'll redirect to the accounts callback
    return {"message": "Please use /accounts/oauth/callback instead", "code": code, "state": state}

app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(automation.router, prefix="/automation", tags=["Automation"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(nlp.router, prefix="/nlp", tags=["NLP"])
app.include_router(safety.router, prefix="/safety", tags=["Safety"])
app.include_router(export.router, prefix="/export", tags=["Export"])
app.include_router(targeting.router, prefix="/targeting", tags=["Targeting"])
app.include_router(behavior.router, prefix="/behavior", tags=["Behavior"])
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(reddit_actions.router, prefix="/reddit", tags=["Reddit Actions"])
app.include_router(discord_promotion.router, prefix="/discord-promotion", tags=["Discord Promotion"])
app.include_router(anti_detection.router, prefix="/anti-detection", tags=["Anti-Detection"])