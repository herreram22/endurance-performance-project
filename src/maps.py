import math

import pandas as pd
import pydeck as pdk


MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"


def prepare_run_map_data(runs_df, block_ranges):
    map_df = runs_df.dropna(subset=["startLatitude", "startLongitude"]).copy()
    map_df["date"] = pd.to_datetime(map_df["start_time"]).dt.date
    map_df["year"] = pd.to_datetime(map_df["start_time"]).dt.year.astype(int)
    map_df["distance_label"] = map_df["distance_miles"].map(lambda value: f"{value:.1f} mi")
    map_df["pace_label"] = map_df["avg_pace_mile"].fillna("N/A")
    map_df["location_label"] = map_df["locationName"].fillna("Unknown")
    map_df["run_name"] = map_df["name"].fillna("Run")
    map_df["radius_m"] = map_df["distance_miles"].fillna(0).clip(lower=0.2).pow(0.5) * 120
    map_df["marathon_block"] = "Outside marathon blocks"

    for block_name, date_range in block_ranges.items():
        start_date, end_date = date_range
        in_block = map_df["start_time"].dt.date.between(start_date.date(), end_date.date())
        map_df.loc[in_block, "marathon_block"] = block_name

    has_end = map_df[["endLatitude", "endLongitude"]].notna().all(axis=1)
    moved = (
        (map_df["startLatitude"].round(5) != map_df["endLatitude"].round(5))
        | (map_df["startLongitude"].round(5) != map_df["endLongitude"].round(5))
    )
    map_df["has_route_chord"] = has_end & moved

    return map_df


def get_initial_view_state(map_df):
    center_lat = map_df["startLatitude"].mean()
    center_lon = map_df["startLongitude"].mean()
    lat_span = map_df["startLatitude"].max() - map_df["startLatitude"].min()
    lon_span = map_df["startLongitude"].max() - map_df["startLongitude"].min()
    geo_span = max(lat_span, lon_span)

    if pd.isna(center_lat) or pd.isna(center_lon):
        center_lat, center_lon, zoom = 20, 0, 1.2
    elif geo_span > 25:
        zoom = 2.0
    elif geo_span > 8:
        zoom = 4.0
    elif geo_span > 1:
        zoom = 7.0
    else:
        zoom = 10.0

    return pdk.ViewState(
        latitude=float(center_lat),
        longitude=float(center_lon),
        zoom=zoom,
        pitch=35,
        bearing=0,
    )


def build_run_atlas_deck(map_df, show_route_chords=True, show_end_points=True):
    layers = []

    if show_route_chords:
        route_df = map_df[map_df["has_route_chord"]].copy()
        layers.append(
            pdk.Layer(
                "ArcLayer",
                route_df,
                get_source_position=["startLongitude", "startLatitude"],
                get_target_position=["endLongitude", "endLatitude"],
                get_source_color=[37, 99, 235, 120],
                get_target_color=[22, 163, 74, 130],
                get_width=1.5,
                pickable=False,
                auto_highlight=False,
            )
        )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            map_df,
            get_position=["startLongitude", "startLatitude"],
            get_radius="radius_m",
            radius_min_pixels=3,
            radius_max_pixels=18,
            get_fill_color=[37, 99, 235, 170],
            get_line_color=[255, 255, 255, 210],
            line_width_min_pixels=0.5,
            pickable=True,
            auto_highlight=True,
        )
    )

    if show_end_points:
        end_df = map_df[map_df[["endLatitude", "endLongitude"]].notna().all(axis=1)].copy()
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                end_df,
                get_position=["endLongitude", "endLatitude"],
                get_radius=70,
                radius_min_pixels=2,
                radius_max_pixels=8,
                get_fill_color=[22, 163, 74, 145],
                pickable=False,
            )
        )

    tooltip = {
        "html": (
            "<b>{run_name}</b><br/>"
            "{date}<br/>"
            "{distance_label} | pace {pace_label}<br/>"
            "{location_label}<br/>"
            "{marathon_block}"
        ),
        "style": {
            "backgroundColor": "rgba(255, 255, 255, 0.96)",
            "color": "#111827",
            "fontFamily": "sans-serif",
            "border": "1px solid #e5e7eb",
            "borderRadius": "10px",
            "boxShadow": "0 12px 30px rgba(15, 23, 42, 0.12)",
        },
    }

    return pdk.Deck(
        layers=layers,
        initial_view_state=get_initial_view_state(map_df),
        map_style=MAP_STYLE,
        tooltip=tooltip,
    )


def summarize_map_bounds(map_df):
    if map_df.empty:
        return "No mapped runs"

    lat_span = map_df["startLatitude"].max() - map_df["startLatitude"].min()
    lon_span = map_df["startLongitude"].max() - map_df["startLongitude"].min()
    span = math.sqrt((lat_span**2) + (lon_span**2))
    if span > 20:
        return "Global footprint"
    if span > 2:
        return "Regional footprint"
    return "Local footprint"
