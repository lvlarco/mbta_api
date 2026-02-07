from src.mbta_fetcher import MBTAFetcher


def generate_stop_map(fetcher, route_ids):
    master_map = {}
    for route in route_ids:
        master_map[route] = {0: {}, 1: {}}  # 0: Outbound, 1: Inbound
        for direction in [0, 1]:
            endpoint = f"https://api-v3.mbta.com/stops"
            params = {"filter[route]": route, "filter[direction_id]": direction}

            response = fetcher.session.get(endpoint, params=params)
            stops = response.json().get("data", [])

            # The API doesn't always give a "sequence" number in /stops,
            # but it returns them in order. We map them to their index.
            for index, stop in enumerate(stops):
                stop_name = stop["attributes"]["name"]
                # We add 1 because MBTA sequence numbers usually start at 1
                master_map[route][direction][index + 1] = stop_name
    return master_map


# Usage
routes_to_map = ["106", "99", "97"]
fetcher = MBTAFetcher()
my_stop_lookup = generate_stop_map(fetcher, routes_to_map)
print(my_stop_lookup)
