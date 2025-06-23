#!/usr/bin/env python3
"""
Quick start script for Reddit Automation Dashboard
Run this to start the server and open the test form
"""
import subprocess
import sys
import time
import webbrowser
import os

def main():
    print("🚀 Starting Reddit Automation Dashboard...")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("backend/main.py"):
        print("❌ Error: Please run this script from the reddit-tool directory")
        print("Current directory:", os.getcwd())
        return
    
    # Start the FastAPI server
    print("📡 Starting FastAPI server...")
    try:
        # Change to backend directory and start server
        os.chdir("backend")
        
        print("🔧 Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=False, capture_output=True)
        
        print("🌐 Starting server on http://localhost:8000")
        print("📋 Test form will be available at: http://localhost:8000/test-form")
        print("📚 API docs will be available at: http://localhost:8000/docs")
        print()
        print("🔧 IMPORTANT SETUP STEPS:")
        print("1. Make sure you have a .env file with your Reddit API credentials")
        print("2. Connect a Reddit account using the /accounts endpoints")
        print("3. Use the test form to submit posts and comments")
        print()
        print("Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ])
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("\nTry running manually:")
        print("cd backend")
        print("pip install -r requirements.txt")
        print("uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

if __name__ == "__main__":
    main()
