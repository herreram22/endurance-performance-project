import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.load_data import PREDICTION_COLUMN, STABILITY_RANGE_MINUTES


def _distance_settings(distance_unit="mi"):
    if distance_unit == "km":
        return 1.609344, "km", "Kilometers"
    return 1, "mi", "Miles"


def apply_chart_theme(fig, height=420):
    fig.update_layout(
        height=height,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=26, r=24, t=92, b=34),
        title=dict(y=0.98, yanchor="top", font=dict(size=18, color="#0f172a", family="Arial")),
        font=dict(color="#0f172a", size=13, family="Arial"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(148,163,184,0.35)",
            borderwidth=1,
            font=dict(size=12, color="#0f172a"),
        ),
        hoverlabel=dict(bgcolor="white", font_size=12, font_color="#0f172a"),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="#cbd5e1",
        title_font=dict(color="#0f172a", size=13),
        tickfont=dict(color="#334155", size=12),
    )
    fig.update_yaxes(
        gridcolor="rgba(148,163,184,0.24)",
        zeroline=False,
        linecolor="#cbd5e1",
        title_font=dict(color="#0f172a", size=13),
        tickfont=dict(color="#334155", size=12),
    )
    return fig


def build_monthly_mileage_chart(runs_df, distance_unit="mi"):
    multiplier, unit_abbrev, unit_label = _distance_settings(distance_unit)
    monthly_distance = (
        runs_df.dropna(subset=["start_time"])
        .set_index("start_time")["distance_miles"]
        .resample("ME")
        .sum()
        .reset_index()
    )
    monthly_distance["distance_display"] = monthly_distance["distance_miles"] * multiplier

    fig = px.area(
        monthly_distance,
        x="start_time",
        y="distance_display",
        title="Historical Running Volume",
        labels={"start_time": "Month", "distance_display": unit_label},
    )
    fig.update_traces(
        line_color="#2E7D32",
        fillcolor="rgba(46, 125, 50, 0.18)",
        hovertemplate=f"%{{x|%b %Y}}<br>%{{y:.1f}} {unit_abbrev}<extra></extra>",
    )
    return apply_chart_theme(fig, height=360)


def build_global_timeline_chart(daily_df, summary_df, distance_unit="mi"):
    chart_df = daily_df.dropna(subset=["date"]).copy().sort_values("date")
    chart_df = chart_df[chart_df["date"].ge(pd.Timestamp("2021-01-01"))].copy()
    _, unit_abbrev, _ = _distance_settings(distance_unit)
    distance_column = "total_distance_miles"
    distance_label = "Weekly mileage"
    if distance_unit == "km":
        chart_df["total_distance_km_display"] = chart_df["total_distance_miles"] * 1.609344
        distance_column = "total_distance_km_display"
        distance_label = "Weekly kilometers"

    weekly_mileage = (
        chart_df.set_index("date")[distance_column]
        .resample("W-SUN")
        .sum()
        .rename("weekly_distance")
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=weekly_mileage["date"],
            y=weekly_mileage["weekly_distance"],
            name=distance_label,
            marker_color="rgba(37, 99, 235, 0.30)",
            hovertemplate=f"%{{x|%b %d, %Y}}<br>%{{y:.1f}} {unit_abbrev}<extra></extra>",
        )
    )

    if "vo2MaxValue" in chart_df:
        fig.add_trace(
            go.Scatter(
                x=chart_df["date"],
                y=chart_df["vo2MaxValue"],
                name="VO2 max",
                yaxis="y2",
                mode="lines",
                line=dict(color="#16A34A", width=3),
                connectgaps=True,
                hovertemplate="%{x|%b %d, %Y}<br>VO2 max %{y:.1f}<extra></extra>",
            )
        )

    if "Marathon_pred" in chart_df:
        prediction_df = chart_df.dropna(subset=["Marathon_pred"]).copy()
        fig.add_trace(
            go.Scatter(
                x=prediction_df["date"],
                y=prediction_df["Marathon_pred"],
                name="Marathon prediction",
                yaxis="y3",
                mode="lines",
                line=dict(color="#F97316", width=3),
                connectgaps=True,
                hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f} min<extra></extra>",
            )
        )

    for _, row in summary_df.dropna(subset=["race_date"]).iterrows():
        fig.add_vline(
            x=row["race_date"],
            line_width=1.5,
            line_dash="dot",
            line_color="#64748b",
        )
        fig.add_annotation(
            x=row["race_date"],
            y=1.03,
            xref="x",
            yref="paper",
            text=row["block_name"].replace(" Marathon", ""),
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            textangle=0,
            font=dict(size=11, color="#0f172a"),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(148,163,184,0.55)",
            borderpad=3,
            xshift=4,
            yshift=4,
        )

    fig.update_layout(
        title="Training Timeline",
        xaxis_title="Date",
        yaxis=dict(title=f"Weekly distance ({unit_abbrev})", rangemode="tozero"),
        yaxis2=dict(title="VO2 max", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(
            title="Prediction",
            overlaying="y",
            side="right",
            anchor="free",
            position=0.94,
            showgrid=False,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="left", x=0),
    )
    fig.update_xaxes(range=[pd.Timestamp("2021-01-01"), chart_df["date"].max()])
    return apply_chart_theme(fig, height=560)


def build_personal_best_chart(pb_df):
    if pb_df.empty:
        return apply_chart_theme(go.Figure(), height=360)

    chart_df = pb_df.sort_values("event_date").copy()
    fig = px.scatter(
        chart_df,
        x="event_date",
        y="official_time_min",
        size="distance_value",
        color="race_type_label",
        hover_name="label",
        title="Official Race Results",
        labels={
            "event_date": "Date",
            "official_time_min": "Official time (min)",
            "race_type_label": "Race type",
        },
        hover_data={
            "official_time_label": True,
            "pace_label": True,
            "distance_display": True,
            "matched_run_name": True,
        },
        color_discrete_sequence=["#2563EB", "#16A34A", "#F97316", "#7C3AED", "#64748B"],
    )
    fig.update_traces(marker=dict(opacity=0.82, line=dict(width=1, color="white")))
    return apply_chart_theme(fig, height=390)


def build_prediction_chart(prediction_df, final_prediction, stable_date):
    lower_bound = final_prediction - STABILITY_RANGE_MINUTES
    upper_bound = final_prediction + STABILITY_RANGE_MINUTES

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pd.concat([prediction_df["date"], prediction_df["date"].iloc[::-1]]),
            y=pd.concat(
                [
                    pd.Series(upper_bound, index=prediction_df.index),
                    pd.Series(lower_bound, index=prediction_df.index).iloc[::-1],
                ]
            ),
            fill="toself",
            fillcolor="rgba(30, 136, 229, 0.16)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="+/- 2 min stability range",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=prediction_df["date"],
            y=prediction_df[PREDICTION_COLUMN],
            mode="lines+markers",
            name="Garmin marathon prediction",
            line=dict(color="#1E88E5", width=3),
            marker=dict(size=6),
            hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f} min<extra></extra>",
        )
    )
    fig.add_hline(
        y=final_prediction,
        line_dash="dash",
        line_color="#78909C",
        annotation_text="Final prediction",
        annotation_position="top left",
    )

    if pd.notna(stable_date):
        fig.add_shape(
            type="line",
            x0=stable_date,
            x1=stable_date,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line=dict(color="#EF6C00", dash="dot", width=2),
        )
        fig.add_annotation(
            x=stable_date,
            y=1,
            xref="x",
            yref="paper",
            text="Stable date",
            showarrow=False,
            yanchor="bottom",
            font=dict(color="#EF6C00"),
        )

    fig.update_layout(
        title="Garmin Marathon Prediction Over Time",
        xaxis_title="Date",
        yaxis_title="Predicted marathon time (minutes)",
        hovermode="x unified",
    )
    return apply_chart_theme(fig, height=460)


def build_accuracy_stability_chart(summary_df, distance_unit="mi"):
    multiplier, unit_abbrev, _ = _distance_settings(distance_unit)
    chart_df = summary_df.copy()
    chart_df["absolute_error"] = chart_df["prediction_error"].abs()
    chart_df["peak_weekly_distance"] = chart_df["peak_weekly_mileage"] * multiplier

    fig = px.scatter(
        chart_df,
        x="days_stable_before_race",
        y="absolute_error",
        size="peak_weekly_distance",
        color="prediction_bias",
        hover_name="block_name",
        title="Accuracy vs. Stability",
        labels={
            "days_stable_before_race": "Days stable before race",
            "absolute_error": "Absolute prediction error (min)",
            "prediction_bias": "Bias",
            "peak_weekly_distance": f"Peak weekly distance ({unit_abbrev})",
        },
        color_discrete_map={
            "optimistic": "#EF6C00",
            "conservative": "#1E88E5",
            "neutral": "#2E7D32",
        },
    )
    return apply_chart_theme(fig, height=430)


def build_volatility_by_block_chart(summary_df):
    chart_df = summary_df.sort_values("mean_volatility").copy()

    fig = px.bar(
        chart_df,
        x="mean_volatility",
        y="block_name",
        orientation="h",
        color="prediction_bias",
        title="Prediction Volatility",
        labels={
            "mean_volatility": "Mean rolling volatility (min)",
            "block_name": "",
            "prediction_bias": "Final bias",
        },
        color_discrete_map={
            "optimistic": "#EF6C00",
            "conservative": "#1E88E5",
            "neutral": "#2E7D32",
        },
        hover_data={
            "max_volatility": ":.2f",
            "days_stable_before_race": True,
            "prediction_error": ":.1f",
        },
    )
    return apply_chart_theme(fig, height=330)


def build_stabilization_timeline_chart(summary_df):
    chart_df = summary_df.sort_values("race_date").copy()

    fig = go.Figure()
    for _, row in chart_df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["stable_date"], row["race_date"]],
                y=[row["block_name"], row["block_name"]],
                mode="lines+markers",
                line=dict(color="#78909C", width=3),
                marker=dict(size=[9, 11], color=["#1E88E5", "#EF6C00"]),
                name=row["block_name"],
                showlegend=False,
                hovertemplate="%{y}<br>%{x|%b %d, %Y}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Prediction Stabilization Window",
        xaxis_title="Date",
        yaxis_title="",
    )
    return apply_chart_theme(fig, height=330)


def build_prediction_error_chart(summary_df):
    chart_df = summary_df.sort_values("race_date").copy()
    fig = px.bar(
        chart_df,
        x="block_name",
        y="prediction_error",
        color="prediction_bias",
        title="Final Prediction Error",
        labels={
            "block_name": "",
            "prediction_error": "Prediction error (min)",
            "prediction_bias": "Bias",
        },
        color_discrete_map={
            "optimistic": "#EF6C00",
            "conservative": "#1E88E5",
            "neutral": "#2E7D32",
        },
        hover_data={
            "actual_time": ":.1f",
            "final_prediction": ":.1f",
            "days_stable_before_race": True,
        },
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#78909C")
    return apply_chart_theme(fig, height=360)


def build_prediction_drift_chart(summary_df):
    chart_df = summary_df.sort_values("race_date").copy()
    fig = px.bar(
        chart_df,
        x="block_name",
        y="prediction_drift",
        color="prediction_bias",
        title="Prediction Drift",
        labels={
            "block_name": "",
            "prediction_drift": "Prediction drift (min)",
            "prediction_bias": "Bias",
        },
        color_discrete_map={
            "optimistic": "#EF6C00",
            "conservative": "#1E88E5",
            "neutral": "#2E7D32",
        },
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#78909C")
    return apply_chart_theme(fig, height=360)


def build_volatility_timeline_chart(block_daily_df, volatility_column):
    chart_df = block_daily_df.dropna(subset=[volatility_column]).copy()
    fig = px.line(
        chart_df,
        x="days_from_start",
        y=volatility_column,
        color="block_name",
        title="Rolling Marathon Prediction Volatility Through Each Block",
        labels={
            "days_from_start": "Days from block start",
            volatility_column: "Rolling volatility (min)",
            "block_name": "Block",
        },
        hover_data={"date": "|%b %d, %Y"},
    )
    fig.update_traces(line_width=3)
    return apply_chart_theme(fig, height=430)


def build_prediction_timeline_by_block_chart(block_daily_df):
    chart_df = block_daily_df.dropna(subset=[PREDICTION_COLUMN]).copy()
    fig = px.line(
        chart_df,
        x="days_from_start",
        y=PREDICTION_COLUMN,
        color="block_name",
        title="Prediction Curves by Block",
        labels={
            "days_from_start": "Days from block start",
            PREDICTION_COLUMN: "Predicted marathon time (min)",
            "block_name": "Block",
        },
        hover_data={"date": "|%b %d, %Y"},
    )
    fig.update_traces(line_width=3)
    return apply_chart_theme(fig, height=430)


def build_volatility_relationship_chart(block_daily_df, x_column, title, x_label, distance_unit="mi"):
    multiplier, unit_abbrev, _ = _distance_settings(distance_unit)
    chart_df = block_daily_df.copy()
    hover_data = {
        "date": "|%b %d, %Y",
        "Marathon_pred_x": ":.1f",
    }

    if x_column == "total_distance_miles":
        chart_df["distance_display"] = chart_df["total_distance_miles"] * multiplier
        x_column = "distance_display"
        x_label = f"Daily distance ({unit_abbrev})"
        hover_data["distance_display"] = ":.1f"

    chart_df = chart_df.dropna(subset=[x_column, "rolling_std_15_Marathond_x"])
    fig = px.scatter(
        chart_df,
        x=x_column,
        y="rolling_std_15_Marathond_x",
        color="block_name",
        title=title,
        labels={
            x_column: x_label,
            "rolling_std_15_Marathond_x": "15-day prediction volatility (min)",
            "block_name": "Block",
        },
        hover_data=hover_data,
    )
    fig.update_traces(marker=dict(size=8, opacity=0.72))
    return apply_chart_theme(fig, height=390)


def build_stability_error_chart(summary_df, distance_unit="mi"):
    multiplier, unit_abbrev, _ = _distance_settings(distance_unit)
    chart_df = summary_df.copy()
    chart_df["absolute_error"] = chart_df["prediction_error"].abs()
    chart_df["peak_weekly_distance"] = chart_df["peak_weekly_mileage"] * multiplier
    fig = px.scatter(
        chart_df,
        x="days_stable_before_race",
        y="absolute_error",
        size="peak_weekly_distance",
        color="prediction_bias",
        hover_name="block_name",
        title="Stabilization Timing vs Final Error",
        labels={
            "days_stable_before_race": "Days stable before race",
            "absolute_error": "Absolute final error (min)",
            "prediction_bias": "Bias",
            "peak_weekly_distance": f"Peak weekly distance ({unit_abbrev})",
        },
        color_discrete_map={
            "optimistic": "#EF6C00",
            "conservative": "#1E88E5",
            "neutral": "#2E7D32",
        },
    )
    return apply_chart_theme(fig, height=390)


def build_block_weekly_mileage_chart(block_df, distance_unit="mi"):
    multiplier, unit_abbrev, unit_label = _distance_settings(distance_unit)
    weekly_df = (
        block_df.set_index("date")["total_distance_miles"]
        .resample("W-SUN")
        .sum()
        .reset_index()
    )
    weekly_df["distance_display"] = weekly_df["total_distance_miles"] * multiplier

    fig = px.bar(
        weekly_df,
        x="date",
        y="distance_display",
        title="Weekly Distance",
        labels={"date": "Week ending", "distance_display": unit_label},
    )
    fig.update_traces(
        marker_color="#2E7D32",
        hovertemplate=f"%{{x|%b %d}}<br>%{{y:.1f}} {unit_abbrev}<extra></extra>",
    )
    return apply_chart_theme(fig, height=360)


def build_block_daily_volume_chart(block_df, distance_unit="mi"):
    multiplier, unit_abbrev, unit_label = _distance_settings(distance_unit)
    distance = block_df["total_distance_miles"] * multiplier
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=block_df["date"],
            y=distance,
            name=f"Daily {unit_abbrev}",
            marker_color="#90CAF9",
            opacity=0.85,
            hovertemplate=f"%{{x|%b %d}}<br>%{{y:.1f}} {unit_abbrev}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=block_df["date"],
            y=distance.rolling(7, min_periods=1).mean(),
            name="7-day average",
            line=dict(color="#EF6C00", width=3),
            hovertemplate=f"%{{x|%b %d}}<br>%{{y:.1f}} {unit_abbrev}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Daily Distance and 7-Day Trend",
        xaxis_title="Date",
        yaxis_title=unit_label,
        hovermode="x unified",
    )
    return apply_chart_theme(fig, height=360)


def build_block_training_load_chart(block_df):
    fig = go.Figure()
    if "dailyTrainingLoadAcute" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["dailyTrainingLoadAcute"],
                name="Acute load",
                line=dict(color="#1E88E5", width=3),
            )
        )
    if "dailyTrainingLoadChronic" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["dailyTrainingLoadChronic"],
                name="Chronic load",
                line=dict(color="#2E7D32", width=3),
            )
        )
    if "dailyAcuteChronicWorkloadRatio" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["dailyAcuteChronicWorkloadRatio"],
                name="ACWR",
                yaxis="y2",
                line=dict(color="#EF6C00", width=2, dash="dot"),
            )
        )

    fig.update_layout(
        title="Training Load and Acute:Chronic Ratio",
        xaxis_title="Date",
        yaxis_title="Training load",
        yaxis2=dict(title="ACWR", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
    )
    return apply_chart_theme(fig, height=390)


def build_block_readiness_chart(block_df):
    fig = go.Figure()
    if "readiness_score_mean" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["readiness_score_mean"],
                name="Readiness",
                line=dict(color="#2E7D32", width=3),
                connectgaps=True,
            )
        )
    if "sleep_score_last" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["sleep_score_last"],
                name="Sleep score",
                line=dict(color="#1E88E5", width=2),
                connectgaps=True,
            )
        )
    if "recovery_time_last" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["recovery_time_last"] / 60,
                name="Recovery time (hours)",
                yaxis="y2",
                line=dict(color="#EF6C00", width=2, dash="dot"),
                connectgaps=True,
            )
        )

    fig.update_layout(
        title="Readiness, Sleep, and Recovery",
        xaxis_title="Date",
        yaxis_title="Score",
        yaxis2=dict(title="Recovery hours", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
    )
    return apply_chart_theme(fig, height=390)


def build_block_physiology_chart(block_df):
    fig = go.Figure()
    if "vo2MaxValue" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["vo2MaxValue"],
                name="VO2 max",
                line=dict(color="#1E88E5", width=3),
                connectgaps=True,
            )
        )
    hrv_col = "hrv_weekly_avg_clean" if "hrv_weekly_avg_clean" in block_df else "hrv_weekly_avg_last"
    if hrv_col in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df[hrv_col],
                name="HRV weekly avg",
                yaxis="y2",
                line=dict(color="#2E7D32", width=3),
                connectgaps=True,
            )
        )
    if "avg_hr" in block_df:
        fig.add_trace(
            go.Scatter(
                x=block_df["date"],
                y=block_df["avg_hr"],
                name="Avg run HR",
                yaxis="y3",
                line=dict(color="#EF6C00", width=2, dash="dot"),
                connectgaps=True,
            )
        )

    fig.update_layout(
        title="Physiology Signals",
        xaxis_title="Date",
        yaxis=dict(title="VO2 max"),
        yaxis2=dict(title="HRV", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(
            title="Avg HR",
            overlaying="y",
            side="right",
            anchor="free",
            position=0.96,
            showgrid=False,
        ),
        hovermode="x unified",
    )
    return apply_chart_theme(fig, height=390)


def build_block_status_chart(block_df, column_name, title):
    status_df = (
        block_df[column_name]
        .dropna()
        .value_counts()
        .rename_axis(column_name)
        .reset_index(name="days")
    )
    fig = px.bar(
        status_df,
        x="days",
        y=column_name,
        orientation="h",
        title=title,
        labels={"days": "Days", column_name: ""},
    )
    fig.update_traces(marker_color="#78909C")
    return apply_chart_theme(fig, height=320)
