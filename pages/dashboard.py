import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Dashboard | KidTrace AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "kidtrace.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

st.markdown("""
<style>
[data-testid="stSidebarNav"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🧭 KidTrace AI")
    st.caption("Elmina Lakeside Mall")
    st.divider()

    st.page_link(
        "app.py",
        label="Search",
        icon="🔍",
    )

    st.page_link(
        "pages/dashboard.py",
        label="Dashboard",
        icon="📊",
    )
# =========================================================
# 2. STYLE
# =========================================================
st.markdown("""
<style>
.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
}

/* Hide automatic navigation because we provide our own links. */
[data-testid="stSidebarNav"] {
    display: none;
}

.hero {
    background: linear-gradient(135deg, #0f2747, #0b5fa5);
    color: white;
    padding: 28px 32px;
    border-radius: 22px;
    margin-bottom: 24px;
}

.hero h1 {
    color: white;
    margin: 0;
}

.hero p {
    margin: .4rem 0 0;
}

[data-testid="stMetric"] {
    background: #f3f7fc;
    border: 1px solid #dbe4ee;
    border-radius: 16px;
    padding: 18px;
}

[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {
    color: #0f2747;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. SIDEBAR
# =========================================================
with st.sidebar:
    st.title("🧭 KidTrace AI")
    st.caption("Elmina Lakeside Mall")
    st.divider()

    st.page_link(
        "app.py",
        label="Search",
        icon="🔍",
    )

    st.page_link(
        "pages/dashboard.py",
        label="Dashboard",
        icon="📊",
    )

    st.divider()
    st.caption("Search activity and case statistics")

    if st.button(
        "🔄 Refresh Dashboard",
        use_container_width=True,
    ):
        st.rerun()


# =========================================================
# 4. DATABASE
# =========================================================
def initialise_database():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS search_cases (
                case_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_seen_location TEXT NOT NULL,
                last_seen_at TEXT,
                status TEXT NOT NULL DEFAULT 'Searching',
                latest_location TEXT,
                match_count INTEGER NOT NULL DEFAULT 0,
                reviewed_at TEXT,
                dispatched_at TEXT,
                resolved_at TEXT
            )
        """)


def load_cases():
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(
            """
            SELECT
                case_id,
                created_at,
                last_seen_location,
                last_seen_at,
                status,
                latest_location,
                match_count,
                reviewed_at,
                dispatched_at,
                resolved_at
            FROM search_cases
            ORDER BY created_at DESC
            """,
            connection,
        )


def duration_label(minutes):
    if pd.isna(minutes) or minutes < 0:
        return "—"

    if minutes < 1:
        return f"{minutes * 60:.0f} sec"

    if minutes < 60:
        return f"{minutes:.1f} min"

    if minutes < 1440:
        return f"{minutes / 60:.1f} hr"

    return f"{minutes / 1440:.1f} days"


def show_metrics(total, active, resolved, average):
    columns = st.columns(4)

    with columns[0]:
        st.metric("Total Searches", total)

    with columns[1]:
        st.metric("Active Cases", active)

    with columns[2]:
        st.metric("Resolved Cases", resolved)

    with columns[3]:
        st.metric(
            "Average Resolution Time",
            duration_label(average),
        )


# =========================================================
# 5. HEADER
# =========================================================
st.markdown("""
<div class="hero">
    <h1>📊 Search Dashboard</h1>
    <p>
        Search activity, case progress and response statistics
    </p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 6. LOAD RECORDS
# =========================================================
try:
    initialise_database()
    cases = load_cases()
except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error("Unable to read the search records.")
    st.caption(str(error))
    st.stop()

# Timestamps should be stored consistently in Malaysia local time.
for column in [
    "created_at",
    "last_seen_at",
    "reviewed_at",
    "dispatched_at",
    "resolved_at",
]:
    cases[column] = pd.to_datetime(
        cases[column],
        errors="coerce",
    )

cases["status"] = (
    cases["status"]
    .fillna("Searching")
    .astype(str)
    .str.strip()
    .replace("", "Searching")
)

cases["match_count"] = (
    pd.to_numeric(cases["match_count"], errors="coerce")
    .fillna(0)
    .clip(lower=0)
    .astype(int)
)


# =========================================================
# 7. EMPTY DASHBOARD
# =========================================================
if cases.empty:
    show_metrics(0, 0, 0, float("nan"))

    st.info(
        "No search records yet. Records will appear here "
        "after the Search page saves them to the database."
    )

    st.markdown("#### Search History")

    st.dataframe(
        pd.DataFrame(
            columns=[
                "Case ID",
                "Search Started",
                "Last-Seen Location",
                "Status",
                "Latest Location",
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.stop()


# =========================================================
# 8. FILTERS
# =========================================================
st.markdown("#### Filter Records")

date_column, status_column = st.columns(
    [1.5, 1],
    gap="large",
)

valid_dates = cases["created_at"].dropna()

with date_column:
    if not valid_dates.empty:
        selected_dates = st.date_input(
            "Search creation date",
            value=(
                valid_dates.min().date(),
                valid_dates.max().date(),
            ),
            min_value=valid_dates.min().date(),
            max_value=valid_dates.max().date(),
        )
    else:
        selected_dates = ()
        st.caption("No valid search dates are available.")

with status_column:
    statuses = sorted(
        cases["status"].unique().tolist()
    )

    selected_statuses = st.multiselect(
        "Case status",
        options=statuses,
        default=statuses,
    )

filtered = cases[
    cases["status"].isin(selected_statuses)
].copy()

if isinstance(selected_dates, (tuple, list)):
    if len(selected_dates) == 2:
        start_date, end_date = selected_dates

        filtered = filtered[
            filtered["created_at"].notna()
            & (filtered["created_at"].dt.date >= start_date)
            & (filtered["created_at"].dt.date <= end_date)
        ]

    elif len(selected_dates) == 1:
        st.caption(
            "Select an end date to apply the date filter."
        )

if filtered.empty:
    show_metrics(0, 0, 0, float("nan"))
    st.info("No records match the selected filters.")
    st.stop()

st.caption(
    "Statistics use the selected filters. "
    "Each saved search counts as one case."
)


# =========================================================
# 9. SUMMARY STATISTICS
# =========================================================
resolved_mask = (
    filtered["status"]
    .str.casefold()
    .eq("child found")
)

total_searches = len(filtered)
resolved_cases = int(resolved_mask.sum())
active_cases = total_searches - resolved_cases

resolved_records = filtered.loc[resolved_mask]

resolution_minutes = (
    resolved_records["resolved_at"]
    - resolved_records["created_at"]
).dt.total_seconds() / 60

valid_durations = resolution_minutes[
    resolution_minutes.notna()
    & (resolution_minutes >= 0)
]

average_resolution = (
    valid_durations.mean()
    if not valid_durations.empty
    else float("nan")
)

show_metrics(
    total_searches,
    active_cases,
    resolved_cases,
    average_resolution,
)

st.caption(
    "Resolution time runs from search creation to Child Found. "
    "Only completed cases with valid timestamps are included."
)


# =========================================================
# 10. CHARTS
# =========================================================
st.divider()

daily_column, progress_column = st.columns(
    [1.5, 1],
    gap="large",
)

with daily_column:
    st.markdown("#### Searches by Day")

    dated_records = filtered.dropna(
        subset=["created_at"]
    )

    if dated_records.empty:
        st.info("No valid search dates are available.")
    else:
        daily_counts = (
            dated_records
            .set_index("created_at")
            .resample("D")
            .size()
            .rename("Searches")
            .to_frame()
        )

        st.bar_chart(
            daily_counts,
            color="#0b5fa5",
            use_container_width=True,
        )

with progress_column:
    st.markdown("#### Case Status")

    status_counts = (
        filtered["status"]
        .value_counts()
        .rename_axis("Status")
        .rename("Cases")
        .to_frame()
    )

    st.bar_chart(
        status_counts,
        color="#0b5fa5",
        use_container_width=True,
    )


# =========================================================
# 11. FREQUENT LAST-SEEN LOCATIONS
# =========================================================
st.divider()
st.markdown("#### Most Reported Last-Seen Locations")

locations = (
    filtered["last_seen_location"]
    .fillna("")
    .astype(str)
    .str.strip()
)

location_counts = (
    locations[locations.ne("")]
    .value_counts()
    .head(10)
    .rename_axis("Location")
    .rename("Searches")
    .reset_index()
)

if location_counts.empty:
    st.info("No last-seen locations are recorded.")
else:
    st.dataframe(
        location_counts,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "Counts show locations entered during searches, "
    "not the overall safety of each location."
)


# =========================================================
# 12. SEARCH HISTORY
# =========================================================
st.divider()
st.markdown("#### Search History")

history = filtered.sort_values(
    "created_at",
    ascending=False,
).copy()

durations = (
    history["resolved_at"] - history["created_at"]
).dt.total_seconds() / 60

history["Resolution Time"] = [
    duration_label(minutes)
    if status.casefold() == "child found"
    else "—"
    for minutes, status in zip(
        durations,
        history["status"],
    )
]

for column in [
    "created_at",
    "last_seen_at",
    "resolved_at",
]:
    history[column] = (
        history[column]
        .dt.strftime("%d %b %Y, %I:%M %p")
        .fillna("—")
    )

history["latest_location"] = (
    history["latest_location"]
    .fillna("—")
    .replace("", "—")
)

history = history.rename(
    columns={
        "case_id": "Case ID",
        "created_at": "Search Started",
        "last_seen_at": "Reported Last-Seen Time",
        "last_seen_location": "Last-Seen Location",
        "status": "Status",
        "latest_location": "Latest Recorded Location",
        "match_count": "Candidate Matches",
        "resolved_at": "Resolved At",
    }
)

display_columns = [
    "Case ID",
    "Search Started",
    "Last-Seen Location",
    "Status",
    "Latest Recorded Location",
    "Candidate Matches",
    "Resolution Time",
]

st.dataframe(
    history[display_columns],
    use_container_width=True,
    hide_index=True,
)

export_columns = display_columns + [
    "Reported Last-Seen Time",
    "Resolved At",
]

st.download_button(
    "⬇️ Download Search History",
    data=history[export_columns]
    .to_csv(index=False)
    .encode("utf-8-sig"),
    file_name="kidtrace_search_history.csv",
    mime="text/csv",
    use_container_width=True,
)


# =========================================================
# 13. FOOTER
# =========================================================
st.divider()
st.caption(
    "Statistics are calculated from saved search records. "
    "Simulated locations remain prototype simulation data."
)