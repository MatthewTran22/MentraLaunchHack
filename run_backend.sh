#!/bin/bash
# Run the FastAPI backend server

uv run uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8000


