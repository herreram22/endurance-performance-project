import pandas as pd


def format_minutes(minutes):
    if pd.isna(minutes):
        return "N/A"

    total_seconds = int(round(minutes * 60))
    hours = total_seconds // 3600
    minutes_part = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes_part:02d}:{seconds:02d}"
    return f"{minutes_part}:{seconds:02d}"


def format_date(date_value):
    if pd.isna(date_value):
        return "N/A"
    return pd.to_datetime(date_value).strftime("%b %d, %Y")
