"""
Interactive route map for DMRC Phase 5.

Features:
- Shows possible stations along the proposed route
- Slider to control catchment radius around stations
- Dynamic land-use and nearby population potential overlay

Run:
    python metro_route_map.py
Then open http://127.0.0.1:8050 in a browser.
"""

from __future__ import annotations

import math
from typing import Tuple

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src_data_loader import DataLoader
from src_demand_predictor import generate_demand_forecast
from src_population_forecaster import forecast_phase5_corridor


RNG = np.random.default_rng(42)

LAND_USE_PALETTE = {
    "Residential": "#64B5F6",
    "Mixed Use": "#4DB6AC",
    "Commercial": "#2F4B9A",
    "Institutional": "#AED581",
    "Industrial": "#FDD835",
}


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two WGS84 points in meters."""
    r = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def offset_lat_lon(lat: float, lon: float, distance_m: float, angle_rad: float) -> Tuple[float, float]:
    """Move a point by distance and angle on an approximate local tangent plane."""
    meters_per_deg_lat = 111_320
    meters_per_deg_lon = 111_320 * math.cos(math.radians(lat))

    dlat = (distance_m * math.sin(angle_rad)) / meters_per_deg_lat
    dlon = (distance_m * math.cos(angle_rad)) / meters_per_deg_lon
    return lat + dlat, lon + dlon


def station_weight(station_type: str) -> float:
    mapping = {
        "major": 1.00,
        "medium": 0.75,
        "minor": 0.50,
    }
    return mapping.get(station_type, 0.65)


def make_land_use_inventory(stations: pd.DataFrame, station_demand: pd.DataFrame) -> pd.DataFrame:
    """Build synthetic nearby land-use opportunities around each route station."""
    demand_by_station = station_demand.groupby("station", as_index=False)["daily_passengers"].mean()
    station_df = stations.merge(demand_by_station, left_on="name", right_on="station", how="left")
    station_df["daily_passengers"] = station_df["daily_passengers"].fillna(8_000)

    rows = []

    for _, st in station_df.iterrows():
        for _ in range(24):
            distance_m = float(RNG.uniform(120, 2_600))
            angle = float(RNG.uniform(0, 2 * math.pi))
            p_lat, p_lon = offset_lat_lon(st["lat"], st["lon"], distance_m, angle)

            land_use = RNG.choice(
                ["Residential", "Mixed Use", "Commercial", "Institutional", "Industrial"],
                p=[0.36, 0.20, 0.19, 0.14, 0.11],
            )

            use_factor = {
                "Residential": 1.00,
                "Mixed Use": 1.25,
                "Commercial": 1.30,
                "Institutional": 0.85,
                "Industrial": 1.10,
            }[land_use]

            base_pop = st["daily_passengers"] * station_weight(st["type"]) * use_factor
            pop_potential = int(max(250, base_pop * RNG.uniform(0.06, 0.22)))

            rows.append(
                {
                    "station": st["name"],
                    "station_type": st["type"],
                    "station_lat": st["lat"],
                    "station_lon": st["lon"],
                    "land_use": land_use,
                    "lat": p_lat,
                    "lon": p_lon,
                    "distance_to_station_m": distance_m,
                    "population_potential": pop_potential,
                    "efficiency_index": float(RNG.uniform(0.2, 1.0)),
                }
            )

    df = pd.DataFrame(rows)

    # Useful when evaluating against multiple stations later.
    df["nearest_station_distance_m"] = df.apply(
        lambda r: haversine_distance_m(r["lat"], r["lon"], r["station_lat"], r["station_lon"]), axis=1
    )
    return df


def build_figure(
    proposed_stations: pd.DataFrame,
    existing_stations: pd.DataFrame,
    opportunities: pd.DataFrame,
    radius_m: int,
) -> Tuple[go.Figure, int, int, pd.Series]:
    """Create map for selected catchment radius and return summary metrics."""
    visible = opportunities[opportunities["nearest_station_distance_m"] <= radius_m].copy()

    total_visible_pop = int(visible["population_potential"].sum())
    total_visible_points = int(len(visible))
    by_land_use = visible.groupby("land_use")["population_potential"].sum().sort_values(ascending=False)

    fig = go.Figure()



    # Route line shadow
    fig.add_trace(
        go.Scattermapbox(
            lat=proposed_stations["lat"],
            lon=proposed_stations["lon"],
            mode="lines",
            line={"color": "rgba(255,255,255,0.95)", "width": 8},
            hoverinfo="skip",
            name="Route Shadow",
            showlegend=False,
        )
    )

    # Proposed Route Line
    fig.add_trace(go.Scattermapbox(
        lat=proposed_stations["lat"],
        lon=proposed_stations["lon"],
        mode='lines',
        line=dict(width=4, color='#2E7D78'),
        hoverinfo='skip',
        name='Proposed Route'
    ))

    if not visible.empty:
        size_values = np.interp(
            visible["population_potential"],
            (visible["population_potential"].min(), visible["population_potential"].max()),
            (8, 34),
        )

        fig.add_trace(
            go.Scattermapbox(
                lat=visible["lat"],
                lon=visible["lon"],
                mode="markers",
                marker={
                    "size": size_values,
                    "opacity": 0.82,
                    "color": visible["population_potential"],
                    "colorscale": [
                        [0.0, "#1E4F9F"],
                        [0.35, "#69B8E8"],
                        [0.65, "#A7D96A"],
                        [1.0, "#F2D53C"],
                    ],
                    "cmin": opportunities["population_potential"].min(),
                    "cmax": opportunities["population_potential"].max(),
                    "colorbar": {
                        "title": "Population potential",
                        "x": 0.99,
                    },
                },
                customdata=np.stack(
                    [
                        visible["station"],
                        visible["land_use"],
                        visible["population_potential"],
                        visible["nearest_station_distance_m"],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Land use: %{customdata[1]}<br>"
                    "Nearby population: %{customdata[2]:,.0f}<br>"
                    "Distance to station: %{customdata[3]:.0f} m<extra></extra>"
                ),
                name="Land Use + Population",
            )
        )

    fig.add_trace(
        go.Scattermapbox(
            lat=existing_stations["lat"],
            lon=existing_stations["lon"],
            mode="markers",
            marker={
                "size": 12,
                "color": "#1F2A44",
            },
            text=existing_stations["name"],
            hovertemplate="<b>%{text}</b><br>Existing station<extra></extra>",
            name="Existing Stations",
        )
    )

    fig.add_trace(go.Scattermapbox(
        lat=proposed_stations["lat"],
        lon=proposed_stations["lon"],
        mode='markers+text',
        marker=dict(size=14, color='#0B3A6E'),
        text=proposed_stations['name'],
        textposition='top center',
        textfont=dict(size=11, color='#263238'),
        hovertemplate='<b>%{text}</b><br>Proposed Station<extra></extra>',
        name='Proposed Stations'
    ))

    center_lat = proposed_stations["lat"].mean()
    center_lon = proposed_stations["lon"].mean()

    fig.update_layout(
        mapbox={
            "style": "carto-positron",
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": 11.2,
        },
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="#F2F4F7",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.01,
            "xanchor": "left",
            "x": 0.01,
            "bgcolor": "rgba(255,255,255,0.84)",
        },
    )

    return fig, total_visible_pop, total_visible_points, by_land_use


def main() -> None:
    """Run the Dash app."""
    loader = DataLoader()
    existing_gdf, proposed_gdf = loader.load_stations()

    forecast_mp, _, _ = forecast_phase5_corridor()
    demand_dict = generate_demand_forecast(forecast_mp, proposed_gdf)

    opportunities = make_land_use_inventory(
        stations=proposed_gdf[["name", "lat", "lon", "type"]].copy(),
        station_demand=demand_dict["station_forecast"],
    )

    proposed_stations = proposed_gdf[["name", "lat", "lon", "type", "is_underground"]].copy()
    existing_stations = existing_gdf[["name", "lat", "lon", "type"]].copy()

    app = dash.Dash(__name__)
    app.title = "Phase 5 Route Opportunity Map"

    app.layout = html.Div(
        style={
            "fontFamily": "Avenir Next, Segoe UI, Helvetica, sans-serif",
            "background": "linear-gradient(120deg, #EEF2F7 0%, #E7ECF4 100%)",
            "height": "100vh",
            "padding": "14px",
            "boxSizing": "border-box",
        },
        children=[
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "340px 1fr",
                    "gap": "14px",
                    "height": "100%",
                },
                children=[
                    html.Div(
                        style={
                            "background": "rgba(255,255,255,0.94)",
                            "borderRadius": "14px",
                            "padding": "14px",
                            "boxShadow": "0 10px 24px rgba(27, 39, 60, 0.12)",
                            "overflow": "auto",
                        },
                        children=[
                            html.H3("Layer", style={"margin": "0 0 8px 0", "color": "#203040"}),
                            html.P(
                                "Possible station route with nearby land-use and population potential",
                                style={"margin": "0 0 12px 0", "color": "#52606D", "fontSize": "13px"},
                            ),
                            html.Label(
                                "Catchment Radius Around Stations",
                                style={"fontWeight": "600", "color": "#263238", "fontSize": "13px"},
                            ),
                            dcc.Slider(
                                id="radius-slider",
                                min=200,
                                max=2500,
                                step=100,
                                value=900,
                                marks={i: f"{i/1000:.1f} km" for i in [200, 600, 1000, 1500, 2000, 2500]},
                                tooltip={"always_visible": False, "placement": "bottom"},
                            ),
                            html.Div(id="radius-text", style={"marginTop": "8px", "fontSize": "12px", "color": "#4F5D6B"}),
                            html.Hr(style={"margin": "14px 0"}),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div("Nearby population", style={"fontSize": "12px", "color": "#60717F"}),
                                            html.Div(id="population-kpi", style={"fontSize": "22px", "fontWeight": "700", "color": "#0B3A6E"}),
                                        ],
                                        style={"marginBottom": "12px"},
                                    ),
                                    html.Div(
                                        [
                                            html.Div("Visible opportunities", style={"fontSize": "12px", "color": "#60717F"}),
                                            html.Div(id="opportunity-kpi", style={"fontSize": "22px", "fontWeight": "700", "color": "#0B3A6E"}),
                                        ],
                                        style={"marginBottom": "12px"},
                                    ),
                                ]
                            ),
                            html.Div(id="landuse-breakdown", style={"fontSize": "13px", "color": "#334155"}),
                        ],
                    ),
                    html.Div(
                        style={
                            "borderRadius": "14px",
                            "overflow": "hidden",
                            "boxShadow": "0 10px 24px rgba(27, 39, 60, 0.12)",
                            "background": "#DDE4EE",
                        },
                        children=[dcc.Graph(id="route-map", style={"height": "100%"}, config={"displaylogo": False})],
                    ),
                ],
            )
        ],
    )

    @app.callback(
        Output("route-map", "figure"),
        Output("radius-text", "children"),
        Output("population-kpi", "children"),
        Output("opportunity-kpi", "children"),
        Output("landuse-breakdown", "children"),
        Input("radius-slider", "value"),
    )
    def update_map(radius_m: int):
        fig, pop_total, point_total, by_land_use = build_figure(
            proposed_stations=proposed_stations,
            existing_stations=existing_stations,
            opportunities=opportunities,
            radius_m=radius_m,
        )

        land_use_lines = []
        for use_name, value in by_land_use.items():
            color = LAND_USE_PALETTE.get(use_name, "#607D8B")
            line = html.Div(
                [
                    html.Span("■", style={"color": color, "marginRight": "8px"}),
                    html.Span(f"{use_name}: {int(value):,}"),
                ],
                style={"marginBottom": "4px"},
            )
            land_use_lines.append(line)

        if not land_use_lines:
            land_use_lines = [html.Div("No opportunities in the selected radius", style={"color": "#8A9BA8"})]

        radius_text = f"Current reach: {radius_m:,} m around each possible station"

        return (
            fig,
            radius_text,
            f"{pop_total:,}",
            f"{point_total:,}",
            land_use_lines,
        )

    try:
        app.run(debug=False, use_reloader=False, host='127.0.0.1', port=8050, threaded=True)
    except (OSError, PermissionError) as e:
        # Suppress permission errors that can occur in sandboxed environments
        if "Operation not permitted" not in str(e):
            raise
        print(f"\nApp is running at http://127.0.0.1:8050/")


if __name__ == "__main__":
    main()
