import requests
import polyline
from typing import List, Dict


class MBTAFetcher:
    BASE_URL = "https://api-v3.mbta.com"
    STATION_IDS = {"Malden Center": "place-mlmnl", "Wellington": "place-welln"}

    def __init__(self, api_key: str = None):
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"x-api-key": api_key})

    def get_orange_line_southbound(self, station_name: str) -> List[Dict]:
        """
        Returns the list of attributes for Orange Line trains southbound
        :param station_name: Malden or Wellington
        :return: list of prediction attributes
        """
        if station_name not in self.STATION_IDS:
            raise ValueError(f"Station {station_name} not found.")
        stop_id = self.STATION_IDS[station_name]
        return self.get_predictions("Orange", stop_id, direction_id=0)

    def get_route_stop_map(self, route_id: str, direction_id: int) -> Dict[int, str]:
        """
        Queries MBTA API and creates a bus route map of stop ids and stop names
        :param route_id: numeric route id
        :param direction_id:    southbound/northbound or inbound/outbound
                                represented by 0 or 1
        :return: dictionary of bus stops
        """
        endpoint = f"{self.BASE_URL}/stops"
        params = {"filter[route]": route_id, "filter[direction_id]": direction_id}
        try:
            response = self.session.get(endpoint, params=params)
            data = response.json().get("data", [])
            return {i + 1: stop["attributes"]["name"] for i, stop in enumerate(data)}
        except Exception as e:
            print(f"Error building stop map for {route_id}: {e}")
            return {}

    def get_route_shape(self, route_id: str) -> List[List[float]]:
        """
        Fetches the longest shape for a route (usually the main path)
        and decodes it into GPS coordinates.
        """
        # 1. Query the shapes endpoint directly filtered by route
        endpoint = f"{self.BASE_URL}/shapes"
        params = {
            "filter[route]": route_id,
            "sort": "-length",  # Optional: tries to get the longest one first
        }

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            json_data = response.json()
            data = json_data.get("data", [])

            if not data:
                print(f"No shapes found for route {route_id}")
                return []

            # 2. Pick the first shape returned (usually the most 'typical' or longest)
            # MBTA shapes are returned as encoded polylines
            encoded_polyline = data[0]["attributes"].get("polyline")

            if encoded_polyline:
                return polyline.decode(encoded_polyline)

        except Exception as e:
            print(f"Error fetching shape for {route_id}: {e}")

        return []

    def get_predictions(
        self,
        route_id: str,
        stop_id: str,
        direction_id: int = None,
        stop_map: Dict = None,
    ) -> List[Dict]:
        """
        Queries predictions from MBTA API, using GET requests
        :param route_id: train station name or bus route id
        :param stop_id: train id or bus id
        :param direction_id: either 0 or 1
        :param stop_map: dictionary containing bus stop id and name
        :return: list of parsed attributes
        """

        endpoint = f"{self.BASE_URL}/predictions"
        params = {
            "filter[route]": route_id,
            "filter[stop]": stop_id,
            "include": "vehicle",
            "sort": "arrival_time",
            # "page[limit]": 15,
        }
        if direction_id is not None:
            params["filter[direction_id]"] = direction_id

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            json_data = response.json()

            included_map = {
                (item["type"], item["id"]): item
                for item in json_data.get("included", [])
            }
            return self._parse_predictions(
                json_data.get("data", []), included_map, stop_map
            )
        except Exception as e:
            print(f"Error fetching predictions for {route_id}: {e}")
            return []

    @staticmethod
    def _parse_predictions(
        data: List[Dict], included_map: Dict, stop_map: Dict = None
    ) -> List[Dict]:
        clean_results = []
        for item in data:
            attrs = item.get("attributes", {})
            vehicle_rel = item.get("relationships", {}).get("vehicle", {}).get("data")

            lat, lon = None, None
            location_desc = "Location unknown"
            current_seq = None
            direction_id = None

            if vehicle_rel:
                veh = included_map.get(("vehicle", vehicle_rel["id"]))
                if veh:
                    v_attrs = veh.get("attributes", {})
                    lat = v_attrs.get("latitude")
                    lon = v_attrs.get("longitude")
                    direction_id = v_attrs.get(
                        "direction_id"
                    )  # <--- NEW: Get the real direction (0 or 1)

                    status = v_attrs.get("current_status", "").replace("_", " ").title()
                    current_seq = v_attrs.get("current_stop_sequence")

                    stop_name = "en route"
                    if stop_map and current_seq in stop_map:
                        stop_name = stop_map[current_seq]

                    location_desc = f"{status} {stop_name}"

            clean_results.append(
                {
                    "time": attrs.get("arrival_time") or attrs.get("departure_time"),
                    "location": location_desc,
                    "current_seq": current_seq,
                    "lat": lat,
                    "lon": lon,
                    "direction_id": direction_id,
                    "id": vehicle_rel["id"] if vehicle_rel else "Unknown",
                }
            )
        return clean_results
