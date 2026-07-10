import pandas as pd
from src.tools.device_capability import infer_capabilities_from_columns


def test_infer_heart_rate_and_power():
    cols = ["timestamp", "heartRate", "power", "cadence"]
    caps = infer_capabilities_from_columns(cols)
    assert "heart_rate" in caps
    assert "power" in caps
    assert "cadence" in caps


def test_infer_gps_and_steps():
    cols = ["latitude", "longitude", "steps", "elevation"]
    caps = infer_capabilities_from_columns(cols)
    assert "gps" in caps
    assert "steps" in caps
    assert "elevation" in caps
