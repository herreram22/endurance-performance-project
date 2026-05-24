# Health Performance Project

A longitudinal running and performance analytics project built using Garmin telemetry and physiological data.

The goal of this project is to investigate training progression, wearable-derived fitness metrics, race prediction systems, and performance trends over time using real-world endurance training data.

---

## Overview

This repository currently contains notebooks for:

- Parsing Garmin activity and metrics exports
- Building cleaned and structured datasets
- Creating an integrated daily master table
- Evaluating Garmin race prediction behavior
- Exploring relationships between training load, readiness, recovery, and performance

The project combines:
- data engineering
- exploratory analysis
- performance science
- wearable analytics
- longitudinal athlete monitoring

---

## Goals

Current project goals include:

- Building a unified daily training and performance dataset
- Investigating how Garmin race predictions evolve over time
- Comparing predicted race performances against official race results
- Exploring relationships between:
  - training load
  - recovery
  - readiness
  - VO2 max estimates
  - race performance
- Evaluating the reliability and limitations of wearable-derived physiological models

Long-term goals may include:
- interactive dashboards
- geospatial run visualizations
- predictive modeling
- ML-based performance estimation
- automated training analysis systems

---

## Project Structure

```text
.
├── notebooks/
│   ├── 01_parse_activities.ipynb
│   ├── 02_parse_metrics.ipynb
│   ├── 03_parse_race_predictor.ipynb
│   ├── 04_parse_training_readiness.ipynb
│   ├── 05_parse_max_met.ipynb
│   ├── 06_parse_training_history.ipynb
│   ├── 07_daily_master_table.ipynb
│   └── 08_prediction_analysis.ipynb
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Data Sources

All source data currently comes from Garmin Connect export files.

### Activities
Contains individual running activities and workout-level metrics such as:
- distance
- duration
- pace
- cadence
- heart rate
- power
- elevation
- training load

### Metrics
Contains Garmin physiological and training metrics including:
- acute training load
- chronic training load
- ACWR
- load tunnel metrics

### Race Predictor
Contains Garmin race time predictions for:
- 5K
- 10K
- Half Marathon
- Marathon

### Training Readiness
Contains Garmin readiness snapshots and recovery-related metrics such as:
- readiness score
- HRV
- recovery time
- sleep score
- stress history

### Max MET
Contains VO2 max-related physiological estimates and Garmin fitness metrics.

### Training History
Contains training status and fitness trend information over time.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

Suggested notebook workflow:

1. `notebooks/01_parse_activities.ipynb`
2. `notebooks/02_parse_metrics.ipynb`
3. `notebooks/03_parse_race_predictor.ipynb`
4. `notebooks/04_parse_training_readiness.ipynb`
5. `notebooks/05_parse_max_met.ipynb`
6. `notebooks/06_parse_training_history.ipynb`
7. `notebooks/07_daily_master_table.ipynb`
8. `notebooks/08_prediction_analysis.ipynb`

---

## Current Outputs

### Processed Datasets

Current processed datasets include:
- `runs_v1.parquet`
- `acute_training_load_v1.parquet`
- `race_predictions_v1.parquet`
- `training_readiness_v1.parquet`
- `training_history_v1.parquet`
- `max_met_v1.parquet`
- `daily_master_v1.parquet`

### Daily Master Table

An integrated daily-level dataset combining:
- running volume
- training load
- readiness
- race predictions
- VO2 max metrics
- training status

### Visualizations

Current analyses include:
- race prediction trends over time
- event overlays
- Garmin prediction vs official race result comparisons
- training load trends

---

## Current Analysis Work

### Garmin Race Prediction Evaluation

Current work investigates:
- prediction leakage on race days
- prediction stability over time
- prediction accuracy across race distances
- differences between shorter-distance and marathon predictions

Initial observations suggest:
- shorter-distance predictions are relatively stable
- marathon predictions are more volatile and sensitive
- Garmin predictions may become more reliable after consistent training history accumulates

---

## Notes and Caveats

- Garmin export data is highly fragmented across multiple JSON files.
- Different watches provide different levels of sensor and physiological data.
- Some early activity and prediction data may be unreliable due to:
  - older devices
  - GPS issues
  - sparse training history
  - incomplete physiological calibration
- Garmin readiness and training history datasets are snapshot-based and required aggregation into daily summaries.
- Official race results are manually curated to avoid contamination from:
  - warmups
  - cooldowns
  - GPS drift
  - activity aggregation issues

---

## Future Directions

Potential future work includes:

- weekly and block-level training analysis
- marathon build comparisons
- geospatial run visualizations
- performance trend modeling
- VO2 max prediction systems
- wearable data validation studies
- ML-based fatigue or readiness estimation
- interactive dashboards and web applications

---

## Status

Project currently in active exploratory development.