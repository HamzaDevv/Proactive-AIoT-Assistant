import os
import hmac
import hashlib
import json
import httpx
from typing import Dict, Any, List, Optional

class HAClient:
    def __init__(self):
        self.base_url = os.getenv("HA_TUNNEL_URL", "http://localhost:8123")
        self.secret = os.getenv("TUNNEL_HMAC_SECRET", "")
        self.token = os.getenv("HA_TOKEN", "") # Long-lived access token

    def _sign_request(self, body: Dict[str, Any]) -> str:
        if not self.secret:
            return ""
        payload = json.dumps(body, sort_keys=True).encode()
        return hmac.new(self.secret.encode(), payload, hashlib.sha256).hexdigest()

    def _get_headers(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        if body and self.secret:
            headers["X-HA-Signature"] = self._sign_request(body)
        return headers

    async def get_state(self, entity_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/states/{entity_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Error fetching state for {entity_id}: {e}")
                return {"state": "unknown"}

    async def get_zone_states(self, entity_ids: List[str]) -> Dict[str, str]:
        """Fetch states for a list of entities in parallel."""
        states = {}
        async with httpx.AsyncClient() as client:
            for eid in entity_ids:
                try:
                    response = await client.get(
                        f"{self.base_url}/api/states/{eid}",
                        headers=self._get_headers()
                    )
                    if response.status_code == 200:
                        states[eid] = response.json().get("state", "unknown")
                    else:
                        states[eid] = "unknown"
                except Exception:
                    states[eid] = "unknown"
        return states

    async def call_service(self, domain: str, service: str, service_data: Dict[str, Any]):
        headers = self._get_headers(service_data)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/services/{domain}/{service}",
                    json=service_data,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Error calling service {domain}.{service}: {e}")
                return {"status": "error", "message": str(e)}

ha_client = HAClient()
