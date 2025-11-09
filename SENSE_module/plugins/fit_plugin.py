# plugins/fit_plugin.py

import asyncio
from typing import Dict, Any

from .base_plugin import BasePlugin
from SENSE_module.fit_service import FitService


class FitPlugin(BasePlugin):
    def __init__(self):
        self.fit = FitService()

    async def sense(self) -> Dict[str, Any]:
        today_steps, today_hr, last7_hr, today_cal = await asyncio.gather(
            asyncio.to_thread(self.fit.get_today_steps),
            asyncio.to_thread(self.fit.get_today_hr_avg),
            asyncio.to_thread(self.fit.get_daily_hr_avg, 7),
            asyncio.to_thread(self.fit.get_today_calories),
        )

        if today_hr is None:
            clean = [x for x in last7_hr if x]
            today_hr = sum(clean) / len(clean) if clean else 75

        if today_steps < 1500:
            state = "idle"
        elif today_steps < 8000:
            state = "walking"
        else:
            state = "post_workout"

        hr = int(
            today_hr
            + (10 if state == "walking" else (25 if state == "post_workout" else 0))
        )

        clean_hr = [x for x in last7_hr if x]
        stress = (
            "high" if clean_hr and hr > (sum(clean_hr) / len(clean_hr)) + 5 else "low"
        )

        return {
            "fit": {
                "heart_rate": hr,
                "activity_status": state,
                "stress_level": stress,
                "calories_today": today_cal,
                "confidence": 0.95,
            }
        }
