import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import (
    build_block_daily_volume_chart,
    build_block_physiology_chart,
    build_block_readiness_chart,
    build_block_status_chart,
    build_block_training_load_chart,
    build_block_weekly_mileage_chart,
    build_global_timeline_chart,
    build_monthly_mileage_chart,
    build_personal_best_chart,
    build_prediction_drift_chart,
    build_prediction_error_chart,
    build_prediction_chart,
    build_prediction_timeline_by_block_chart,
    build_stability_error_chart,
    build_stabilization_timeline_chart,
    build_volatility_relationship_chart,
    build_volatility_timeline_chart,
    build_volatility_by_block_chart,
)
from src.formatting import format_date, format_minutes
from src.load_data import (
    BLOCK_FILES,
    PREDICTION_COLUMN,
    load_all_block_daily,
    load_block_data,
    load_block_date_ranges,
)
from src.maps import build_run_atlas_deck, prepare_run_map_data, summarize_map_bounds


ASSETS_DIR = Path(__file__).parent.parent / "app" / "assets"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_CAPTIONS = {
    "indy_medal": "Indianapolis medal",
    "boston_marathon": "Boston Marathon",
    "boston_group": "Boston Marathon training group",
    "boston_training": "Boston training",
    "indy_ground": "Indianapolis race day",
}


def render_metric_row(metrics):
    columns = st.columns(len(metrics))
    for column, metric in zip(columns, metrics):
        label, value, *rest = metric
        delta = rest[0] if rest else None
        column.metric(label, value, delta=delta)


def distance_label(miles, distance_unit):
    if pd.isna(miles):
        return "N/A"
    if distance_unit == "km":
        return f"{miles * 1.609344:,.1f} km"
    return f"{miles:,.1f} mi"


def distance_unit_name(distance_unit):
    return "kilometers" if distance_unit == "km" else "miles"


def standard_race_distance_miles(race_type):
    race_type = str(race_type).lower()
    if race_type == "marathon":
        return 26.2188
    if race_type == "half":
        return 13.1094
    if race_type == "10k":
        return 6.2137
    if race_type == "5k":
        return 3.1069
    return pd.NA


def render_page_intro(title, description, caption=None):
    if caption:
        st.caption(caption.upper())
    st.title(title)
    st.write(description)


def figure_caption(text):
    st.caption(text)


def get_asset_image_by_stem(stem):
    for image_path in find_asset_images():
        if image_path.stem.lower() == stem.lower():
            return image_path
    return None


def find_asset_images(keywords=None):
    if not ASSETS_DIR.exists():
        return []

    image_paths = [
        path
        for path in sorted(ASSETS_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not keywords:
        return image_paths

    lowered_keywords = [keyword.lower() for keyword in keywords]
    return [
        path
        for path in image_paths
        if any(keyword in path.stem.lower() for keyword in lowered_keywords)
    ]


def get_image_caption(image_path):
    return IMAGE_CAPTIONS.get(image_path.stem.lower(), image_path.stem.replace("_", " ").title())


def image_to_data_uri(image_path):
    suffix = image_path.suffix.lower().lstrip(".")
    mime_type = "jpeg" if suffix == "jpg" else suffix
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:image/{mime_type};base64,{encoded}"


def render_home_hero(image_path, large=False):
    if not image_path:
        render_page_intro(
            "Endurance Performance Project",
            (
                "A personal endurance analytics dashboard built from multi-year Garmin "
                "telemetry, marathon training blocks, physiological signals, and official "
                "race outcomes."
            ),
            "Historical running intelligence",
        )
        return

    st.markdown(
        f"""
        <div class="hero-card {'hero-card--large' if large else ''}" style="background-image: url('{image_to_data_uri(image_path)}');">
            <div class="hero-card__overlay">
                <div class="hero-card__eyebrow">Historical Running Intelligence</div>
                <h1 class="hero-card__title">Endurance Performance Project</h1>
                <div class="hero-card__copy">
                    A personal endurance analytics dashboard built from Garmin telemetry,
                    marathon training blocks, physiological signals, and official race outcomes.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_landing_page():
    landing_image = get_asset_image_by_stem("boston_training_landing") or get_asset_image_by_stem("boston_training")
    landing_image_markup = (
        f'<img class="landing-image" src="{image_to_data_uri(landing_image)}" alt="">'
        if landing_image is not None
        else ""
    )

    st.markdown(
        f"""
        <section class="landing-hero">
            {landing_image_markup}
            <div class="landing-scrim">
                <div class="landing-bubble">
                    <div class="landing-eyebrow">Endurance Performance Project</div>
                    <h1 class="landing-title">A living archive of training, racing, and adaptation.</h1>
                    <div class="landing-copy">
                        This dashboard turns Garmin history into a personal performance system:
                        marathon blocks, official race outcomes, prediction dynamics, training
                        volume, VO2, readiness, and the long arc of becoming fitter over time.
                    </div>
                    <div class="landing-actions">
                        <a class="landing-enter" href="?dashboard=1" target="_self">Enter dashboard</a>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_html_card(class_name, eyebrow, title, copy):
    st.markdown(
        f"""
        <div class="{class_name}">
            <div class="card-eyebrow">{eyebrow}</div>
            <div class="card-title">{title}</div>
            <div class="card-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def race_report_copy(summary_row, distance_unit="mi"):
    error = summary_row["prediction_error"]
    bias = summary_row["prediction_bias"]
    error_text = f"{abs(error):.1f} minutes"
    if bias == "conservative":
        prediction_sentence = f"Garmin was conservative by {error_text}, predicting a slower race than the official result."
    elif bias == "optimistic":
        prediction_sentence = f"Garmin was optimistic by {error_text}, predicting a faster race than the official result."
    else:
        prediction_sentence = "Garmin landed very close to the official result."

    return (
        f"{prediction_sentence} The estimate stabilized {int(summary_row['days_stable_before_race'])} "
        f"days before race day, while the block peaked at {distance_label(summary_row['peak_weekly_mileage'], distance_unit)} "
        f"and averaged {distance_label(summary_row['avg_weekly_mileage'], distance_unit)} per week. "
        f"VO2 drift was {summary_row['vo2_drift']:+.1f}, average readiness was "
        f"{summary_row['avg_readiness']:.1f}, and average HRV was {summary_row['avg_hrv']:.1f}."
    )


def render_race_report_card(summary_row, distance_unit="mi"):
    render_html_card(
        "race-report-card",
        "Race report",
        f"{summary_row['block_name']} | {format_minutes(summary_row['actual_time'])}",
        race_report_copy(summary_row, distance_unit),
    )


def prepare_personal_best_data(events_df, runs_df, distance_unit="mi"):
    race_df = events_df[
        events_df["event_type"].eq("race") & events_df["official_time_min"].notna()
    ].copy()
    if race_df.empty:
        return race_df

    race_df["event_date"] = pd.to_datetime(race_df["date"])
    race_df["race_type_label"] = race_df["race_type"].fillna("race").str.upper()
    race_df["distance_miles_standard"] = race_df["race_type"].map(standard_race_distance_miles)
    race_df["distance_value"] = race_df["distance_miles_standard"]
    if distance_unit == "km":
        race_df["distance_value"] = race_df["distance_miles_standard"] * 1.609344
    race_df["distance_display"] = race_df["distance_miles_standard"].map(
        lambda miles: distance_label(miles, distance_unit)
    )
    race_df["official_time_label"] = race_df["official_time_min"].map(format_minutes)
    race_df["pace_minutes"] = race_df["official_time_min"] / race_df["distance_value"]
    race_df["pace_label"] = race_df["pace_minutes"].map(format_minutes)
    race_df["matched_run_name"] = "No same-day Garmin run matched"
    race_df["matched_location"] = ""
    race_df["recorded_distance_miles"] = pd.NA

    runs_by_date = runs_df.copy()
    runs_by_date["event_date"] = runs_by_date["start_time"].dt.normalize()

    for index, event in race_df.iterrows():
        same_day_runs = runs_by_date[runs_by_date["event_date"].eq(event["event_date"].normalize())].copy()
        if same_day_runs.empty:
            continue
        same_day_runs["duration_delta"] = (
            same_day_runs["duration_minutes"] - event["official_time_min"]
        ).abs()
        matched_run = same_day_runs.sort_values(["duration_delta", "distance_miles"]).iloc[0]
        race_df.loc[index, "matched_run_name"] = matched_run["name"]
        race_df.loc[index, "matched_location"] = matched_run.get("locationName", "")
        race_df.loc[index, "recorded_distance_miles"] = matched_run["distance_miles"]

    return race_df.sort_values("event_date")


def render_overview(summary_df, runs_df, distance_unit="mi"):
    total_runs = len(runs_df)
    total_miles = runs_df["distance_miles"].sum()
    first_run = runs_df["start_time"].min()
    latest_run = runs_df["start_time"].max()
    mean_abs_error = summary_df["prediction_error"].abs().mean()
    peak_weekly = summary_df["peak_weekly_mileage"].max()

    hero_image = get_asset_image_by_stem("boston_group")
    render_home_hero(hero_image)

    st.write(
        "The goal is to turn years of training history into a clearer performance "
        "record: how race predictions evolved, when they stabilized, how training load "
        "and recovery signals moved, and where the watch aligned with race-day reality."
    )

    st.subheader("Start Here")
    start_columns = st.columns(4)
    with start_columns[0]:
        render_html_card(
            "finding-card",
            "Scope",
            "Historical Garmin export",
            "This is a cleaned historical analysis, not a live API-connected training app.",
        )
    with start_columns[1]:
        render_html_card(
            "finding-card",
            "First stop",
            "Key Findings",
            "Use the synthesis page for the shortest read on what changed across race blocks.",
        )
    with start_columns[2]:
        render_html_card(
            "finding-card",
            "Deep dive",
            "Block Explorer",
            "Open each marathon block to inspect volume, readiness, prediction behavior, and race context.",
        )
    with start_columns[3]:
        render_html_card(
            "finding-card",
            "Caveat",
            "Exploratory evidence",
            "The patterns are personal and useful, but the sample is still small.",
        )

    st.divider()

    render_metric_row(
        [
            ("Total runs", f"{total_runs:,}"),
            (f"Historical {distance_unit_name(distance_unit)}", distance_label(total_miles, distance_unit)),
            ("Training history", f"{first_run:%Y} - {latest_run:%Y}"),
            ("Marathon blocks", f"{summary_df['block_name'].nunique()}"),
            ("Avg prediction miss", f"{mean_abs_error:.1f} min"),
        ]
    )

    st.subheader("Historical Running Volume")
    st.write(
        "A month-by-month view of the full training archive. The marathon block pages "
        "build on this broader base instead of treating each race cycle in isolation."
    )
    st.plotly_chart(build_monthly_mileage_chart(runs_df, distance_unit), use_container_width=True)
    figure_caption(
        f"Monthly volume frames the project historically: sustained {distance_unit_name(distance_unit)}, race-build "
        "ramps, downtime, and the background training load behind each marathon block."
    )

    st.subheader("Research Questions")
    question_columns = st.columns(3)
    question_columns[0].write("**Prediction behavior**")
    question_columns[0].write("How did Garmin marathon estimates move as training became more consistent and race-specific?")
    question_columns[1].write("**Stability timing**")
    question_columns[1].write("When did predictions settle into a narrow range before race day?")
    question_columns[2].write("**Race outcome context**")
    question_columns[2].write("Where did final predictions overestimate or underestimate the official result?")

    st.subheader("Marathon Block Snapshot")
    snapshot_columns = st.columns(summary_df["block_name"].nunique())
    for column, (_, row) in zip(snapshot_columns, summary_df.sort_values("race_date").iterrows()):
        column.metric(
            row["block_name"].replace(" Marathon", ""),
            format_minutes(row["actual_time"]),
            f"{row['prediction_error']:+.1f} min",
        )
    figure_caption(
        f"Block-level metrics come from the curated marathon summary table. "
        f"The highest peak week analyzed is {distance_label(peak_weekly, distance_unit)}."
    )


def render_block_metrics(summary_row, distance_unit="mi"):
    render_metric_row(
        [
            ("Official race time", format_minutes(summary_row["actual_time"])),
            ("Final Garmin prediction", format_minutes(summary_row["final_prediction"])),
            (
                "Prediction error",
                f"{summary_row['prediction_error']:+.1f} min",
                summary_row["prediction_bias"].title(),
            ),
            (
                "Stable before race",
                f"{int(summary_row['days_stable_before_race'])} days",
                format_date(summary_row["stable_date"]),
            ),
            ("Peak week", distance_label(summary_row["peak_weekly_mileage"], distance_unit)),
        ]
    )


def render_key_findings(summary_df, distance_unit="mi"):
    comparison_df = summary_df.copy()
    comparison_df["absolute_error"] = comparison_df["prediction_error"].abs()
    closest_prediction = comparison_df.sort_values("absolute_error").iloc[0]
    biggest_miss = comparison_df.sort_values("absolute_error", ascending=False).iloc[0]
    earliest_stability = comparison_df.sort_values("days_stable_before_race", ascending=False).iloc[0]
    highest_peak = comparison_df.sort_values("peak_weekly_mileage", ascending=False).iloc[0]
    best_marathon = comparison_df.sort_values("actual_time").iloc[0]

    render_page_intro(
        "Key Findings",
        (
            "A concise synthesis of the marathon block analysis: what looked meaningful, "
            "where the watch was useful, and where the evidence is still early."
        ),
        "Dashboard synthesis",
    )

    render_metric_row(
        [
            ("Best marathon", best_marathon["block_name"], format_minutes(best_marathon["actual_time"])),
            ("Closest prediction", closest_prediction["block_name"], f"{closest_prediction['absolute_error']:.1f} min miss"),
            ("Earliest stability", earliest_stability["block_name"], f"{int(earliest_stability['days_stable_before_race'])} days"),
            ("Highest peak week", highest_peak["block_name"], distance_label(highest_peak["peak_weekly_mileage"], distance_unit)),
        ]
    )

    st.subheader("What Stands Out")
    finding_columns = st.columns(3)
    with finding_columns[0]:
        render_html_card(
            "finding-card",
            "Finding 01",
            "Prediction stability varied by block",
            (
                f"{earliest_stability['block_name']} stabilized earliest at "
                f"{int(earliest_stability['days_stable_before_race'])} days before race day. "
                "That makes stabilization timing worth tracking alongside the final estimate."
            ),
        )
    with finding_columns[1]:
        render_html_card(
            "finding-card",
            "Finding 02",
            "Garmin bias moved both directions",
            (
                "The watch was not consistently optimistic or conservative. Some blocks "
                "finished with faster predictions than reality, while others gave room back."
            ),
        )
    with finding_columns[2]:
        render_html_card(
            "finding-card",
            "Finding 03",
            "Training context matters",
            (
                f"{highest_peak['block_name']} produced the highest peak week at "
                f"{distance_label(highest_peak['peak_weekly_mileage'], distance_unit)}, but accuracy still depended "
                "on more than volume alone."
            ),
        )

    st.subheader("Race Report Cards")
    for row_pair_start in range(0, len(comparison_df), 2):
        columns = st.columns(2)
        for column, (_, row) in zip(columns, comparison_df.iloc[row_pair_start : row_pair_start + 2].iterrows()):
            with column:
                render_race_report_card(row, distance_unit)

    st.info(
        "This page summarizes personal historical patterns. It is useful for reflection "
        "and future hypotheses, not broad claims about Garmin prediction accuracy."
    )


def render_timeline_view(summary_df, daily_df, distance_unit="mi"):
    render_page_intro(
        "Timeline View",
        (
            "A single longitudinal view that overlays weekly distance, marathon race dates, "
            "VO2 max, and Garmin marathon prediction changes."
        ),
        "All-history training timeline",
    )

    st.plotly_chart(build_global_timeline_chart(daily_df, summary_df, distance_unit), use_container_width=True)
    figure_caption(
        f"Weekly {distance_unit_name(distance_unit)} are shown as bars. VO2 max and marathon prediction are layered as "
        "lines, while dotted vertical markers identify the analyzed marathon race dates."
    )

    with st.expander("Data notes"):
        st.write(
            "This timeline is powered by `daily_master_v1.parquet` and starts on "
            "January 1, 2021. Race markers come from `marathon_block_summary_v1.parquet`."
        )
        st.write(
            "Weekly volume is aggregated from daily distance. VO2 max and marathon prediction "
            "are Garmin-derived daily fields and may contain missing periods."
        )

    st.subheader("Race Markers")
    marker_columns = st.columns(summary_df["block_name"].nunique())
    for column, (_, row) in zip(marker_columns, summary_df.sort_values("race_date").iterrows()):
        column.metric(
            row["block_name"].replace(" Marathon", ""),
            format_date(row["race_date"]),
            format_minutes(row["actual_time"]),
        )


def render_personal_best_tracker(events_df, runs_df, distance_unit="mi"):
    render_page_intro(
        "Personal Best Tracker",
        (
            "A race-result tracker built from the events table, with same-day Garmin "
            "activities matched in for supporting activity details."
        ),
        "Performance milestones",
    )

    pb_df = prepare_personal_best_data(events_df, runs_df, distance_unit)
    if pb_df.empty:
        st.warning("No race rows with official times were found in the events table.")
        return

    best_by_type = pb_df.sort_values("official_time_min").groupby("race_type_label", as_index=False).first()
    fastest_race = pb_df.sort_values("pace_minutes").iloc[0]

    render_metric_row(
        [
            ("Race events", f"{len(pb_df):,}"),
            ("Current PB categories", f"{best_by_type['race_type_label'].nunique()}"),
            ("Fastest race pace", fastest_race["pace_label"], fastest_race["label"]),
            ("Most recent race", format_date(pb_df["event_date"].max())),
        ]
    )

    st.plotly_chart(build_personal_best_chart(pb_df), use_container_width=True)
    figure_caption(
        "This view uses official event times from events_table. Same-day Garmin activities "
        "are matched only to add activity context, not to define the PR."
    )

    with st.expander("Data notes"):
        st.write(
            "Race results come from `data_raw/events_table.csv`. Garmin activity records "
            "from `runs_v1.parquet` are matched by same calendar date for context."
        )
        st.write(
            "Current PB categories are calculated as the fastest official time within each "
            "race type listed in the events table."
        )

    st.subheader("Current Personal Bests")
    pb_columns = st.columns(len(best_by_type))
    for column, (_, row) in zip(pb_columns, best_by_type.iterrows()):
        column.metric(row["race_type_label"], row["official_time_label"], format_date(row["event_date"]))

def render_how_garmin_works():
    render_page_intro(
        "How Garmin Works",
        (
            "Context for interpreting Garmin race predictions and the assumptions behind "
            "this personal analysis."
        ),
        "Model context",
    )

    st.write(
        "It is important to consider how the technology behind Garmin's race prediction "
        "works in order to understand this analysis. Although the specific details of "
        "Garmin's computations are not fully public, we know that Garmin takes into "
        "account VO2 estimates, training history, and previous personal records to "
        "provide a target race time."
    )
    st.write(
        "It is also possible to obtain event-specific race predictions that account for "
        "environmental factors such as elevation, temperature, altitude, and wind."
    )
    st.info(
        'Garmin notes that "it is advisable to have longer activities in your history '
        'in the weeks leading up to the race event for more accurate predictions."'
    )
    st.write(
        "This makes sense: more relevant data often leads to better-informed predictions "
        "and models, especially for longer events like the marathon."
    )
    st.write(
        "I also want to highlight the importance of VO2 max in these race predictions. "
        "Even though I do not have specific knowledge of Garmin's internal model, this "
        "metric is widely used across the endurance and wearable-technology industries "
        "as a representation of overall cardiovascular fitness."
    )
    st.write(
        "Companies such as WHOOP treat VO2 max as a gold-standard marker because it has "
        "become one of the most reliable physiological indicators of aerobic capacity, "
        "which is highly relevant in the world of marathoning."
    )


def render_block_explorer(summary_df, distance_unit="mi"):
    render_page_intro(
        "Marathon Block Explorer",
        (
            "A focused cockpit for each marathon build, connecting training volume, "
            "load, readiness, physiology, prediction movement, and race outcome context."
        ),
        "Block-level performance view",
    )

    selected_block = st.selectbox("Marathon block", list(BLOCK_FILES.keys()))
    block_df = load_block_data(BLOCK_FILES[selected_block])
    summary_row = summary_df[summary_df["block_name"].eq(selected_block)].iloc[0]
    prediction_df = block_df.dropna(subset=[PREDICTION_COLUMN]).sort_values("date")

    st.subheader(selected_block)
    st.write(
        f"Race date: {format_date(summary_row['race_date'])}. "
        f"Training window: {format_date(block_df['date'].min())} to "
        f"{format_date(block_df['date'].max())}."
    )

    render_block_metrics(summary_row, distance_unit)
    st.divider()

    (
        report_tab,
        overview_tab,
        prediction_tab,
        training_tab,
        recovery_tab,
        physiology_tab,
        status_tab,
    ) = st.tabs(
        [
            "Race Report",
            "Block Overview",
            "Prediction",
            "Training Load",
            "Recovery",
            "Physiology",
            "Status",
        ]
    )

    with report_tab:
        render_race_report_card(summary_row, distance_unit)
        st.write("")
        report_columns = st.columns(3)
        report_columns[0].metric("Race result", format_minutes(summary_row["actual_time"]))
        report_columns[1].metric("Garmin final", format_minutes(summary_row["final_prediction"]))
        report_columns[2].metric("Prediction bias", summary_row["prediction_bias"].title(), f"{summary_row['prediction_error']:+.1f} min")
        st.write(
            "This card is generated from the curated block summary table, so the narrative "
            "stays tied to the official block metrics rather than the raw daily data."
        )

    with overview_tab:
        context_columns = st.columns(4)
        context_columns[0].metric("Average weekly distance", distance_label(summary_row["avg_weekly_mileage"], distance_unit))
        context_columns[1].metric("Average training load", f"{summary_row['avg_training_load']:.0f}")
        context_columns[2].metric("Average readiness", f"{summary_row['avg_readiness']:.1f}")
        context_columns[3].metric("Average HRV", f"{summary_row['avg_hrv']:.1f}")

        left, right = st.columns(2)
        with left:
            st.plotly_chart(build_block_weekly_mileage_chart(block_df, distance_unit), use_container_width=True)
            figure_caption(
                f"Weekly {distance_unit_name(distance_unit)} show the broad architecture of the build: progression, "
                "peak workload, recovery weeks, and taper."
            )
        with right:
            st.plotly_chart(build_block_daily_volume_chart(block_df, distance_unit), use_container_width=True)
            figure_caption(
                f"Daily {distance_unit_name(distance_unit)} add texture underneath the weekly totals, while the "
                "7-day average smooths the short-term training rhythm."
            )

    with prediction_tab:
        st.plotly_chart(
            build_prediction_chart(
                prediction_df=prediction_df,
                final_prediction=summary_row["final_prediction"],
                stable_date=summary_row["stable_date"],
            ),
            use_container_width=True,
        )
        figure_caption(
            "The shaded band marks +/- 2 minutes around the final pre-race prediction. "
            "The vertical marker shows when the final stable window began."
        )

    with training_tab:
        st.plotly_chart(build_block_training_load_chart(block_df), use_container_width=True)
        figure_caption(
            "Acute and chronic load describe short-term strain against longer-term "
            "fitness context. ACWR highlights rapid workload shifts."
        )

    with recovery_tab:
        st.plotly_chart(build_block_readiness_chart(block_df), use_container_width=True)
        figure_caption(
            "Readiness, sleep, and recovery time show how Garmin framed day-to-day "
            "preparedness during the build."
        )

    with physiology_tab:
        st.plotly_chart(build_block_physiology_chart(block_df), use_container_width=True)
        figure_caption(
            "VO2 max, HRV, and average run heart rate provide a compact view of fitness "
            "signals and physiological strain."
        )

    with status_tab:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                build_block_status_chart(block_df, "training_status", "Training Status Distribution"),
                use_container_width=True,
            )
            figure_caption("Distribution of Garmin training-status labels during the selected block.")
        with right:
            st.plotly_chart(
                build_block_status_chart(block_df, "acwrStatus", "ACWR Status Distribution"),
                use_container_width=True,
            )
            figure_caption("Distribution of Garmin acute:chronic workload labels during the selected block.")

def render_prediction_dynamics(summary_df, distance_unit="mi"):
    render_page_intro(
        "Prediction Dynamics",
        (
            "A deeper look at Garmin marathon prediction behavior across training "
            "blocks: volatility, stabilization, drift, and final race-day error."
        ),
        "Exploratory model behavior analysis",
    )

    comparison_df = summary_df.copy()
    comparison_df["absolute_error"] = comparison_df["prediction_error"].abs()
    block_daily_df = load_all_block_daily()
    most_stable = comparison_df.sort_values("mean_volatility").iloc[0]
    most_volatile = comparison_df.sort_values("mean_volatility", ascending=False).iloc[0]
    earliest_stability = comparison_df.sort_values(
        "days_stable_before_race", ascending=False
    ).iloc[0]
    closest_prediction = comparison_df.sort_values("absolute_error").iloc[0]

    render_metric_row(
        [
            (
                "Lowest volatility",
                most_stable["block_name"],
                f"{most_stable['mean_volatility']:.2f} min",
            ),
            (
                "Highest volatility",
                most_volatile["block_name"],
                f"{most_volatile['mean_volatility']:.2f} min",
            ),
            (
                "Earliest stability",
                earliest_stability["block_name"],
                f"{int(earliest_stability['days_stable_before_race'])} days",
            ),
            (
                "Closest final prediction",
                closest_prediction["block_name"],
                f"{closest_prediction['absolute_error']:.1f} min miss",
            ),
        ]
    )

    st.info(
        "Read this section as exploratory evidence. The dataset is rich, but the race "
        "sample is still small, so the strongest takeaway is pattern discovery rather "
        "than statistical proof."
    )

    with st.expander("Data notes"):
        st.write(
            "Block-level prediction metrics come from `marathon_block_summary_v1.parquet`. "
            "Daily prediction and volatility timelines combine the four processed marathon block files."
        )
        st.write(
            "This page should be read as single-athlete exploratory analysis. It is meant "
            "to surface patterns, not prove causal relationships."
        )

    (
        findings_tab,
        timelines_tab,
        relationships_tab,
        accuracy_tab,
    ) = st.tabs(
        [
            "Findings",
            "Timelines",
            "Relationships",
            "Accuracy",
        ]
    )

    with findings_tab:
        st.subheader("Notebook Findings, Dashboard Version")
        st.write(
            "The analysis did not uncover one clean driver of Garmin prediction changes. "
            "Instead, the story appears to be block-specific: prediction curves, volatility, "
            "and final error all changed depending on the training cycle."
        )
        finding_columns = st.columns(2)
        with finding_columns[0]:
            st.write("**Prediction behavior was block-specific.**")
            st.write(
                "Garmin marathon predictions did not evolve uniformly across training "
                "cycles. Indianapolis looked relatively stable, Mesa showed more "
                "abrupt swings, BQ had repeated oscillation, and Boston showed an "
                "initial adaptation phase followed by steadier behavior."
            )
            st.write("**Stabilization may be meaningful.**")
            st.write(
                "Several blocks settled within a narrow range weeks before race day. "
                "That stabilization pattern may be more informative than the final "
                "prediction alone, but it still needs more race samples."
            )
        with finding_columns[1]:
            st.write("**Physiological relationships looked weak.**")
            st.write(
                "The notebook did not find a strong relationship between prediction "
                "volatility and readiness, ACWR, or training load. Some stressed or "
                "aggressive periods lined up with volatility, but not consistently."
            )
            st.write("**Bias was not uniform.**")
            st.write(
                "Garmin alternated between optimistic and conservative marathon "
                "predictions. The direction and size of error varied by block."
            )

        left, right = st.columns(2)
        with left:
            st.plotly_chart(build_volatility_by_block_chart(comparison_df), use_container_width=True)
            figure_caption(
                "Mean rolling volatility summarizes how jumpy the marathon prediction "
                "was inside each block."
            )
        with right:
            st.plotly_chart(
                build_stabilization_timeline_chart(comparison_df),
                use_container_width=True,
            )
            figure_caption(
                "Each line runs from the first stable prediction date to race day. "
                "Longer windows suggest the estimate settled earlier."
            )

    with timelines_tab:
        st.subheader("Prediction Motion Through the Build")
        st.write(
            "These timelines align blocks by training-day number so the shape of each "
            "build can be compared directly, even though the races happened on different "
            "calendar dates."
        )
        volatility_window = st.radio(
            "Rolling volatility window",
            ["7-day", "15-day", "30-day"],
            horizontal=True,
        )
        volatility_column = {
            "7-day": "rolling_std_7_Marathond_x",
            "15-day": "rolling_std_15_Marathond_x",
            "30-day": "rolling_std_30_Marathond_x",
        }[volatility_window]

        st.plotly_chart(
            build_volatility_timeline_chart(block_daily_df, volatility_column),
            use_container_width=True,
        )
        figure_caption(
            "Rolling volatility measures short-term prediction instability. Higher "
            "values mean the watch estimate was moving around more from day to day."
        )
        st.plotly_chart(
            build_prediction_timeline_by_block_chart(block_daily_df),
            use_container_width=True,
        )
        figure_caption(
            "Aligned prediction curves show whether estimates improved steadily, drifted, "
            "or moved in abrupt steps during each marathon build."
        )

    with relationships_tab:
        st.subheader("Signal Checks")
        st.write(
            "This view tests whether obvious training and recovery signals line up with "
            "prediction volatility. The early answer is cautious: relationships exist in "
            "moments, but no single variable clearly explains the prediction swings."
        )
        relationship_columns = st.columns(2)
        with relationship_columns[0]:
            st.plotly_chart(
                build_volatility_relationship_chart(
                    block_daily_df,
                    "dailyTrainingLoadAcute",
                    "Acute Training Load vs Prediction Volatility",
                    "Acute training load",
                    distance_unit,
                ),
                use_container_width=True,
            )
            figure_caption("Acute load is a short-term workload measure. The relationship with prediction volatility appears noisy.")
            st.plotly_chart(
                build_volatility_relationship_chart(
                    block_daily_df,
                    "readiness_score_mean",
                    "Readiness vs Prediction Volatility",
                    "Readiness score",
                    distance_unit,
                ),
                use_container_width=True,
            )
            figure_caption("Readiness does not appear to provide a clean one-variable explanation for volatility.")
        with relationship_columns[1]:
            st.plotly_chart(
                build_volatility_relationship_chart(
                    block_daily_df,
                    "dailyAcuteChronicWorkloadRatio",
                    "ACWR vs Prediction Volatility",
                    "Acute:chronic workload ratio",
                    distance_unit,
                ),
                use_container_width=True,
            )
            figure_caption("ACWR captures workload balance, but the chart does not show a simple threshold effect.")
            st.plotly_chart(
                build_volatility_relationship_chart(
                    block_daily_df,
                    "total_distance_miles",
                    "Daily Distance vs Prediction Volatility",
                    "Daily distance",
                    distance_unit,
                ),
                use_container_width=True,
            )
            figure_caption(f"Daily {distance_unit_name(distance_unit)} show training dose, but prediction volatility still varies by block context.")

    with accuracy_tab:
        st.subheader("Final Estimate vs Race Outcome")
        st.write(
            "The accuracy view separates two ideas: how much the prediction changed "
            "during the block, and how close the final pre-race estimate was to the "
            "official result."
        )
        left, right = st.columns(2)
        with left:
            st.plotly_chart(build_prediction_error_chart(comparison_df), use_container_width=True)
            figure_caption(
                "Positive error means Garmin predicted a slower marathon than the official "
                "result. Negative error means Garmin was too optimistic."
            )
            st.plotly_chart(build_stability_error_chart(comparison_df, distance_unit), use_container_width=True)
            figure_caption(
                "This chart asks whether earlier stabilization lined up with lower final "
                "error. With four races, it is a prompt for future tracking."
            )
        with right:
            st.plotly_chart(build_prediction_drift_chart(comparison_df), use_container_width=True)
            figure_caption(
                "Prediction drift is the net movement from early block context to the "
                "final pre-race estimate."
            )
            st.write("**Reading the signs**")
            st.write(
                "Positive error means the final Garmin prediction was slower than the "
                "official result; negative error means Garmin was more optimistic than "
                "the race outcome."
            )
            st.write(
                "Prediction drift describes how much the marathon prediction changed "
                "from early block context toward the final pre-race estimate."
            )

    with st.expander("Limitations"):
        st.write(
            "This analysis is based on one athlete and four fully "
            "documented marathon blocks. That makes the patterns useful for personal "
            "reflection and hypothesis generation, but not statistically strong."
        )
        st.write(
            "Garmin export data also required substantial cleaning. Device changes, "
            "missing physiological metrics, duplicate snapshots, and race-day leakage "
            "can all affect derived prediction metrics."
        )
        st.write(
            "The safest conclusion for now: marathon prediction dynamics appear to "
            "vary by block, and volatility/stabilization may be worth tracking, but "
            "no single training or readiness variable explains the behavior on its own."
        )


def render_running_atlas(runs_df, distance_unit="mi"):
    render_page_intro(
        "Running Atlas",
        (
            "An interactive map of the training archive, built from Garmin activity GPS "
            "coordinates. This view turns the run log into a geographic footprint."
        ),
        "Athlete training history atlas",
    )

    block_ranges = load_block_date_ranges()
    map_df = prepare_run_map_data(runs_df, block_ranges)

    if map_df.empty:
        st.warning("No runs with usable GPS start coordinates were found.")
        return

    years = sorted(map_df["year"].dropna().unique().tolist())
    activity_types = sorted(map_df["activityType"].dropna().unique().tolist())
    block_options = sorted(map_df["marathon_block"].dropna().unique().tolist())
    distance_multiplier = 1.609344 if distance_unit == "km" else 1
    distance_abbrev = "km" if distance_unit == "km" else "mi"
    distance_column = "distance_display"
    map_df[distance_column] = map_df["distance_miles"] * distance_multiplier
    min_distance = float(map_df[distance_column].min())
    max_distance = float(map_df[distance_column].max())

    filter_columns = st.columns([1.1, 1.4, 1.2, 1.2])
    with filter_columns[0]:
        selected_years = st.multiselect("Year", years, default=years)
    with filter_columns[1]:
        selected_blocks = st.multiselect(
            "Marathon block",
            block_options,
            default=block_options,
        )
    with filter_columns[2]:
        selected_types = st.multiselect(
            "Activity type",
            activity_types,
            default=activity_types,
        )
    with filter_columns[3]:
        distance_range = st.slider(
            f"Distance range ({distance_abbrev})",
            min_value=round(min_distance, 1),
            max_value=round(max_distance, 1),
            value=(round(min_distance, 1), round(max_distance, 1)),
            step=0.5,
        )

    display_columns = st.columns([1, 1, 2])
    with display_columns[0]:
        show_route_chords = st.toggle("Route chords", value=True)
    with display_columns[1]:
        show_end_points = st.toggle("End points", value=True)
    with display_columns[2]:
        st.caption(
            "Route chords connect each activity's start and end coordinates. Full route "
            "polylines can be added later once processed coordinate streams are available."
        )

    filtered_df = map_df[
        map_df["year"].isin(selected_years)
        & map_df["marathon_block"].isin(selected_blocks)
        & map_df["activityType"].isin(selected_types)
        & map_df[distance_column].between(distance_range[0], distance_range[1])
    ].copy()

    if filtered_df.empty:
        st.warning("No runs match the current filters.")
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("Mapped runs", f"{len(filtered_df):,}")
    metric_columns[1].metric(f"Mapped {distance_unit_name(distance_unit)}", f"{filtered_df[distance_column].sum():,.0f} {distance_abbrev}")
    metric_columns[2].metric("Longest run", f"{filtered_df[distance_column].max():.1f} {distance_abbrev}")
    metric_columns[3].metric("Footprint", summarize_map_bounds(filtered_df))

    st.pydeck_chart(
        build_run_atlas_deck(
            filtered_df,
            show_route_chords=show_route_chords,
            show_end_points=show_end_points,
        ),
        use_container_width=True,
    )
    figure_caption(
        "Marker size scales with activity distance. Blue-orange arcs show start-to-end "
        "route direction for activities with usable endpoint coordinates."
    )
