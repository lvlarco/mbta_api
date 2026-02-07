import requests
import json
from datetime import datetime
from typing import List, Dict, Optional


class Train:
    """
    Represents a single train vehicle on the MBTA network.
    """

    def __init__(self, vehicle_data: dict):
        self.id = vehicle_data.get("id")
        attributes = vehicle_data.get("attributes", {})

        # Position Data
        self.latitude = attributes.get("latitude")
        self.longitude = attributes.get("longitude")
        self.bearing = attributes.get("bearing")
        self.speed = attributes.get("speed")

        # Status Data
        self.current_status = attributes.get("current_status")
        self.direction_id = attributes.get("direction_id")
        self.label = attributes.get("label")  # Often the train number
        self.updated_at = attributes.get("updated_at")

        # Route Data
        # relationships/route/data/id usually holds the route ID (e.g., "Red", "Green-B")
        try:
            self.route_id = vehicle_data["relationships"]["route"]["data"]["id"]
        except (KeyError, TypeError):
            self.route_id = "Unknown"

    def get_coordinates(self) -> tuple:
        """Returns (latitude, longitude)."""
        return self.latitude, self.longitude

    def get_direction(self) -> str:
        """
        Maps direction_id to a human-readable string.
        Note: 0 is generally Outbound and 1 is Inbound for subway, 
        but this can vary by specific route definition.
        """
        return "Outbound (0)" if self.direction_id == 0 else "Inbound (1)"

    def __repr__(self):
        return f"<Train {self.label} | Route: {self.route_id} | Status: {self.current_status}>"


class MBTAClient:
    """
    Client to handle connection to the MBTA V3 API.
    """
    BASE_URL = "https://api-v3.mbta.com"

    def __init__(self, api_key: str = None):
        """
        Initialize with an optional API key. 
        (MBTA allows limited requests without a key, but a key is recommended).
        """
        self.api_key = api_key
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"x-api-key": self.api_key})

    def fetch_live_trains(self, lines: List[str] = None) -> List[Train]:
        """
        Fetches live vehicle data.

        :param lines: Optional list of route IDs to filter (e.g., ['Red', 'Orange']).
                      If None, fetches default subway lines.
        :return: A list of Train objects.
        """
        endpoint = f"{self.BASE_URL}/vehicles"

        # Default to all major subway lines if no specific lines requested
        if not lines:
            lines = ["Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E"]

        params = {
            "filter[route]": ",".join(lines),
            "include": "route"  # Include route data to ensure we have IDs
        }

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            return [Train(item) for item in data]

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to MBTA API: {e}")
            return []


class TrainMap:
    """
    Manages the organization and classification of Train objects.
    """

    def __init__(self, trains: List[Train]):
        self.trains = trains
        self.grouped_data = self._group_by_color()

    def _group_by_color(self) -> Dict[str, List[Train]]:
        """
        Internal method to classify trains by Line Color.
        """
        color_map = {
            "Red": [],
            "Orange": [],
            "Blue": [],
            "Green": [],
            "Other": []
        }

        for train in self.trains:
            rid = train.route_id
            if rid == "Red" or rid == "Mattapan":
                color_map["Red"].append(train)
            elif rid == "Orange":
                color_map["Orange"].append(train)
            elif rid == "Blue":
                color_map["Blue"].append(train)
            elif rid.startswith("Green"):
                color_map["Green"].append(train)
            else:
                color_map["Other"].append(train)

        return color_map

    def get_map(self) -> Dict[str, List[Dict]]:
        """
        Returns a dictionary representing the current map of trains.
        Structure: { "Color": [ {Train Info}, ... ] }
        """
        result_map = {}
        for color, train_list in self.grouped_data.items():
            result_map[color] = []
            for train in train_list:
                result_map[color].append({
                    "id": train.id,
                    "label": train.label,
                    "coordinates": train.get_coordinates(),
                    "bearing": train.bearing,
                    "status": train.current_status,
                    "direction": train.get_direction(),
                    "specific_route": train.route_id
                })
        return result_map

    def print_status_board(self):
        """
        Prints a text-based status board of the current map.
        """
        print(f"\n{'=' * 40}")
        print(f"MBTA LIVE TRAIN TRACKER - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 40}")

        for color, trains in self.grouped_data.items():
            if not trains:
                continue
            print(f"\n--- {color.upper()} LINE ({len(trains)} Trains) ---")
            print(f"{'ID':<10} {'Route':<10} {'Status':<20} {'Coords'}")
            for t in trains:
                coords = f"{t.latitude:.4f}, {t.longitude:.4f}"
                print(f"{t.label:<10} {t.route_id:<10} {t.current_status:<20} {coords}")


if __name__ == "__main__":
    client = MBTAClient(api_key=None)
    trains = client.fetch_live_trains()

    train_map = TrainMap(trains)
    train_map.print_status_board()

    data_map = train_map.get_map()
    # print(data_map['Red']) # Example: Access only Red line data