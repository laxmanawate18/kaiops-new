#!/usr/bin/env python3
"""
Main entry point for the ADK FastAPI application.
Run this file to start the server.
"""

import sys
import os
from pathlib import Path

# Load environment variables FIRST, before any other imports
from dotenv import load_dotenv
load_dotenv()

# Add project root to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

import uvicorn
if __name__ == "__main__":
    print("Starting ADK FastAPI Server...")
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/api/v1/health")
    print("Chat Endpoint: http://localhost:8000/api/v1/chat")
    
    try:
        from app.main import app
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except Exception as e:
        print(f"FAILED TO START UVICORN: {e}")
        raise
