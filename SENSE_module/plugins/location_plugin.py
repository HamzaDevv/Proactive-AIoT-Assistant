import requests
import SENSE_module.shared_state
from typing import Dict, Any, cast
from .base_plugin import BasePlugin
from dotenv import load_dotenv
import os
import googlemaps

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DESTINATION_ADDRESS = os.getenv("DESTINATION_ADDRESS")  # e.g., "IIEST Shibpur, Howrah"
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY) if GOOGLE_MAPS_API_KEY else None


class LocationPlugin(BasePlugin):
    async def sense(self) -> Dict[str, Any]:
        # ✅ If browser location is available (high confidence)
        if shared_state.LAST_LOCATION:
            lat, lon = shared_state.LAST_LOCATION
            place = self.reverse_geocode(lat, lon)
            eta = (
                self.estimate_eta(lat, lon, DESTINATION_ADDRESS)
                if DESTINATION_ADDRESS
                else None
            )
            return {
                "location": {"place": place, "travel_eta_min": eta, "confidence": 0.98}
            }

        # 🟡 Fallback: IP-based location (mid confidence)
        try:
            loc = requests.get("https://ipinfo.io/json").json()
            lat, lon = map(float, loc["loc"].split(","))
            place = self.reverse_geocode(lat, lon)
            eta = (
                self.estimate_eta(lat, lon, DESTINATION_ADDRESS)
                if DESTINATION_ADDRESS
                else None
            )

            return {
                "location": {"place": place, "travel_eta_min": eta, "confidence": 0.45}
            }

        except:
            # ❌ No location at all
            return {
                "location": {"place": None, "travel_eta_min": None, "confidence": 0.30}
            }

    def reverse_geocode(self, lat: float, lon: float) -> str:
        """Convert GPS → Place Name (Human readable)."""
        if not GOOGLE_MAPS_API_KEY:
            return f"{lat:.5f}, {lon:.5f}"

        url = (
            "https://maps.googleapis.com/maps/api/geocode/json"
            f"?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
        )
        try:
            data = requests.get(url).json()
            results = data.get("results", [])
            if results:
                return results[0]["formatted_address"]
        except:
            pass

        return f"{lat:.5f}, {lon:.5f}"

    def estimate_eta(self, lat: float, lon: float, destination: str) -> Any:
        """Returns travel time in minutes using Google Distance Matrix."""
        if not gmaps:
            return None

        try:
            result = cast(Any, gmaps).distance_matrix(
                origins=[(lat, lon)], destinations=[destination], mode="walking"
            )

            sec = result["rows"][0]["elements"][0]["duration"]["value"]
            return round(sec / 60)  # convert seconds to minutes

        except:
            return None
