import time
import os
import iso8601

from typing import List, Dict
from src.mbta_fetcher import MBTAFetcher
from datetime import datetime
from resources.api_keys import MBTA_API_KEY_V3
from resources import time_distances as td
from resources.routes_data import STOP_MAP


class CommuteOptimizer:
    WALK_TO_MALDEN_STATION = td.MALDEN_STATION_WALK
    WALK_TO_WELLINGTON_STATION = td.WELLINGTON_STATION_WALK
    WALK_TO_BUS_STOPS = td.TIME_TO_BUS_STOP
    SAFETY_BUFFER = td.BUFFER_TIME

    BUS_CONFIG = td.BUS_CONFIG

    def __init__(self, api_key: str = None):
        self.fetcher = MBTAFetcher(api_key)
        self.master_stop_maps = STOP_MAP
        self.HOME_SEQUENCES = td.HOME_SEQUENCES

    @staticmethod
    def _get_minutes_until(timestamp_str: str) -> float:
        """
        Calculates the minutes differential between the timestamp
        and now
        :param timestamp_str: timestamp to compare against now
        :return: delta time in minutes
        """
        if not timestamp_str:
            return 999
        arrival_dt = iso8601.parse_date(timestamp_str)
        now = datetime.now(arrival_dt.tzinfo)
        return (arrival_dt - now).total_seconds() / 60

    def calculate_best_route(self) -> List[Dict]:
        """
        Evaluates the best routes taking into consideration the shortest
        travel time to the T station. Considers walking and list of bus routes
        :return: list of the shortest routes
        """
        options = []
        ol_malden = self.fetcher.get_orange_line_southbound("Malden Center")
        ol_wellington = self.fetcher.get_orange_line_southbound("Wellington")

        if (not ol_malden) and (not ol_wellington):
            print("no trains")
            return []

        # 1. EVALUATE: WALK
        for station_name, walk_time, trains in [
            ("Malden Center", self.WALK_TO_MALDEN_STATION, ol_malden),
            ("Wellington", self.WALK_TO_WELLINGTON_STATION, ol_wellington),
        ]:
            if not trains:
                continue
            for train in trains:
                wait_time = self._get_minutes_until(train["time"])
                if wait_time > (walk_time + self.SAFETY_BUFFER):
                    options.append(
                        {
                            "desc": f"Walk to {station_name}",
                            "leave_in": wait_time - walk_time - self.SAFETY_BUFFER,
                            "arrival_on_train": wait_time,
                            "status": "N/A (Walking)",
                            "route_type": "Walking",
                        }
                    )
                    break

        # 2. EVALUATE: BUSES
        for route_id, directions in self.BUS_CONFIG.items():
            for target_key, data in directions.items():
                target_name = (
                    "Malden Center" if target_key == "to_malden" else "Wellington"
                )
                current_map = self.master_stop_maps[route_id][data["dir"]]
                bus_preds = self.fetcher.get_predictions(
                    route_id, data["id"], data["dir"], stop_map=current_map
                )

                if not bus_preds:
                    continue

                for bus in bus_preds:
                    curr_seq = bus.get("current_seq")
                    home_seq = self.HOME_SEQUENCES[route_id][target_key]
                    vehicle_direction = bus.get("direction_id")
                    expected_direction = data["dir"]

                    if curr_seq and home_seq:
                        if vehicle_direction == expected_direction:
                            stops_away = home_seq - curr_seq
                        else:
                            current_map = self.master_stop_maps[route_id][vehicle_direction]
                            stops_to_terminal = len(current_map) - curr_seq
                            stops_away = stops_to_terminal + home_seq
                        if stops_away > 0:
                            status_str = f"{stops_away} stops away ({bus['location']})"
                        else:
                            status_str = bus["location"]
                    else:
                        status_str = bus["location"]

                    bus_wait = self._get_minutes_until(bus["time"])

                    if bus_wait > (self.WALK_TO_BUS_STOPS + self.SAFETY_BUFFER):
                        arrival_at_station = bus_wait + data["travel_time"]
                        trains = (
                            ol_malden
                            if target_name == "Malden Center"
                            else ol_wellington
                        )

                        best_train_wait = None
                        if trains:
                            for train in trains:
                                train_wait = self._get_minutes_until(train["time"])
                                if train_wait > (
                                    arrival_at_station + self.SAFETY_BUFFER
                                ):
                                    best_train_wait = train_wait
                                    break

                        if best_train_wait is None:
                            best_train_wait = arrival_at_station + 1
                            status_str += " (Est. Connection)"

                        options.append(
                            {
                                "desc": f"Bus {route_id} -> {target_name}",
                                "leave_in": bus_wait
                                - self.WALK_TO_BUS_STOPS
                                - self.SAFETY_BUFFER,
                                "arrival_on_train": best_train_wait,
                                "status": status_str,
                                "route_type": "Bus",
                                "lat": bus.get("lat"),
                                "lon": bus.get("lon"),
                                "vehicle_id": bus.get("id"),
                                "route_id": route_id,
                                "bus_data": bus,
                                "direction_id": bus.get("direction_id"),
                            }
                        )
                        break

        options.sort(key=lambda x: x["arrival_on_train"])
        return options


def run_loop() -> None:
    """
    Loop to run the commute optimizer indefinitely. Will update and display
    best routes every 60 seconds.
    """
    optimizer = CommuteOptimizer(api_key=MBTA_API_KEY_V3)

    while True:
        try:
            os.system("cls" if os.name == "nt" else "clear")
            print(f"{' MBTA COMMUTE DASHBOARD ':=^55}")
            print(f" Last Update: {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'=' * 55}")

            results = optimizer.calculate_best_route()

            if not results:
                print("\n Searching for viable routes...")
            else:
                for i, opt in enumerate(results[:4]):
                    medal = "🥇" if i == 0 else "  "
                    leave_min = round(opt["leave_in"])

                    # Colors: Red if <= 5 mins, Green otherwise
                    color = "\033[91m" if leave_min <= 5 else "\033[92m"
                    reset = "\033[0m"

                    print(f"\n{medal} {opt['desc']}")
                    print(f"   LEAVE IN: {color}{leave_min} min{reset}")
                    print(f"   STATUS:   {opt['status']}")
                    print(f"   On Orange Line in: {round(opt['arrival_on_train'])} min")

            time.sleep(60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_loop()
