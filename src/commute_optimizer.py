import time
import os
from mbta_fetcher import MBTAFetcher
from datetime import datetime
from api_keys import MBTA_API_KEY_V3
import iso8601


class CommuteOptimizer:
    WALK_TO_MALDEN_STATION = "INSERT TIME HERE"
    WALK_TO_WELLINGTON_STATION = "INSERT TIME HERE"
    WALK_TO_BUS_STOPS = "INSERT TIME HERE"
    SAFETY_BUFFER = "INSERT TIME HERE"

    BUS_CONFIG = {
        "106": {
            "to_malden": {"id": "5412", "travel_time": "INSERT TIME HERE", "dir": 0},
            "to_well": {"id": "5396", "travel_time": "INSERT TIME HERE", "dir": 1}
        },
        "99": {
            "to_malden": {"id": "5412", "travel_time": "INSERT TIME HERE", "dir": 0},
            "to_well": {"id": "5396", "travel_time": "INSERT TIME HERE", "dir": 1}
        },
        "97": {
            "to_malden": {"id": "5058", "travel_time": "INSERT TIME HERE", "dir": 0},
            "to_well": {"id": "5047", "travel_time": "INSERT TIME HERE", "dir": 1}
        }
    }

    def __init__(self, api_key: str = None):
        self.fetcher = MBTAFetcher(api_key)
        self.master_stop_maps = {}

        for route in ["106", "99", "97"]:
            # Pass the route to the fetcher to get stop names
            self.master_stop_maps[route] = {
                0: self.fetcher.get_route_stop_map(route, 0),
                1: self.fetcher.get_route_stop_map(route, 1)
            }

        self.HOME_SEQUENCES = {
            "106": {"to_malden": 14, "to_well": 12},
            "99": {"to_malden": 10, "to_well": 18},
            "97": {"to_malden": 15, "to_well": 8}
        }

    def _get_minutes_until(self, timestamp_str: str) -> float:
        if not timestamp_str: return 999
        arrival_dt = iso8601.parse_date(timestamp_str)
        now = datetime.now(arrival_dt.tzinfo)
        return (arrival_dt - now).total_seconds() / 60

    def calculate_best_route(self):
        options = []
        ol_malden = self.fetcher.get_orange_line_southbound("Malden Center")
        ol_wellington = self.fetcher.get_orange_line_southbound("Wellington")

        if not ol_malden or not ol_wellington:
            return []

        # 1. EVALUATE: WALK
        for station_name, walk_time, trains in [
            ("Malden Center", self.WALK_TO_MALDEN_STATION, ol_malden),
            ("Wellington", self.WALK_TO_WELLINGTON_STATION, ol_wellington)
        ]:
            for train in trains:
                wait_time = self._get_minutes_until(train['time'])
                if wait_time > (walk_time + self.SAFETY_BUFFER):
                    options.append({
                        "desc": f"Walk to {station_name}",
                        "leave_in": wait_time - walk_time - self.SAFETY_BUFFER,
                        "arrival_on_train": wait_time,
                        "status": "N/A (Walking)",
                        "route_type": "Walking"
                    })
                    break

        # 2. EVALUATE: BUSES
        for route_id, directions in self.BUS_CONFIG.items():
            for target_key, data in directions.items():
                target_name = "Malden Center" if target_key == "to_malden" else "Wellington"

                # Pass the stop_map for the specific route and direction
                current_map = self.master_stop_maps[route_id][data['dir']]
                bus_preds = self.fetcher.get_predictions(route_id, data['id'], data['dir'], stop_map=current_map)

                if not bus_preds: continue

                for bus in bus_preds[:2]:
                    # CALCULATE "STOPS AWAY" STATUS
                    curr_seq = bus.get('current_seq')
                    home_seq = self.HOME_SEQUENCES[route_id][target_key]

                    if curr_seq and home_seq:
                        stops_away = home_seq - curr_seq
                        if stops_away > 0:
                            status_str = f"{stops_away} stops away ({bus['location']})"
                        else:
                            status_str = bus['location']
                    else:
                        status_str = bus['location']

                    bus_wait = self._get_minutes_until(bus['time'])

                    if bus_wait > (self.WALK_TO_BUS_STOPS + self.SAFETY_BUFFER):
                        arrival_at_station = bus_wait + data['travel_time']
                        trains = ol_malden if target_name == "Malden Center" else ol_wellington

                        for train in trains:
                            train_wait = self._get_minutes_until(train['time'])
                            if train_wait > (arrival_at_station + self.SAFETY_BUFFER):
                                options.append({
                                    "desc": f"Bus {route_id} -> {target_name}",
                                    "leave_in": bus_wait - self.WALK_TO_BUS_STOPS - self.SAFETY_BUFFER,
                                    "arrival_on_train": train_wait,
                                    "status": status_str,
                                    "route_type": "Bus"
                                })
                                break
                        break

        options.sort(key=lambda x: x['arrival_on_train'])
        return options


def run_loop():
    # Heads up: Be careful sharing your API key in public places!
    optimizer = CommuteOptimizer(api_key=MBTA_API_KEY_V3)

    while True:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{' MBTA COMMUTE DASHBOARD ':=^55}")
            print(f" Last Update: {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'=' * 55}")

            results = optimizer.calculate_best_route()

            if not results:
                print("\n Searching for viable routes...")
            else:
                for i, opt in enumerate(results[:4]):
                    medal = "🥇" if i == 0 else "  "
                    leave_min = round(opt['leave_in'])

                    # Colors: Red if <= 5 mins, Green otherwise
                    color = "\033[91m" if leave_min <= 5 else "\033[92m"
                    reset = "\033[0m"

                    print(f"\n{medal} {opt['desc']}")
                    print(f"   LEAVE IN: {color}{leave_min} min{reset}")
                    print(f"   STATUS:   {opt['status']}")
                    print(f"   On Orange Line in: {round(opt['arrival_on_train'])} min")

            print(f"\n{'=' * 55}")
            print(" Refreshing in 60 seconds... (Ctrl+C to stop)")
            time.sleep(60)

        except KeyboardInterrupt:
            print("\nTracker stopped. safe travels!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_loop()