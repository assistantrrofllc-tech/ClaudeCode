"""Test configuration — runs before any test module imports."""
import os

# Prevent APScheduler from starting during tests
os.environ["TESTING"] = "1"
