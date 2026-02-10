import dash
from dash import html, dcc
import dash_leaflet as dl
from dash.dependencies import Input, Output

from resources.routes_data import ROUTES_DETAILS
from resources.api_keys import MBTA_API_KEY_V3
from src.commute_optimizer import CommuteOptimizer

TEXT_STYLE = {
    "fontFamily": "Arial, sans-serif",
    "fontWeight": "bold",
    "color": "#000000",
    "textAlign": "left",
}

home_icon = dict(iconUrl="/assets/home.png", iconSize=[60, 60], iconAnchor=[30, 60])

# ... imports remain the same ...

app = dash.Dash(__name__)

app.layout = html.Div([
    dcc.Interval(id="interval-component", interval=15 * 1000, n_intervals=0),

    # LEFT PANEL: DASHBOARD
    html.Div([
        html.Div(id="primary-option-container", children=[
            html.Div("LEAVE IN", style={**TEXT_STYLE, "fontSize": "25px", "color": "#666"}),
            html.Div(id="primary-timer", style={**TEXT_STYLE, "fontSize": "130px", "lineHeight": "1.0"}),
            html.Div(id="primary-desc", style={**TEXT_STYLE, "fontSize": "30px", "marginTop": "10px"}),
        ], style={"padding": "30px", "borderBottom": "4px solid #eee"}),

        html.Div(id="secondary-options-list", style={**TEXT_STYLE, "flex": "1", "overflowY": "auto"}),
    ], className="dashboard-panel"),  # <--- CHANGED: Uses CSS class now

    # RIGHT PANEL: MAP
    html.Div([
        dl.Map([
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"),
            dl.LayerGroup(id="route-path-layer"),
            dl.Marker(icon=home_icon),
            dl.LayerGroup(id="bus-layer"),
        ],
            id="map",
            style={"width": "100%", "height": "100%"},  # Let CSS control the size
            zoom=15, zoomControl=False, attributionControl=False,
        )
    ], className="map-panel")  # <--- CHANGED: Uses CSS class now

], className="main-container")  # <--- CHANGED: Uses CSS class now

com_opt = CommuteOptimizer(MBTA_API_KEY_V3)


def get_bus_icon(route_id):
    icon_urls = {
        "106": "/assets/bus-green.png",
        "99": "/assets/bus-yellow.png",
        "97": "/assets/bus-blue.png",
    }
    return dict(
        iconUrl=icon_urls.get(route_id, "/assets/bus-default.png"),
        iconSize=[60, 60],
        iconAnchor=[30, 30],
    )


@app.callback(
    [
        Output("primary-timer", "children"),
        Output("primary-timer", "style"),
        Output("primary-desc", "children"),
        Output("secondary-options-list", "children"),
        Output("bus-layer", "children"),
        Output("route-path-layer", "children"),
    ],
    [Input("interval-component", "n_intervals")],
)
def refresh_ui(n):
    results = com_opt.calculate_best_route()
    if not results:
        return "--", TEXT_STYLE, "LOADING...", [], [], []

    # 1. Primary Logic
    top = results[0]
    leave_min = round(top.get("leave_in", 0))
    timer_color = "#d00000" if leave_min <= 5 else "#27ae60"

    secondary_cards = []
    path_layer = []
    bus_markers = []

    # Track which routes we've already drawn to avoid overlap mess
    drawn_routes = set()

    # Process top 4 results
    # We use .get() to avoid the KeyError if a field is missing
    for i, opt in enumerate(results[:4]):
        r_id = opt.get("route_id")
        if not r_id:
            continue  # Skip if no route ID exists (like walking)

        # A. Sidebar Card
        card = html.Div(
            [
                html.Div(
                    [
                        html.Span(
                            f"{round(opt.get('leave_in', 0))}m ",
                            style={"fontSize": "35px", "fontWeight": "bold"},
                        ),
                        html.Span(
                            f"via {opt.get('desc', 'Unknown')}",
                            style={"fontSize": "18px"},
                        ),
                    ]
                ),
                html.Div(
                    f"Status: {opt.get('status', 'N/A')}",
                    style={"fontSize": "14px", "color": "#666"},
                ),
            ],
            style={
                "padding": "20px",
                "borderLeft": f'15px solid {opt.get("color", "#ccc")}',
                "backgroundColor": "#f9f9f9" if i == 0 else "#fff",
                "borderBottom": "1px solid #ddd",
            },
        )
        secondary_cards.append(card)

        # B. Map Path (Drawing all, but highlighting the top one)
        if r_id in ROUTES_DETAILS and r_id not in drawn_routes:
            is_winner = r_id == top.get("route_id")
            path_layer.append(
                dl.Polyline(
                    positions=ROUTES_DETAILS[r_id]["coords"],
                    color=ROUTES_DETAILS[r_id]["color"],
                    # weight=12 if is_winner else 4,
                    weight=4,
                    # opacity=0.8 if is_winner else 0.2,
                    opacity=0.5,
                )
            )
            drawn_routes.add(r_id)

        # C. Bus Marker
        if opt.get("lat") and opt.get("lon"):
            bus_markers.append(
                dl.Marker(
                    position=[opt["lat"], opt["lon"]],
                    icon=get_bus_icon(r_id),
                    children=[dl.Tooltip(f"Route {r_id}")],
                )
            )

    return (
        f"{leave_min} MIN",
        {**TEXT_STYLE, "fontSize": "130px", "color": timer_color},
        top.get("desc", "Unknown").upper(),
        secondary_cards,
        bus_markers,
        path_layer,
    )


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8050)
