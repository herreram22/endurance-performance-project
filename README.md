# Health Performance Project

A longitudinal endurance performance analytics project built using multi-year Garmin telemetry, physiological metrics, and marathon training data.

This project investigates how wearable-derived race predictions evolve throughout marathon training cycles and explores the relationships between prediction stability, training load, readiness, recovery, and race outcomes using real-world endurance training data.

The repository combines:

* wearable data engineering
* longitudinal athlete monitoring
* exploratory performance science
* physiological signal analysis
* and predictive performance evaluation

---

## Overview

This repository currently contains notebooks for:

* Parsing Garmin activity and metrics exports
* Building cleaned and structured datasets
* Creating an integrated daily master table
* Evaluating Garmin race prediction behavior
* Exploring relationships between training load, readiness, recovery, and performance
* Comparing marathon training blocks longitudinally
* Investigating prediction stability and volatility during marathon builds

The project evolved from a personal running analytics experiment into a broader investigation of how wearable systems estimate, update, and communicate endurance fitness throughout marathon training cycles.

---

## Preliminary Findings

Initial exploratory analysis revealed several notable patterns:

* Garmin marathon predictions exhibited substantially different volatility profiles across marathon blocks.
* Some marathon blocks stabilized remarkably early, with predictions remaining within ±2 minutes of the final pre-race estimate more than 50 days before race day.
* Prediction volatility appeared highly block-dependent rather than strictly load-dependent.
* Elevated volatility periods occasionally coincided with lower readiness states and more aggressive workload dynamics.
* Garmin prediction leakage effects were observed on race days, requiring exclusion of race-day predictions from volatility analysis.
* Real-world wearable telemetry required substantial preprocessing due to duplicate snapshots, inconsistent timestamps, invalid physiological values, and fragmented export structures.

---

## Goals

Current project goals include:

* Building a unified daily training and performance dataset
* Investigating how Garmin race predictions evolve over time
* Comparing predicted race performances against official race results
* Exploring relationships between:

  * training load
  * recovery
  * readiness
  * VO2 max estimates
  * race performance
  * prediction stability
  * marathon block dynamics
* Evaluating the reliability and limitations of wearable-derived physiological models

Long-term goals may include:

* interactive dashboards
* geospatial run visualizations
* predictive modeling
* ML-based performance estimation
* automated training analysis systems
* multi-athlete longitudinal analysis

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
├── data_processed/
│   ├── runs_v1.parquet
│   ├── acute_training_load_v1.parquet
│   ├── race_predictions_v1.parquet
│   ├── training_readiness_v1.parquet
│   ├── training_history_v1.parquet
│   ├── max_met_v1.parquet
│   └── daily_master_v1.parquet
│
├── figures/
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

* distance
* duration
* pace
* cadence
* heart rate
* power
* elevation
* training load

### Metrics

Contains Garmin physiological and training metrics including:

* acute training load
* chronic training load
* ACWR
* load tunnel metrics

### Race Predictor

Contains Garmin race time predictions for:

* 5K
* 10K
* Half Marathon
* Marathon

### Training Readiness

Contains Garmin readiness snapshots and recovery-related metrics such as:

* readiness score
* HRV
* recovery time
* sleep score
* stress history

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

* `runs_v1.parquet`
* `acute_training_load_v1.parquet`
* `race_predictions_v1.parquet`
* `training_readiness_v1.parquet`
* `training_history_v1.parquet`
* `max_met_v1.parquet`
* `daily_master_v1.parquet`

### Daily Master Table

An integrated daily-level dataset combining:

* running volume
* training load
* readiness
* race predictions
* VO2 max metrics
* training status
* HRV metrics
* recovery metrics

### Marathon Block Analysis

Current marathon-specific analyses include:

* prediction stabilization timing
* rolling volatility analysis
* marathon block comparison
* prediction drift throughout training
* relationships between prediction behavior and physiological metrics
* comparison between final predictions and official race performances

### Visualizations

Current analyses include:

* race prediction trends over time
* event overlays
* Garmin prediction vs official race result comparisons
* marathon block stabilization visualizations
* rolling volatility analysis
* training load trends
* physiological relationship exploration

---

## Current Analysis Work

### Garmin Race Prediction Evaluation

Current work investigates:

* prediction leakage on race days
* prediction stability over time
* prediction accuracy across race distances
* differences between shorter-distance and marathon predictions
* stabilization behavior throughout marathon blocks
* relationships between volatility and physiological metrics

Initial observations suggest:

* shorter-distance predictions are relatively stable
* marathon predictions are more volatile and sensitive
* prediction stabilization timing varies substantially between marathon blocks
* prediction volatility appears highly context-dependent
* Garmin predictions may become more reliable after consistent training history accumulates

---

## Notes and Caveats

* Garmin export data is highly fragmented across multiple JSON files.
* Different watches provide different levels of sensor and physiological data.
* Some early activity and prediction data may be unreliable due to:

  * older devices
  * GPS issues
  * sparse training history
  * incomplete physiological calibration
* Garmin readiness and training history datasets are snapshot-based and required aggregation into daily summaries.
* Official race results are manually curated to avoid contamination from:

  * warmups
  * cooldowns
  * GPS drift
  * activity aggregation issues
* Race-day prediction leakage effects were observed in Garmin prediction behavior and required exclusion from certain analyses.
* This project currently analyzes a single-athlete longitudinal dataset and should therefore be interpreted as exploratory rather than broadly generalizable.

---

## Future Directions

Short-term goals include:

* dashboard and visualization development
* improved block-level comparison tools
* geospatial run visualizations
* interactive longitudinal analytics

Long-term goals may include:

* multi-athlete dataset integration
* predictive modeling
* wearable data validation studies
* ML-based fatigue or readiness estimation
* automated training recommendation systems
* large-scale endurance performance analysis

---

## Project Status

Project currently in active exploratory development focused on Garmin prediction dynamics and marathon block analysis.
