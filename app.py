from __future__ import annotations

import html
import json
import re
import csv
import io
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
)

from database import (
    initialise_database,
    create_case,
    review_case,
    dispatch_case,
    resolve_case,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "cctv_metadata.csv"
MAP_PATH = DATA_DIR / "floor_plan" / "floor plan elmina.png"

DIRECTORY_URL = (
    "https://www.simedarbyproperty.com/"
    "malls/elmina-lake-side-mall/"
)

DEMO_STOP_COUNT = 4
DEMO_MINUTE_GAP = 4

app = Flask(__name__)
app.secret_key = "kidtrace-hackathon-demo-secret-change-me"

initialise_database()

# In-memory active-case state for the hackathon demo.
# A production system should use server-side sessions / database tables.
ACTIVE = {}


def safe_number(value, default):
    try:
        number = float(value)
        return number if pd.notna(number) else default
    except (ValueError, TypeError):
        return default


def format_time(value):
    text = str(value).strip()
    for pattern in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(text, pattern).strftime("%H:%M")
        except ValueError:
            continue
    return text


def video_path(value):
    relative = str(value).strip().replace("\\", "/")
    if relative.startswith("data/"):
        return ROOT / relative
    if relative.startswith("cctv_videos/"):
        return DATA_DIR / relative
    return DATA_DIR / "cctv_videos" / relative


_PLACES_CACHE = None


def load_directory():
    global _PLACES_CACHE
    if _PLACES_CACHE is not None:
        return _PLACES_CACHE

    request_obj = Request(
        DIRECTORY_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request_obj, timeout=30) as response:
        page = response.read().decode("utf-8")

    bounds_match = re.search(
        r"var bounds\s*=\s*(\[\[.*?\]\]);",
        page,
        flags=re.DOTALL,
    )
    if not bounds_match:
        raise ValueError("Official map bounds were not found.")

    bounds = json.loads(bounds_match.group(1))
    south, west = bounds[0]
    north, east = bounds[1]

    pattern = (
        r'\{\s*id:\s*(\d+),\s*coords:\s*'
        r'(\[\s*\[[^\[\]]*\](?:\s*,\s*\[[^\[\]]*\])*\s*\])'
        r',\s*popupContent:\s*(["\x27])(.*?)\3\s*\}'
    )

    records = re.findall(pattern, page, flags=re.DOTALL)
    if not records:
        raise ValueError("Clickable areas were not found.")

    places = {}
    seen = set()

    overrides = {
        "93": ("Children's Playground", "Near GK-08"),
        "98": ("Information Counter", "Near Water Feature"),
        "96": ("Central Drop-off", "Near GF-18 & 19"),
        "110": ("Water Feature", "Near Information Counter"),
    }

    for official_id, raw_coordinates, quote, popup in records:
        coordinates = json.loads(raw_coordinates)
        if len(coordinates) < 3:
            continue

        text = re.sub(r"<[^>]+>", "|", popup)
        parts = [
            html.unescape(part).strip()
            for part in text.split("|")
            if part.strip()
        ]
        if not parts:
            continue

        is_shop = bool(
            re.match(
                r"^(GF|GK|DT|P)-",
                parts[0],
                flags=re.IGNORECASE,
            )
        )

        if is_shop:
            unit = parts[0]
            name = " ".join(parts[1:]).strip()
        else:
            name = " ".join(parts).strip()
            unit = f"Facility point {official_id}"

        if not name or name.lower() == "name":
            continue

        name = name.replace("Walkaway", "Walkway")
        if official_id in overrides:
            name, unit = overrides[official_id]

        polygon = [
            [
                (longitude - west) / (east - west),
                1 - (latitude - south) / (north - south),
            ]
            for latitude, longitude in coordinates
        ]

        centre_x = sum(p[0] for p in polygon) / len(polygon)
        centre_y = sum(p[1] for p in polygon) / len(polygon)

        signature = (
            name.lower(),
            unit.lower(),
            round(centre_x, 3),
            round(centre_y, 3),
        )
        if signature in seen:
            continue
        seen.add(signature)

        place_id = f"official_{official_id}"
        if place_id in places:
            place_id = f"{place_id}_{len(places)}"

        places[place_id] = {
            "name": name,
            "unit": unit,
            "polygon": polygon,
        }

    extras = [
        (
            "operations",
            "Integrated Operations Office",
            "West Block",
            [[0.091, 0.322], [0.159, 0.322], [0.159, 0.438], [0.091, 0.438]],
        ),
        (
            "sales_gallery",
            "Sales Gallery",
            "West Block",
            [[0.117, 0.548], [0.178, 0.548], [0.178, 0.696], [0.117, 0.696]],
        ),
        (
            "promo_central",
            "Promotion Space",
            "Near GK-01",
            [[0.632, 0.368], [0.647, 0.386], [0.647, 0.414], [0.632, 0.414]],
        ),
        (
            "promo_south",
            "Promotion Space",
            "Near Children's Playground",
            [[0.585, 0.610], [0.624, 0.599], [0.624, 0.657], [0.585, 0.670]],
        ),
    ]
    for place_id, name, unit, polygon in extras:
        places[place_id] = {
            "name": name,
            "unit": unit,
            "polygon": polygon,
        }

    _PLACES_CACHE = places
    return places


def label_for(place):
    return f"{place['name']} — {place['unit']}"


def resolve_csv_place(value, places):
    text = str(value).strip().lower()

    exact = [
        place_id
        for place_id, place in places.items()
        if text in {
            label_for(place).lower(),
            place["name"].lower(),
            place["unit"].lower(),
        }
    ]
    if len(exact) == 1:
        return exact[0]

    names = [
        place_id
        for place_id, place in places.items()
        if place["name"].lower() in text
    ]
    if len(names) == 1:
        return names[0]

    legacy = {
        "playground": "official_93",
        "escalator": "official_98",
        "food court": "official_23",
        "main entrance": "official_96",
        "east wing": "official_30",
        "east corridor": "official_30",
    }
    for keyword, place_id in legacy.items():
        if keyword in text and place_id in places:
            return place_id
    return None


def point_inside(x, y, polygon):
    inside = False
    previous = len(polygon) - 1
    for current in range(len(polygon)):
        xi, yi = polygon[current]
        xj, yj = polygon[previous]

        if (yi > y) != (yj > y):
            crossing = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def polygon_area(polygon):
    return abs(
        sum(
            polygon[i][0] * polygon[(i + 1) % len(polygon)][1]
            - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
            for i in range(len(polygon))
        )
    ) / 2


def reference_point(polygon):
    return [
        sum(p[0] for p in polygon) / len(polygon),
        sum(p[1] for p in polygon) / len(polygon),
    ]


def location_point(location, places):
    if not location:
        return None
    if location.get("point") is not None:
        return list(location["point"])
    place_id = location.get("place_id")
    if place_id in places:
        return reference_point(places[place_id]["polygon"])
    return None


def build_demo_trail(record, context, places):
    start = deepcopy(context["start"])
    destination_id = record.get("place_id")
    if destination_id not in places:
        raise ValueError("This candidate has no mapped destination.")

    destination = {
        "place_id": destination_id,
        "label": label_for(places[destination_id]),
        "point": None,
    }

    start_point = location_point(start, places)
    destination_point = location_point(destination, places)
    if start_point is None or destination_point is None:
        raise ValueError("Timeline endpoints could not be mapped.")

    count = max(2, min(int(DEMO_STOP_COUNT), 5))
    middle_count = count - 2

    excluded = {start.get("place_id"), destination_id}
    pool = [
        place_id
        for place_id, place in places.items()
        if place_id not in excluded
        and re.match(r"^(GF|GK|DT)-", place["unit"])
    ]

    used_units = {
        places[place_id]["unit"]
        for place_id in excluded
        if place_id in places
    }

    middle = []
    for index in range(middle_count):
        fraction = (index + 1) / (middle_count + 1)
        target = [
            start_point[0] + (destination_point[0] - start_point[0]) * fraction,
            start_point[1] + (destination_point[1] - start_point[1]) * fraction,
        ]

        available = [
            place_id
            for place_id in pool
            if places[place_id]["unit"] not in used_units
        ]
        if not available:
            break

        chosen = min(
            available,
            key=lambda place_id: sum(
                (a - b) ** 2
                for a, b in zip(reference_point(places[place_id]["polygon"]), target)
            ),
        )

        middle.append({
            "place_id": chosen,
            "label": label_for(places[chosen]),
            "point": None,
        })
        used_units.add(places[chosen]["unit"])
        pool.remove(chosen)

    stops = [start] + middle + [destination]
    start_datetime = datetime.fromisoformat(context["start_datetime"])

    trail = []
    for index, stop in enumerate(stops):
        point = location_point(stop, places)
        trail.append({
            "number": index + 1,
            "timestamp": (
                start_datetime
                + timedelta(minutes=index * DEMO_MINUTE_GAP)
            ).isoformat(),
            "location": stop["label"],
            "place_id": stop.get("place_id"),
            "point": point,
            "camera": (
                "Last seen"
                if index == 0
                else (
                    record.get("camera_id", f"DEMO-C{index:02d}")
                    if index == len(stops) - 1
                    else f"DEMO-C{index:02d}"
                )
            ),
        })
    return trail


def require_auth():
    return session.get("staff_id") == "SEC001"


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/login")
def api_login():
    payload = request.get_json(force=True)
    staff_id = str(payload.get("staff_id", "")).strip().upper()
    password = str(payload.get("password", ""))

    if staff_id == "SEC001" and password == "kidtrace123":
        session["staff_id"] = staff_id
        return jsonify({"ok": True, "staff_id": staff_id})
    return jsonify({"ok": False, "message": "Invalid Staff ID or password."}), 401


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/places")
def api_places():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    try:
        places = load_directory()
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

    return jsonify({
        "ok": True,
        "places": [
            {
                "id": place_id,
                "name": place["name"],
                "unit": place["unit"],
                "label": label_for(place),
                "polygon": place["polygon"],
            }
            for place_id, place in places.items()
        ],
    })


@app.get("/api/floor-plan")
def api_floor_plan():
    if not MAP_PATH.is_file():
        return "Floor plan missing", 404
    return send_file(MAP_PATH)


@app.get("/media/<path:relative>")
def media(relative):
    path = DATA_DIR / relative
    try:
        resolved = path.resolve()
        resolved.relative_to(DATA_DIR.resolve())
    except Exception:
        return "Invalid path", 400

    if not resolved.is_file():
        return "Not found", 404
    return send_file(resolved)


@app.post("/api/search")
def api_search():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    if not CSV_PATH.is_file():
        return jsonify({
            "ok": False,
            "message": "data/cctv_metadata.csv is missing.",
        }), 400

    places = load_directory()
    payload = request.form

    top = payload.get("top", "").strip()
    bottom = payload.get("bottom", "").strip()
    height = safe_number(payload.get("height"), 115)
    last_date = payload.get("last_date", "").strip()
    last_time = payload.get("last_time", "").strip()
    place_id = payload.get("place_id", "").strip()
    custom_label = payload.get("custom_label", "").strip()
    custom_x = payload.get("custom_x", "").strip()
    custom_y = payload.get("custom_y", "").strip()

    if place_id and place_id in places:
        selected = {
            "place_id": place_id,
            "label": label_for(places[place_id]),
            "point": None,
        }
    elif custom_label and custom_x and custom_y:
        selected = {
            "place_id": None,
            "label": custom_label,
            "point": [float(custom_x), float(custom_y)],
        }
    else:
        return jsonify({
            "ok": False,
            "message": "Please choose the last-seen location.",
        }), 400

    try:
        last_seen_dt = datetime.fromisoformat(f"{last_date}T{last_time}")
    except ValueError:
        return jsonify({
            "ok": False,
            "message": "Please enter a valid last-seen date and time.",
        }), 400

    df = pd.read_csv(CSV_PATH)
    if df.empty:
        return jsonify({"ok": False, "message": "The CCTV metadata file is empty."}), 400

    missing = {"location", "video_path"} - set(df.columns)
    if missing:
        return jsonify({
            "ok": False,
            "message": "Missing CSV columns: " + ", ".join(sorted(missing)),
        }), 400

    df["original_location"] = df["location"]
    df["place_id"] = df["location"].apply(
        lambda value: resolve_csv_place(value, places)
    )
    df["location"] = df.apply(
        lambda row: (
            label_for(places[row["place_id"]])
            if row["place_id"] in places
            else str(row["original_location"])
        ),
        axis=1,
    )

    def score_record(row):
        visual = max(
            0.0,
            min(safe_number(row.get("base_similarity"), 0.5), 1.0),
        ) * 0.55

        top_score = (
            0.18
            if top
            and str(row.get("top", "")).strip().lower() == top.lower()
            else 0.0
        )
        bottom_score = (
            0.12
            if bottom
            and str(row.get("bottom", "")).strip().lower() == bottom.lower()
            else 0.0
        )

        difference = abs(
            safe_number(row.get("height_cm"), 115) - height
        )
        height_score = max(
            0.0,
            0.10 * (1 - difference / 20),
        )

        if selected["place_id"] is not None:
            matches_location = row["place_id"] == selected["place_id"]
        else:
            matches_location = (
                str(row["original_location"]).strip().lower()
                == selected["label"].lower()
            )

        location_score = 0.05 if matches_location else 0.0

        return pd.Series({
            "score_visual": visual,
            "score_top": top_score,
            "score_bottom": bottom_score,
            "score_height": height_score,
            "score_loc": location_score,
            "final_score": min(
                visual + top_score + bottom_score
                + height_score + location_score,
                0.99,
            ),
        })

    scores = df.apply(score_record, axis=1)
    df = pd.concat(
        [
            df.drop(columns=list(scores.columns), errors="ignore"),
            scores,
        ],
        axis=1,
    )

    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    context = {
        "start": deepcopy(selected),
        "start_datetime": last_seen_dt.isoformat(),
    }

    case_id = create_case(
        last_seen_location=selected["label"],
        last_seen_at=context["start_datetime"],
        match_count=min(len(df), 3),
    )

    records = []
    for index, row in df.head(3).iterrows():
        record = row.to_dict()
        record["_row_index"] = int(index)

        vpath = video_path(record.get("video_path", ""))
        try:
            rel = vpath.resolve().relative_to(DATA_DIR.resolve()).as_posix()
        except Exception:
            rel = ""

        records.append({
            "index": int(index),
            "match_number": int(index) + 1,
            "score": round(float(record["final_score"]) * 100),
            "camera_id": str(record.get("camera_id", "N/A")),
            "location": str(record.get("location", "N/A")),
            "time": format_time(record.get("time", "N/A")),
            "video_url": f"/media/{rel}" if rel else "",
            "mapped": bool(record.get("place_id") in places),
            "breakdown": {
                "visual": round(float(record["score_visual"]) * 100),
                "top": round(float(record["score_top"]) * 100),
                "bottom": round(float(record["score_bottom"]) * 100),
                "height": round(float(record["score_height"]) * 100),
                "location": round(float(record["score_loc"]) * 100),
            },
        })

    ACTIVE[case_id] = {
        "context": context,
        "records": df.head(3).to_dict(orient="records"),
        "trail": None,
        "dispatched": False,
        "found": False,
    }

    return jsonify({
        "ok": True,
        "case_id": case_id,
        "selected_location": selected["label"],
        "matches": records,
    })


@app.post("/api/verify")
def api_verify():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    payload = request.get_json(force=True)
    case_id = payload.get("case_id")
    index = int(payload.get("index", -1))

    state = ACTIVE.get(case_id)
    if not state or index < 0 or index >= len(state["records"]):
        return jsonify({"ok": False, "message": "Invalid case or candidate."}), 400

    places = load_directory()
    record = state["records"][index]

    try:
        trail = build_demo_trail(
            record,
            state["context"],
            places,
        )
        review_case(
            case_id,
            latest_location="[SIMULATED] " + trail[-1]["location"],
        )
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    state["trail"] = trail
    state["verified_index"] = index

    return jsonify({
        "ok": True,
        "trail": [
            {
                **stop,
                "display_time": datetime.fromisoformat(
                    stop["timestamp"]
                ).strftime("%H:%M"),
            }
            for stop in trail
        ],
        "latest": trail[-1],
    })


@app.post("/api/dispatch")
def api_dispatch():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    payload = request.get_json(force=True)
    case_id = payload.get("case_id")
    state = ACTIVE.get(case_id)

    if not state or not state.get("trail"):
        return jsonify({"ok": False, "message": "Verify a match first."}), 400

    dispatch_case(case_id)
    state["dispatched"] = True

    return jsonify({
        "ok": True,
        "latest": state["trail"][-1]["location"],
    })


@app.post("/api/resolve")
def api_resolve():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    payload = request.get_json(force=True)
    case_id = payload.get("case_id")
    state = ACTIVE.get(case_id)

    if not state or not state.get("trail"):
        return jsonify({"ok": False, "message": "Verify a match first."}), 400

    resolve_case(case_id)
    state["found"] = True
    return jsonify({"ok": True})



@app.get("/api/dashboard")
def api_dashboard():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    statuses = [
        value.strip()
        for value in request.args.get("status", "").split(",")
        if value.strip()
    ]

    clauses = []
    params = []

    if start:
        clauses.append("date(created_at) >= date(?)")
        params.append(start)
    if end:
        clauses.append("date(created_at) <= date(?)")
        params.append(end)
    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with sqlite3.connect(DATA_DIR / "kidtrace.db") as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            f"""
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
            {where}
            ORDER BY datetime(created_at) DESC
            """,
            params,
        ).fetchall()

    records = [dict(row) for row in rows]

    def resolution_seconds(record):
        if not record.get("resolved_at"):
            return None
        try:
            started = datetime.fromisoformat(record["created_at"])
            resolved = datetime.fromisoformat(record["resolved_at"])
            return max(0, int((resolved - started).total_seconds()))
        except Exception:
            return None

    for record in records:
        record["resolution_seconds"] = resolution_seconds(record)

    total = len(records)
    resolved = sum(1 for r in records if r["status"] == "Child Found")
    active = total - resolved
    resolution_values = [
        r["resolution_seconds"]
        for r in records
        if r["resolution_seconds"] is not None
    ]
    average_resolution = (
        round(sum(resolution_values) / len(resolution_values))
        if resolution_values
        else None
    )

    by_day = {}
    by_status = {}
    by_location = {}

    for record in records:
        day = str(record["created_at"])[:10]
        by_day[day] = by_day.get(day, 0) + 1
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
        location = record["last_seen_location"] or "Unknown"
        by_location[location] = by_location.get(location, 0) + 1

    top_locations = sorted(
        [{"location": key, "count": value} for key, value in by_location.items()],
        key=lambda item: (-item["count"], item["location"].lower()),
    )[:8]

    return jsonify({
        "ok": True,
        "stats": {
            "total": total,
            "active": active,
            "resolved": resolved,
            "average_resolution_seconds": average_resolution,
        },
        "by_day": [
            {"date": key, "count": by_day[key]}
            for key in sorted(by_day)
        ],
        "by_status": [
            {"status": key, "count": value}
            for key, value in sorted(
                by_status.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "top_locations": top_locations,
        "records": records,
    })


@app.get("/api/dashboard/export")
def api_dashboard_export():
    if not require_auth():
        return jsonify({"ok": False, "message": "Unauthorised"}), 401

    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    statuses = [
        value.strip()
        for value in request.args.get("status", "").split(",")
        if value.strip()
    ]

    clauses = []
    params = []

    if start:
        clauses.append("date(created_at) >= date(?)")
        params.append(start)
    if end:
        clauses.append("date(created_at) <= date(?)")
        params.append(end)
    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with sqlite3.connect(DATA_DIR / "kidtrace.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT
                case_id,
                created_at,
                last_seen_location,
                status,
                latest_location,
                match_count,
                resolved_at
            FROM search_cases
            {where}
            ORDER BY datetime(created_at) DESC
            """,
            params,
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Case ID",
        "Search Started",
        "Last-Seen Location",
        "Status",
        "Latest Recorded Location",
        "Candidate Matches",
        "Resolved At",
    ])
    for row in rows:
        writer.writerow([
            row["case_id"],
            row["created_at"],
            row["last_seen_location"],
            row["status"],
            row["latest_location"] or "",
            row["match_count"],
            row["resolved_at"] or "",
        ])

    data = output.getvalue().encode("utf-8-sig")
    return app.response_class(
        data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=kidtrace_search_history.csv"
        },
    )


if __name__ == "__main__":
    app.run(debug=True, port=8501)
