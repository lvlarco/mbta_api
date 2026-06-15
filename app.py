import dash
from dash import html, dcc
import dash_leaflet as dl
from dash.dependencies import Input, Output

from resources.time_distances import HOME_DETAILS
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
malden_icon = dict(iconUrl="/assets/malden.png", iconSize=[60, 60], iconAnchor=[30, 60])
wellington_icon = dict(iconUrl="/assets/wellington.png", iconSize=[60, 60], iconAnchor=[30, 60])

app = dash.Dash(__name__, title="GoTime", meta_tags=[
    {"name": "mobile-web-app-capable", "content": "yes"},
    {"name": "application-name", "content": "GoTime"},
])

app.layout = html.Div([
    dcc.Interval(id="interval-component", interval=15 * 1000, n_intervals=0),

    # LEFT PANEL: DASHBOARD
    html.Div([
        html.Div(id="primary-option-container", children=[
            html.Div("LEAVE IN", style={**TEXT_STYLE, "fontSize": "25px", "color": "#666"}),
            html.Div(id="primary-timer", style={**TEXT_STYLE, "fontSize": "100px", "lineHeight": "1.0"}),
            html.Div(id="primary-desc", style={**TEXT_STYLE, "fontSize": "30px", "marginTop": "10px"}),
        ], style={"padding": "30px", "borderBottom": "4px solid #eee"}),

        html.Div(id="secondary-options-list", style={**TEXT_STYLE, "flex": "1", "overflowY": "auto"}),
    ], className="dashboard-panel"),

    # RIGHT PANEL: MAP
    html.Div([
        dl.Map([
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"),
            dl.LayerGroup(id="route-path-layer"),
            dl.Marker(position=HOME_DETAILS.get("coords"), icon=home_icon),
            dl.Marker(position=[42.426715, -71.074349], icon=malden_icon, zIndexOffset=-1000),
            dl.Marker(position=[42.401907, -71.077096], icon=wellington_icon, zIndexOffset=-1000),

            dl.LayerGroup(id="bus-layer"),
        ],
            id="map",
            style={"width": "100%", "height": "100%"},
            center=HOME_DETAILS.get("map_centering"),
            zoom=14, zoomControl=False, attributionControl=False,
        )
    ], className="map-panel")

], className="main-container")

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

    # Gets top route icon
    top_route_id = top.get("route_id")
    if top_route_id:
        top_icon_url = get_bus_icon(top_route_id)["iconUrl"]
    elif top.get("route_type") == "Walking":
        top_icon_url = "/assets/walk.png"
    else:
        top_icon_url = None  # truly unknown/empty

    # Process top 4 results
    # We use .get() to avoid the KeyError if a field is missing
    for i, opt in enumerate(results[:4]):
        r_id = opt.get("route_id")
        if not r_id:
            continue  # Skip if no route ID exists (like walking)

        # A. Sidebar Card
        route_color = ROUTES_DETAILS.get(r_id, {}).get("color", "#ccc") if r_id else "#ccc"
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
                "borderLeft": f'15px solid {route_color}',
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
                    zIndexOffset=1000,
                )
            )

    return (
        f"{leave_min} MIN",
        {**TEXT_STYLE, "fontSize": "100px", "color": timer_color},
        html.Div([
            html.Img(src=top_icon_url, style={"height": "70px", "marginRight": "15px",
                                              "verticalAlign": "middle"}) if top_icon_url else None,
            html.Span(top.get("desc", "Unknown").upper()),
        ], style={"display": "flex", "alignItems": "center"}),
        secondary_cards,
        bus_markers,
        path_layer,
    )


if __name__ == "__main__":
    local = "127.0.0.1"
    network = "0.0.0.0"
    app.run(debug=False, host=network, port=8050)
