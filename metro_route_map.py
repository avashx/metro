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

SVG_CHAT = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16' fill='%23A0AAB5'><path d='M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z'/></svg>"
SVG_EXPAND = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='18' height='18' fill='%23A0AAB5'><path d='M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z'/></svg>"
SVG_RULER = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16' fill='%23A0AAB5'><path d='M19.9 4.1c-1.56-1.56-4.09-1.56-5.66 0l-10.6 10.6c-1.56 1.56-1.56 4.09 0 5.66 1.56 1.56 4.09 1.56 5.66 0l10.6-10.6c1.56-1.56 1.56-4.09 0-5.66zM7.34 18.24L5.93 16.83l1.41-1.41 1.41 1.41 1.41-1.41-1.41-1.41 1.41-1.41 1.41 1.41 1.41-1.41-1.41-1.41 1.41-1.41 1.41 1.41 2.83-2.83 1.41 1.41-11.31 11.31z'/></svg>"
SVG_STAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16' fill='%23A0AAB5'><path d='M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z'/></svg>"
SVG_LAYERS = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='18' height='18' fill='%23A0AAB5'><path d='M12 2L2 7l10 5 10-5-10-5zM2 12l10 5 10-5M2 17l10 5 10-5'/></svg>"
SVG_GLOBE = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16' fill='%23A0AAB5'><path d='M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.09 13.36 4 12.69 4 12s.09-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.17.64.26 1.31.26 2s-.09 1.36-.26 2h-3.38z'/></svg>"

CTRL_STYLE = {
    "background": "#1A1D20", "borderRadius": "8px", "boxShadow": "0 2px 10px rgba(0,0,0,0.2)",
    "display": "flex", "alignItems": "center", "justifyContent": "center", "padding": "8px", "cursor": "pointer"
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


def generate_square_polygon(lat: float, lon: float, size_deg: float) -> Tuple[list, list]:
    lats = [lat - size_deg, lat + size_deg, lat + size_deg, lat - size_deg, lat - size_deg, None]
    lons = [lon - size_deg, lon - size_deg, lon + size_deg, lon + size_deg, lon - size_deg, None]
    return lats, lons


def generate_triangle_polygon(lat: float, lon: float, size_deg: float) -> Tuple[list, list]:
    lats = [lat - size_deg, lat + size_deg, lat - size_deg, lat - size_deg, None]
    lons = [lon - size_deg, lon, lon + size_deg, lon - size_deg, None]
    return lats, lons


def generate_shapes_from_df(df: pd.DataFrame, shape_type: str, size_deg: float) -> Tuple[list, list]:
    all_lats, all_lons = [], []
    for _, row in df.iterrows():
        if shape_type == "square":
            l, ln = generate_square_polygon(row["lat"], row["lon"], size_deg)
        else:
            l, ln = generate_triangle_polygon(row["lat"], row["lon"], size_deg)
        all_lats.extend(l)
        all_lons.extend(ln)
    return all_lats, all_lons


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


def calculate_growth_multiplier(target_year: int) -> float:
    """Calculate the compound growth multiplier based on MP2041."""
    multiplier = 1.0
    base_year = 2025
    if target_year == base_year:
        return multiplier
    for y in range(base_year + 1, target_year + 1):
        if y <= 2030:
            multiplier *= 1.022
        else:
            multiplier *= 1.028
    return multiplier


def build_growth_chart(opportunities: pd.DataFrame, radius_m: int, current_year: int) -> go.Figure:
    """Build the Plotly line chart for population growth forecasting."""
    visible_base = opportunities[opportunities["nearest_station_distance_m"] <= radius_m]
    base_pop_sum = visible_base["population_potential"].sum()

    years = []
    populations = []
    for y in range(2025, 2041):
        mult = calculate_growth_multiplier(y)
        years.append(y)
        populations.append(int(base_pop_sum * mult))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years,
        y=populations,
        mode="lines+markers",
        line={"color": "#2E7D78", "width": 3},
        marker={"size": 6},
        name="Forecast"
    ))

    current_pop = populations[current_year - 2025]
    fig.add_trace(go.Scatter(
        x=[current_year],
        y=[current_pop],
        mode="markers",
        marker={"size": 12, "color": "#D84315"},
        name="Current Year"
    ))

    fig.update_layout(
        margin={"l": 50, "r": 20, "t": 30, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title={"text": "Catchment Population Growth", "font": {"size": 13, "color": "#203040"}},
        xaxis={"fixedrange": True, "dtick": 3, "gridcolor": "#E0E6F2"},
        yaxis={"fixedrange": True, "gridcolor": "#E0E6F2"},
        showlegend=False,
    )
    return fig


def build_figure(
    proposed_stations: pd.DataFrame,
    existing_stations: pd.DataFrame,
    opportunities: pd.DataFrame,
    radius_m: int,
    growth_multiplier: float,
) -> Tuple[go.Figure, int, int, pd.Series]:
    """Create map for selected catchment radius and return summary metrics."""
    visible = opportunities[opportunities["nearest_station_distance_m"] <= radius_m].copy()
    visible["population_potential"] = (visible["population_potential"] * growth_multiplier).astype(int)

    total_visible_pop = int(visible["population_potential"].sum())
    total_visible_points = int(len(visible))
    by_land_use = visible.groupby("land_use")["population_potential"].sum().sort_values(ascending=False)

    fig = go.Figure()

    # Split proposed_stations into elevated and underground segments
    underground_mask = proposed_stations["is_underground"] == True
    if underground_mask.any():
        first_ug = underground_mask.idxmax()
        last_ug = underground_mask[::-1].idxmax()
        elevated_1 = proposed_stations.iloc[:first_ug+1]
        underground = proposed_stations.iloc[first_ug:last_ug+1]
        elevated_2 = proposed_stations.iloc[last_ug:]
    else:
        elevated_1 = proposed_stations
        underground = pd.DataFrame()
        elevated_2 = pd.DataFrame()

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

    # Elevated segments
    for idx, segment in enumerate([elevated_1, elevated_2]):
        if len(segment) > 1:
            fig.add_trace(
                go.Scattermapbox(
                    lat=segment["lat"],
                    lon=segment["lon"],
                    mode="lines",
                    line={"color": "#2E7D78", "width": 4},
                    hoverinfo="skip",
                    name="Elevated Route",
                    showlegend=(idx == 0),
                )
            )

    # Underground segment (Congested Zone)
    if len(underground) > 1:
        fig.add_trace(
            go.Scattermapbox(
                lat=underground["lat"],
                lon=underground["lon"],
                mode="lines",
                line={"color": "#D84315", "width": 4},
                hoverinfo="skip",
                name="Underground (Congested Zone)",
            )
        )

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
                        [0.0, "#001C46"],
                        [0.125, "#04377A"],
                        [0.25, "#265A98"],
                        [0.375, "#4782BE"],
                        [0.5, "#6AA8D7"],
                        [0.625, "#8BD2DA"],
                        [0.75, "#ABDFBE"],
                        [0.875, "#CFF0A1"],
                        [1.0, "#F2E96B"],
                    ],
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

    tr_lats, tr_lons = generate_shapes_from_df(existing_stations, "triangle", 0.0012)
    fig.add_trace(
        go.Scattermapbox(
            lat=tr_lats, lon=tr_lons, mode="lines", fill="toself",
            fillcolor="#1F2A44", line=dict(color="#1F2A44", width=1),
            hoverinfo="skip", showlegend=False
        )
    )
    fig.add_trace(
        go.Scattermapbox(
            lat=existing_stations["lat"],
            lon=existing_stations["lon"],
            mode="markers",
            marker={"size": 16, "color": "rgba(0,0,0,0)"},
            text=existing_stations["name"],
            hovertemplate="<b>%{text}</b><br>Existing station<extra></extra>",
            name="▲ Existing Stations",
        )
    )

    el_stations = proposed_stations[~proposed_stations["is_underground"]]
    ug_stations = proposed_stations[proposed_stations["is_underground"]]

    if not el_stations.empty:
        sq_lats, sq_lons = generate_shapes_from_df(el_stations, "square", 0.0012)
        fig.add_trace(
            go.Scattermapbox(
                lat=sq_lats, lon=sq_lons, mode="lines", fill="toself",
                fillcolor="#0B3A6E", line=dict(color="#0B3A6E", width=1),
                hoverinfo="skip", showlegend=False
            )
        )
        fig.add_trace(
            go.Scattermapbox(
                lat=el_stations["lat"],
                lon=el_stations["lon"],
                mode="markers+text",
                marker={"size": 16, "color": "rgba(0,0,0,0)"},
                text=el_stations["name"],
                textposition="bottom center",
                textfont={"size": 10, "color": "#263238"},
                hovertemplate="<b>%{text}</b><br>Elevated Station<extra></extra>",
                name="■ Elevated Stations",
            )
        )

    if not ug_stations.empty:
        sq_lats, sq_lons = generate_shapes_from_df(ug_stations, "square", 0.0012)
        fig.add_trace(
            go.Scattermapbox(
                lat=sq_lats, lon=sq_lons, mode="lines", fill="toself",
                fillcolor="#D84315", line=dict(color="#D84315", width=1),
                hoverinfo="skip", showlegend=False
            )
        )
        fig.add_trace(
            go.Scattermapbox(
                lat=ug_stations["lat"],
                lon=ug_stations["lon"],
                mode="markers+text",
                marker={"size": 16, "color": "rgba(0,0,0,0)"},
                text=ug_stations["name"],
                textposition="bottom center",
                textfont={"size": 10, "color": "#D84315"},
                hovertemplate="<b>%{text}</b><br>Underground Station<extra></extra>",
                name="■ Underground Stations",
            )
        )

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


app = dash.Dash(__name__)
server = app.server
app.title = "Phase 5 Route Opportunity Map"

def setup_app() -> None:
    """Run the Dash app setup."""
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
    app.layout = html.Div(
        style={
            "fontFamily": "'Inter', 'Segoe UI', Helvetica, sans-serif",
            "height": "100vh",
            "width": "100vw",
            "margin": "0",
            "padding": "0",
            "position": "relative",
            "overflow": "hidden"
        },
        children=[
            html.Div(
                style={"position": "absolute", "top": 0, "left": 0, "width": "100%", "height": "100%", "zIndex": "1"},
                children=[
                    dcc.Store(id="zoom-store", data=11.2),
                    dcc.Graph(id="route-map", style={"height": "100%"}, config={"displaylogo": False, "scrollZoom": True, "displayModeBar": False}),
                    html.Div(
                        style={"position": "absolute", "top": "80px", "right": "20px", "display": "flex", "flexDirection": "column", "gap": "10px", "zIndex": "1000"},
                        children=[
                            html.Div(style={**CTRL_STYLE, "width": "36px", "height": "36px", "boxSizing": "border-box"}, children=[html.Img(src=SVG_CHAT)]),
                            html.Div(
                                style={**CTRL_STYLE, "width": "36px", "flexDirection": "column", "padding": "10px 0", "boxSizing": "border-box"},
                                children=[
                                    html.Img(src=SVG_EXPAND),
                                ]
                            )
                        ]
                    ),
                    html.Div(
                        style={"position": "absolute", "bottom": "30px", "right": "20px", "display": "flex", "alignItems": "flex-end", "gap": "12px", "zIndex": "1000"},
                        children=[
                            html.Div(
                                style={**CTRL_STYLE, "height": "36px", "padding": "0 16px", "gap": "20px", "boxSizing": "border-box"},
                                children=[
                                    html.Img(src=SVG_LAYERS),
                                    html.Img(src=SVG_GLOBE)
                                ]
                            ),
                            html.Div(
                                style={**CTRL_STYLE, "width": "36px", "flexDirection": "column", "padding": "10px 0", "gap": "14px", "boxSizing": "border-box"},
                                children=[
                                    html.Span("+", id="zoom-in-btn", n_clicks=0, style={"color": "#A0AAB5", "fontSize": "22px", "lineHeight": "1", "fontFamily": "monospace", "cursor": "pointer", "userSelect": "none"}),
                                    html.Span("−", id="zoom-out-btn", n_clicks=0, style={"color": "#A0AAB5", "fontSize": "26px", "lineHeight": "1", "fontFamily": "monospace", "cursor": "pointer", "userSelect": "none"})
                                ]
                            ),
                            html.Div(
                                id="reset-view-btn", n_clicks=0,
                                style={**CTRL_STYLE, "width": "36px", "height": "36px", "boxSizing": "border-box"},
                                children=[html.Span("⟲", style={"color": "#A0AAB5", "fontSize": "20px", "lineHeight": "1"})]
                            ),
                        ]
                    )
                ]
            ),
            html.Div(
                style={
                    "position": "absolute",
                    "top": "20px",
                    "left": "20px",
                    "width": "340px",
                    "background": "rgba(255, 255, 255, 0.98)",
                    "borderRadius": "12px",
                    "boxShadow": "0 4px 16px rgba(0,0,0,0.1)",
                    "padding": "0",
                    "zIndex": "1000",
                    "maxHeight": "calc(100vh - 40px)",
                    "overflowY": "auto",
                    "display": "flex",
                    "flexDirection": "column"
                },
                children=[
                    html.Div(
                        style={"padding": "20px 20px 10px 20px", "borderBottom": "1px solid #EAEAEA"},
                        children=[
                            html.Div(
                                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "16px"},
                                children=[
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center"},
                                        children=[
                                            html.H3("DMRC Population based Metro demand analysis", style={"margin": "0", "color": "#203040", "fontSize": "14px", "fontWeight": "600"})
                                        ]
                                    ),
                                    html.Span("✕", style={"color": "#A0AAB5", "cursor": "pointer", "fontSize": "14px", "marginLeft": "8px"})
                                ]
                            )
                        ]
                    ),
                    html.Div(
                        style={"padding": "20px"},
                        children=[
                            html.Details(
                                style={"marginBottom": "20px", "borderBottom": "1px solid #EAEAEA", "paddingBottom": "12px"},
                                children=[
                                    html.Summary(
                                        style={"cursor": "pointer", "fontSize": "14px", "fontWeight": "600", "color": "#203040", "listStyle": "none", "display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                                        children=[
                                            "Reference Dataset",
                                            html.Span("▼", style={"color": "#A0AAB5", "fontSize": "10px"})
                                        ]
                                    ),
                                    html.Div(
                                        style={"marginTop": "16px", "display": "flex", "flexDirection": "column", "gap": "14px"},
                                        children=[
                                            html.Div(
                                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                                                children=[
                                                    html.Span("Landuse", style={"fontSize": "12px", "color": "#708090", "fontWeight": "500", "flex": "1"}),
                                                    html.Div(
                                                        style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": "2", "justifyContent": "flex-end"},
                                                        children=[
                                                            html.A("OSM LULC", href="#", style={"background": "#E8F0FE", "color": "#1A73E8", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                            html.A("Master Plan 2041", href="#", style={"background": "#E8F0FE", "color": "#1A73E8", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                        ]
                                                    )
                                                ]
                                            ),
                                            html.Div(
                                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                                                children=[
                                                    html.Span("Population Forecast", style={"fontSize": "12px", "color": "#708090", "fontWeight": "500", "flex": "1"}),
                                                    html.Div(
                                                        style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": "2", "justifyContent": "flex-end"},
                                                        children=[
                                                            html.A("Census 2011/21", href="#", style={"background": "#E8F0FE", "color": "#1A73E8", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                            html.A("2.2% - 2.8% CAGR", href="#", style={"background": "#FCE8E6", "color": "#D93025", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                        ]
                                                    )
                                                ]
                                            ),
                                            html.Div(
                                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                                                children=[
                                                    html.Span("Metro Stations", style={"fontSize": "12px", "color": "#708090", "fontWeight": "500", "flex": "1"}),
                                                    html.Div(
                                                        style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": "2", "justifyContent": "flex-end"},
                                                        children=[
                                                            html.A("DMRC DPR Phase 5", href="#", style={"background": "#E8F0FE", "color": "#1A73E8", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                        ]
                                                    )
                                                ]
                                            ),
                                            html.Div(
                                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                                                children=[
                                                    html.Span("Metro Line Base", style={"fontSize": "12px", "color": "#708090", "fontWeight": "500", "flex": "1"}),
                                                    html.Div(
                                                        style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": "2", "justifyContent": "flex-end"},
                                                        children=[
                                                            html.A("Historical Ridership", href="#", style={"background": "#E8F0FE", "color": "#1A73E8", "padding": "4px 8px", "borderRadius": "12px", "textDecoration": "none", "fontSize": "10px", "whiteSpace": "nowrap"}),
                                                        ]
                                                    )
                                                ]
                                            ),
                                        ]
                                    )
                                ]
                            ),
                            html.Div(
                                style={"marginBottom": "20px"},
                                children=[
                                    html.Div("Descriptive", style={"fontSize": "11px", "color": "#708090", "fontWeight": "600", "marginBottom": "12px"}),
                                    html.Div("Catchment Radius", style={"fontSize": "13px", "color": "#203040", "marginBottom": "6px", "fontWeight": "500"}),
                                    dcc.Slider(
                                        id="radius-slider", min=200, max=2500, step=100, value=900,
                                        marks=None, tooltip={"always_visible": False, "placement": "bottom"}
                                    ),
                                    html.Div(id="radius-text", style={"fontSize": "11px", "color": "#A0AAB5", "textAlign": "right", "marginTop": "4px"}),
                                    
                                    html.Div("Forecast Year", style={"fontSize": "13px", "color": "#203040", "marginBottom": "6px", "fontWeight": "500", "marginTop": "12px"}),
                                    dcc.Slider(
                                        id="year-slider", min=2025, max=2040, step=1, value=2025,
                                        marks=None, tooltip={"always_visible": False, "placement": "bottom"}
                                    ),
                                    html.Div(id="year-text", style={"fontSize": "11px", "color": "#A0AAB5", "textAlign": "right", "marginTop": "4px"}),
                                ]
                            ),
                            html.Div(
                                style={"marginBottom": "20px"},
                                children=[
                                    html.Div("Impact", style={"fontSize": "11px", "color": "#708090", "fontWeight": "600", "marginBottom": "12px"}),
                                    html.Div([
                                        html.Span("Nearby population", style={"fontSize": "13px", "color": "#203040"}),
                                        html.Span(id="population-kpi", style={"float": "right", "fontSize": "13px", "fontWeight": "600"})
                                    ], style={"marginBottom": "8px"}),
                                    html.Div([
                                        html.Span("Visible opportunities", style={"fontSize": "13px", "color": "#203040"}),
                                        html.Span(id="opportunity-kpi", style={"float": "right", "fontSize": "13px", "fontWeight": "600"})
                                    ], style={"display": "none"}),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Div([

                                        html.Div(
                                            style={"display": "flex", "width": "100%", "height": "8px", "borderRadius": "4px", "overflow": "hidden", "marginBottom": "8px"},
                                            children=[
                                                html.Div(style={"flex": "1", "background": "#001C46"}),
                                                html.Div(style={"flex": "1", "background": "#04377A", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#265A98", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#4782BE", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#6AA8D7", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#8BD2DA", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#ABDFBE", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#CFF0A1", "borderLeft": "1px solid white"}),
                                                html.Div(style={"flex": "1", "background": "#F2E96B", "borderLeft": "1px solid white"}),
                                            ]
                                        ),
                                        html.Div(
                                            style={"display": "flex", "justifyContent": "space-between", "fontSize": "10px", "color": "#708090", "fontWeight": "500"},
                                            children=[
                                                html.Span("0 Pop"),
                                                html.Span("Max Pop")
                                            ]
                                        )
                                    ])
                                ]
                            ),
                            html.Div(
                                dcc.Graph(id="growth-chart", config={"displaylogo": False, "displayModeBar": False}, style={"height": "160px"}),
                                style={"marginTop": "20px", "width": "100%"},
                            ),
                            html.Div(id="landuse-breakdown", style={"display": "none"})
                        ]
                    )
                ]
            )
        ]
    )

    @app.callback(
        Output("zoom-store", "data"),
        Input("zoom-in-btn", "n_clicks"),
        Input("zoom-out-btn", "n_clicks"),
        Input("reset-view-btn", "n_clicks"),
        dash.dependencies.State("zoom-store", "data"),
        prevent_initial_call=True,
    )
    def update_zoom(zoom_in_clicks, zoom_out_clicks, reset_clicks, current_zoom):
        ctx = dash.callback_context
        if not ctx.triggered:
            return current_zoom
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "zoom-in-btn":
            return min(current_zoom + 0.5, 18)
        elif trigger == "zoom-out-btn":
            return max(current_zoom - 0.5, 3)
        elif trigger == "reset-view-btn":
            return 11.2
        return current_zoom

    @app.callback(
        Output("route-map", "figure"),
        Output("growth-chart", "figure"),
        Output("radius-text", "children"),
        Output("year-text", "children"),
        Output("population-kpi", "children"),
        Output("opportunity-kpi", "children"),
        Output("landuse-breakdown", "children"),
        Input("radius-slider", "value"),
        Input("year-slider", "value"),
        Input("zoom-store", "data"),
    )
    def update_map(radius_m: int, target_year: int, zoom_level: float):
        growth_multiplier = calculate_growth_multiplier(target_year)
        fig, pop_total, point_total, by_land_use = build_figure(
            proposed_stations=proposed_stations,
            existing_stations=existing_stations,
            opportunities=opportunities,
            radius_m=radius_m,
            growth_multiplier=growth_multiplier,
        )

        # Apply zoom from store
        if zoom_level is not None:
            fig.update_layout(mapbox_zoom=zoom_level)

        chart_fig = build_growth_chart(opportunities, radius_m, target_year)

        land_use_lines = []
        for use_name, value in by_land_use.items():
            color = LAND_USE_PALETTE.get(use_name, "#607D8B")
            line = html.Div(
                [
                    html.Span("■", style={"color": color, "marginRight": "8px"}),
                    html.Span(f"{use_name}: {int(value):,}"),
                ],
                style={"marginBottom": "4px", "flex": "1 1 45%"},
            )
            land_use_lines.append(line)

        if not land_use_lines:
            land_use_lines = [html.Div("No opportunities in the selected radius", style={"color": "#8A9BA8"})]

        radius_text = f"Current reach: {radius_m:,} m"
        year_text = f"Forecast Year: {target_year}"

        return (
            fig,
            chart_fig,
            radius_text,
            year_text,
            f"{pop_total:,}",
            f"{point_total:,}",
            land_use_lines,
        )

setup_app()

if __name__ == "__main__":
    try:
        app.run(debug=False, use_reloader=False, host='127.0.0.1', port=8050, threaded=True)
    except (OSError, PermissionError) as e:
        # Suppress permission errors that can occur in sandboxed environments
        if "Operation not permitted" not in str(e):
            raise
        print(f"\nApp is running at http://127.0.0.1:8050/")
