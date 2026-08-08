from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

HEADERS = [
    "Timestamp",
    "Channel",
    "Customer Name",
    "Phone",
    "Unit ID",
    "Listing Type",
    "Preferred Date",
    "Preferred Time",
    "Status",
    "Notes",
    "Customer ID",
]


def _get_worksheet():
    if not settings.google_sheets_credentials_file or not settings.google_sheet_id:
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            settings.google_sheets_credentials_file,
            scopes=scopes,
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(settings.google_sheet_id)
        try:
            worksheet = spreadsheet.worksheet(settings.google_sheet_tab)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=settings.google_sheet_tab, rows=1000, cols=len(HEADERS))
        return worksheet
    except Exception as error:
        logger.exception("Failed to connect to Google Sheets: %s", error)
        return None


def ensure_headers() -> None:
    worksheet = _get_worksheet()
    if not worksheet:
        return
    existing = worksheet.row_values(1)
    if existing != HEADERS:
        worksheet.update("A1", [HEADERS])


def append_appointment(record: dict[str, Any]) -> bool:
    worksheet = _get_worksheet()
    if not worksheet:
        logger.warning("Google Sheets not configured; appointment stored locally only.")
        return False

    ensure_headers()
    row = [
        record.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        record.get("channel", ""),
        record.get("customer_name", ""),
        record.get("phone", ""),
        record.get("unit_id", ""),
        record.get("listing_type", ""),
        record.get("preferred_date", ""),
        record.get("preferred_time", ""),
        record.get("status", "New"),
        record.get("notes", ""),
        record.get("customer_id", ""),
    ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return True
