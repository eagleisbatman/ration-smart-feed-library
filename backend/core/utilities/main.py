#!/usr/bin/env python3
"""
Feed Formulation Backend - Main Entry Point
This file serves as the entry point for deployment and direct execution.
It imports the FastAPI app from the app module.
"""

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
