"""
CrewLedger application settings.

Reads from environment variables (or .env file).
All config lives here — no magic strings scattered through the codebase.
"""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "crewledger.db"))
RECEIPT_STORAGE_PATH = os.getenv("RECEIPT_STORAGE_PATH", str(PROJECT_ROOT / "storage" / "receipts"))
CERT_STORAGE_PATH = os.getenv("CERT_STORAGE_PATH", str(PROJECT_ROOT / "storage" / "certifications"))

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# OpenAI (GPT-4o-mini Vision for receipt OCR)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Ollama (local AI)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Email reports
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ACCOUNTANT_EMAIL = os.getenv("ACCOUNTANT_EMAIL", "")

# Application
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
APP_DEBUG = os.getenv("APP_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
