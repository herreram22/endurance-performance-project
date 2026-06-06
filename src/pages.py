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
    build_monthly_mileage_chart,
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


def render_overview(summary_df, runs_df):
    total_runs = len(runs_df)
    total_miles = runs_df["distance_miles"].sum()
    first_run = runs_df["start_time"].min()
    latest_run = runs_df["start_time"].max()
    mean_abs_error = summary_df["prediction_error"].abs().mean()
    peak_weekly = summary_df["peak_weekly_mileage"].max()

    render_page_intro(
        "Endurance Performance Project",
        (
            "A personal endurance analytics dashboard built from multi-year Garmin "
            "telemetry, marathon training blocks, physiological signals, and official "
            "race outcomes."
        ),
        "Historical running intelligence",
    )
    hero_image = get_asset_image_by_stem("boston_group")
    if hero_image:
        st.image(str(hero_image), caption=get_image_caption(hero_image), use_container_width=True)

    st.write(
        "The goal is to turn years of training history into a clearer performance "
        "record: how race predictions evolved, when they stabilized, how training load "
        "and recovery signals moved, and where the watch aligned with race-day reality."
    )

    st.divider()

    render_metric_row(
        [
            ("Total runs", f"{total_runs:,}"),
            ("Historical miles", f"{total_miles:,.0f} mi"),
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
    st.plotly_chart(build_monthly_mileage_chart(runs_df), use_container_width=True)
    figure_caption(
        "Monthly volume frames the project historically: sustained mileage, race-build "
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
    st.dataframe(
        summary_df[
            [
                "block_name",
                "race_date",
                "actual_time",
                "final_prediction",
                "prediction_error",
                "prediction_bias",
                "days_stable_before_race",
                "peak_weekly_mileage",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    figure_caption(
        f"Block-level metrics come from the curated marathon summary table. "
        f"The highest peak week analyzed is {peak_weekly:.1f} miles."
    )


def render_block_metrics(summary_row):
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
            ("Peak weekly mileage", f"{summary_row['peak_weekly_mileage']:.1f} mi"),
        ]
    )


def render_block_explorer(summary_df):
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

    render_block_metrics(summary_row)
    st.divider()

    (
        overview_tab,
        prediction_tab,
        training_tab,
        recovery_tab,
        physiology_tab,
        status_tab,
        data_tab,
    ) = st.tabs(
        [
            "Block Overview",
            "Prediction",
            "Training Load",
            "Recovery",
            "Physiology",
            "Status",
            "Data",
        ]
    )

    with overview_tab:
        context_columns = st.columns(4)
        context_columns[0].metric("Average weekly mileage", f"{summary_row['avg_weekly_mileage']:.1f} mi")
        context_columns[1].metric("Average training load", f"{summary_row['avg_training_load']:.0f}")
        context_columns[2].metric("Average readiness", f"{summary_row['avg_readiness']:.1f}")
        context_columns[3].metric("Average HRV", f"{summary_row['avg_hrv']:.1f}")

        left, right = st.columns(2)
        with left:
            st.plotly_chart(build_block_weekly_mileage_chart(block_df), use_container_width=True)
            figure_caption(
                "Weekly mileage shows the broad architecture of the build: progression, "
                "peak workload, recovery weeks, and taper."
            )
        with right:
            st.plotly_chart(build_block_daily_volume_chart(block_df), use_container_width=True)
            figure_caption(
                "Daily mileage adds texture underneath the weekly totals, while the "
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

    with data_tab:
        st.write("Daily block records used for the charts above.")
        st.dataframe(block_df, use_container_width=True)


def render_prediction_dynamics(summary_df):
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

    (
        findings_tab,
        timelines_tab,
        relationships_tab,
        accuracy_tab,
        table_tab,
    ) = st.tabs(
        [
            "Findings",
            "Timelines",
            "Relationships",
            "Accuracy",
            "Table",
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
                ),
                use_container_width=True,
            )
            figure_caption("ACWR captures workload balance, but the chart does not show a simple threshold effect.")
            st.plotly_chart(
                build_volatility_relationship_chart(
                    block_daily_df,
                    "total_distance_miles",
                    "Daily Mileage vs Prediction Volatility",
                    "Daily miles",
                ),
                use_container_width=True,
            )
            figure_caption("Daily mileage shows training dose, but prediction volatility still varies by block context.")

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
            st.plotly_chart(build_stability_error_chart(comparison_df), use_container_width=True)
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

    with table_tab:
        st.subheader("Block Comparison")
        st.write(
            "A compact audit table for the prediction-dynamics metrics used throughout "
            "this page."
        )
        st.dataframe(
            comparison_df.sort_values("race_date")[
                [
                    "block_name",
                    "race_date",
                    "prediction_bias",
                    "prediction_error",
                    "absolute_error",
                    "days_stable_before_race",
                    "mean_volatility",
                    "max_volatility",
                    "prediction_drift",
                    "avg_training_load",
                    "avg_readiness",
                    "avg_hrv",
                ]
            ],
            use_container_width=True,
            hide_index=True,
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


def render_running_atlas(runs_df):
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
    min_distance = float(map_df["distance_miles"].min())
    max_distance = float(map_df["distance_miles"].max())

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
            "Distance range",
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
        & map_df["distance_miles"].between(distance_range[0], distance_range[1])
    ].copy()

    if filtered_df.empty:
        st.warning("No runs match the current filters.")
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("Mapped runs", f"{len(filtered_df):,}")
    metric_columns[1].metric("Mapped miles", f"{filtered_df['distance_miles'].sum():,.0f} mi")
    metric_columns[2].metric("Longest run", f"{filtered_df['distance_miles'].max():.1f} mi")
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

    with st.expander("Mapped activity records"):
        st.write("Activity-level GPS records currently feeding the atlas.")
        st.dataframe(
            filtered_df[
                [
                    "start_time",
                    "run_name",
                    "activityType",
                    "location_label",
                    "distance_miles",
                    "avg_pace_mile",
                    "marathon_block",
                    "startLatitude",
                    "startLongitude",
                    "endLatitude",
                    "endLongitude",
                ]
            ].sort_values("start_time", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


def render_data_tables(summary_df, daily_df, runs_df):
    render_page_intro(
        "Data Tables",
        (
            "A reference area for auditing the processed datasets behind the dashboard. "
            "The main pages keep raw records out of the way; this page keeps them accessible."
        ),
        "Processed Garmin data audit",
    )

    table_choice = st.selectbox(
        "Dataset",
        ["Marathon block summary", "Daily master", "Runs", "Selected block daily"],
    )

    if table_choice == "Marathon block summary":
        st.write("Curated block-level metrics used for race summaries, cards, and comparison charts.")
        st.dataframe(summary_df, use_container_width=True)
    elif table_choice == "Daily master":
        st.write("Daily-level training and wellness records across the wider Garmin history.")
        st.dataframe(daily_df, use_container_width=True)
    elif table_choice == "Runs":
        st.write("Activity-level run records used for historical volume and the Running Atlas.")
        st.dataframe(runs_df, use_container_width=True)
    else:
        selected_block = st.selectbox("Marathon block", list(BLOCK_FILES.keys()))
        st.write("Daily records for the selected marathon block.")
        st.dataframe(load_block_data(BLOCK_FILES[selected_block]), use_container_width=True)
