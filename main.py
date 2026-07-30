#!/usr/bin/env python3
"""
Convenience entrypoint — run the API with:

    python main.py

Equivalent to:

    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Host/port/reload are read from the environment so nothing here is
hardcoded; see .env.example.
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").strip().lower() == "true",
    )
