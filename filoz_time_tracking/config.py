"""Load config from environment."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_sheet_id() -> str:
    v = os.environ.get("FILOZ_SHEET_ID")
    if not v:
        raise ValueError("FILOZ_SHEET_ID is not set (e.g. in .env)")
    return v.strip()


def get_tracking_sheet_name() -> str:
    return os.environ.get("FILOZ_TRACKING_SHEET_NAME", "Tracking").strip()


def get_credentials_path() -> str | None:
    return os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or None
