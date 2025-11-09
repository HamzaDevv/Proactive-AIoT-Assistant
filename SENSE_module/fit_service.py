# fit_service.py

import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.nutrition.read",  # <-- ADD THIS
    "https://www.googleapis.com/auth/fitness.nutrition.write",  # (optional: only if you ever want to *log* calories)
]


TOKEN_FILE = "token.json"
CREDS_FILE = "SENSE_module/credentials.json"
LOCAL_TZ = "Asia/Kolkata"
DAY_MS = 86400000

STEP_DATATYPE = "com.google.step_count.delta"
HR_DATATYPE = "com.google.heart_rate.bpm"
CAL_DATATYPE = "com.google.calories.expended"


class FitService:
    def __init__(self, auto_authorize: bool = True):
        """Initialize the Fit service with optional auto authorization."""
        self.creds = None
        self._load_credentials()
        if auto_authorize:
            self._ensure_authorized()
        self.service = build("fitness", "v1", credentials=self.creds)

    def _load_credentials(self):
        """Load existing credentials if available."""
        if os.path.exists(TOKEN_FILE):
            try:
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                self.creds = None

    def _ensure_authorized(self):
        """Ensure we have valid credentials, requesting authorization if needed."""
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    self.creds = None

            if not self.creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    # Save the credentials for the next run
                    with open(TOKEN_FILE, "w") as token:
                        token.write(self.creds.to_json())
                except Exception as e:
                    raise RuntimeError(f"Failed to authorize: {e}")

    @staticmethod
    def _last_n_days_ms(n: int) -> tuple[int, int]:
        end = int(time.time() * 1000)
        start = end - (n * DAY_MS)
        return start, end

    @staticmethod
    def _today_range_ms() -> tuple[int, int]:
        now = datetime.now()
        start = int(
            now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
        )
        end = start + DAY_MS
        return (start, end)

    def _aggregate_daily(self, data_type_name: str, start_ms: int, end_ms: int):
        body = {
            "aggregateBy": [{"dataTypeName": data_type_name}],  # <-- No dataSourceId
            "bucketByTime": {"durationMillis": DAY_MS, "timeZoneId": LOCAL_TZ},
            "startTimeMillis": start_ms,
            "endTimeMillis": end_ms,
        }
        return (
            self.service.users().dataset().aggregate(userId="me", body=body).execute()
        )

    @staticmethod
    def _parse_calories(agg: Dict[str, Any]) -> List[Optional[float]]:
        results = []
        for bucket in agg.get("bucket", []):
            total = 0.0
            for dataset in bucket.get("dataset", []):
                for p in dataset.get("point", []):
                    for v in p.get("value", []):
                        if "fpVal" in v:
                            total += float(v["fpVal"])
            results.append(round(total, 2) if total > 0 else None)
        return results

    @staticmethod
    def _parse_steps(agg: Dict[str, Any]) -> List[int]:
        results = []
        for bucket in agg.get("bucket", []):
            total = 0
            for dataset in bucket.get("dataset", []):
                for p in dataset.get("point", []):
                    for v in p.get("value", []):
                        total += v.get("intVal", 0)
            results.append(total)
        return results

    @staticmethod
    def _parse_hr(agg: Dict[str, Any]) -> List[Optional[float]]:
        avgs = []
        for bucket in agg.get("bucket", []):
            values = []
            for dataset in bucket.get("dataset", []):
                for p in dataset.get("point", []):
                    for v in p.get("value", []):
                        if "fpVal" in v:
                            values.append(v["fpVal"])
            if values:
                avgs.append(sum(values) / len(values))
            else:
                avgs.append(None)
        return avgs

    def get_today_steps(self) -> int:
        s, e = self._today_range_ms()
        agg = self._aggregate_daily(STEP_DATATYPE, s, e)
        steps = self._parse_steps(agg)
        return steps[0] if steps else 0

    def get_today_hr_avg(self) -> Optional[float]:
        s, e = self._today_range_ms()
        agg = self._aggregate_daily(HR_DATATYPE, s, e)
        hr = self._parse_hr(agg)
        return hr[0] if hr else None

    def get_daily_hr_avg(self, days: int = 7) -> List[Optional[float]]:
        s, e = self._last_n_days_ms(days)
        agg = self._aggregate_daily(HR_DATATYPE, s, e)
        return self._parse_hr(agg)

    def get_daily_steps(self, days: int = 7) -> List[int]:
        s, e = self._last_n_days_ms(days)
        agg = self._aggregate_daily(STEP_DATATYPE, s, e)
        return self._parse_steps(agg)

    def get_today_calories(self) -> Optional[float]:
        s, e = self._today_range_ms()
        agg = self._aggregate_daily(CAL_DATATYPE, s, e)
        cals = self._parse_calories(agg)
        return cals[0] if cals else None

    def get_daily_calories(self, days: int = 7) -> List[Optional[float]]:
        s, e = self._last_n_days_ms(days)
        agg = self._aggregate_daily(CAL_DATATYPE, s, e)
        return self._parse_calories(agg)
