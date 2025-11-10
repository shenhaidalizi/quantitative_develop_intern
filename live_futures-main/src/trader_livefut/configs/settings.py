import os
from pathlib import Path

# Define the base directory for the live_futures project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Define the path for live data, relative to the project's base directory
FUTURES_LIVE_DATA_PATH = os.path.join(BASE_DIR, 'data', 'live_futures')

# Ensure the live data directory exists
os.makedirs(FUTURES_LIVE_DATA_PATH, exist_ok=True)
