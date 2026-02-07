import requests
import time
from typing import List, Dict


class MBTAFetcher:
    BASE_URL = "https://api-v3.mbta.com"

    STATION_IDS = {
        "Malden Center": "place-mlmnl",
        "Wellington": "place-welln",
        "ADD STATIONS": "AS NEEDED"
    }

    def __init__(self, api_key: str = None):
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"x-api-key": api_key})

    def get_orange_line_southbound(self, station_name: str) -> List[Dict]:
        if station_name not in self.STATION_IDS:
            raise ValueError(f"Station {station_name} not found.")
        stop_id = self.STATION_IDS[station_name]
        return self.get_predictions("Orange", stop_id, direction_id=0)

    def get_route_stop_map(self, route_id: str, direction_id: int) -> Dict[int, str]:
        endpoint = f"{self.BASE_URL}/stops"
        params = {
            "filter[route]": route_id,
            "filter[direction_id]": direction_id
        }
        try:
            response = self.session.get(endpoint, params=params)
            data = response.json().get("data", [])
            # Map sequence (1-based) to Stop Name
            return {i + 1: stop['attributes']['name'] for i, stop in enumerate(data)}
        except Exception as e:
            print(f"Error building stop map for {route_id}: {e}")
            return {}

    def get_predictions(self, route_id: str, stop_id: str, direction_id: int = None, stop_map: Dict = None) -> List[
        Dict]:
        # ADDED: Tiny throttle to prevent 429s
        time.sleep(0.1)

        endpoint = f"{self.BASE_URL}/predictions"
        params = {
            "filter[route]": route_id,
            "filter[stop]": stop_id,
            "include": "vehicle",
            "sort": "arrival_time"
        }
        if direction_id is not None:
            params["filter[direction_id]"] = direction_id

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            json_data = response.json()

            included_map = {
                (item['type'], item['id']): item
                for item in json_data.get("included", [])
            }
            return self._parse_predictions(json_data.get("data", []), included_map, stop_map)
        except Exception as e:
            print(f"Error fetching predictions for {route_id}: {e}")
            return []

    def _parse_predictions(self, data: List[Dict], included_map: Dict, stop_map: Dict = None) -> List[Dict]:
        clean_results = []
        for item in data:
            attrs = item.get("attributes", {})
            location_desc = "Location unknown"
            current_seq = None

            vehicle_rel = item.get("relationships", {}).get("vehicle", {}).get("data")
            if vehicle_rel:
                veh = included_map.get(("vehicle", vehicle_rel['id']))
                if veh:
                    v_attrs = veh.get("attributes", {})
                    status = v_attrs.get("current_status", "").replace("_", " ").title()
                    current_seq = v_attrs.get("current_stop_sequence")

                    stop_name = "en route"
                    if stop_map and current_seq in stop_map:
                        stop_name = stop_map[current_seq]

                    location_desc = f"{status} {stop_name}"

            clean_results.append({
                "time": attrs.get("arrival_time") or attrs.get("departure_time"),
                "location": location_desc,
                "current_seq": current_seq
            })
        return clean_results