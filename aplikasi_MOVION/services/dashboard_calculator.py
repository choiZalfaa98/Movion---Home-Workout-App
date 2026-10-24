from services.workout_report_service import get_workout_history

import json
from datetime import datetime

def fetch_dashboard_stats(user_id):
    try:
        try:
            result = get_workout_history(user_id=user_id, mode=None)
        except TypeError:
            result = get_workout_history(user_id=user_id)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to load workout history"),
                "data": get_empty_dashboard_stats(),
            }

        rows = result.get("data", []) or []
        stats = calculate_dashboard_stats(rows)

        return {
            "success": True,
            "data": stats,
        }

    except Exception as e:
        #print("[DASHBOARD_STATS_ERROR]", e)

        return {
            "success": False,
            "error": str(e),
            "data": get_empty_dashboard_stats(),
        }

def fetch_monthly_workout_frequency(user_id):
    try:
        try:
            result = get_workout_history(user_id=user_id, mode=None)
        except TypeError:
            result = get_workout_history(user_id=user_id)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to load workout history"),
                "data": get_empty_monthly_frequency(),
            }

        rows = result.get("data", []) or []
        chart_data = calculate_monthly_workout_frequency(rows)

        return {
            "success": True,
            "data": chart_data,
        }

    except Exception as e:
        #print("[MONTHLY_FREQ_ERROR]", e)

        return {
            "success": False,
            "error": str(e),
            "data": get_empty_monthly_frequency(),
        }

def calculate_monthly_workout_frequency(history_rows):
    completed_dates = []

    for row in history_rows:
        status = str(row.get("status", "")).lower()

        if status != "completed":
            continue

        dt = extract_workout_datetime(row)

        if dt is None:
            continue

        completed_dates.append(dt)

    if not completed_dates:
        return get_empty_monthly_frequency()

    latest_dt = max(completed_dates)
    target_year = latest_dt.year
    target_month = latest_dt.month

    values = [0, 0, 0, 0]

    for dt in completed_dates:
        if dt.year != target_year or dt.month != target_month:
            continue

        week_index = get_month_week_index(dt.day)
        values[week_index] += 1

    month_label = latest_dt.strftime("%B %Y")
    max_value = max(values) if values else 0

    y_axis_max = max(1, max_value + 1)

    return {
        "month_label": month_label,
        "values": values,
        "y_axis_max": y_axis_max,
    }

def extract_workout_datetime(row):
    for key in ("started_at", "ended_at", "created_at"):
        value = row.get(key)

        if not value:
            continue

        dt = parse_supabase_datetime(value)

        if dt is not None:
            return dt
    return None

def parse_supabase_datetime(value):
    if isinstance(value, datetime):
        return value

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except Exception:
        return None

def get_month_week_index(day):
    """
    Week 1 = 1-7
    Week 2 = 8-14
    Week 3 = 15-21
    Week 4 = 22-last day of the month
    """

    if day <= 7:
        return 0

    if day <= 14:
        return 1

    if day <= 21:
        return 2

    return 3

def get_empty_monthly_frequency():
    now = datetime.now()

    return {
        "month_label": now.strftime("%B %Y"),
        "values": [0, 0, 0, 0],
        "y_axis_max": 7,
    }

def calculate_dashboard_stats(history_rows):
    total_correct_reps = 0
    total_reps = 0
    total_calories = 0.0
    total_duration_seconds = 0

    completed_sessions = 0

    for row in history_rows:
        status = str(row.get("status", "")).lower()

        if status != "completed":
            continue

        report_data = extract_report_data(row)

        if not report_data:
            continue

        users = report_data.get("users", []) or []

        if not users:
            continue

        user_data = users[0]

        completed_sessions += 1

        exercises = user_data.get("exercises", {}) or {}

        for _exercise_name, exercise_stats in exercises.items():
            correct = safe_int(exercise_stats.get("correct", 0))
            total = safe_int(exercise_stats.get("total", 0))

            total_correct_reps += correct
            total_reps += total

        total_calories += safe_float(user_data.get("calories", 0))
        total_duration_seconds += parse_duration_to_seconds(
            user_data.get("duration", "00:00:00")
        )

    correct_percentage = (
        (total_correct_reps / total_reps) * 100
        if total_reps > 0
        else 0
    )

    return {
        "completed_sessions": completed_sessions,

        "total_correct_reps": total_correct_reps,
        "total_reps": total_reps,
        "correct_reps_percentage": correct_percentage,

        "total_calories": total_calories,
        "total_duration_seconds": total_duration_seconds,

        "correct_reps_display": format_percentage(correct_percentage),
        "calories_display": format_calories(total_calories),
        "duration_display": format_duration_hours(total_duration_seconds),
    }

def extract_report_data(row):
    reports = row.get("workout_reports")

    if reports is None:
        return {}

    if isinstance(reports, dict):
        reports = [reports]

    if not isinstance(reports, list) or not reports:
        return {}

    report = reports[0] or {}
    report_data = report.get("report_data", {})

    if isinstance(report_data, dict):
        return report_data

    if isinstance(report_data, str):
        try:
            return json.loads(report_data)
        except Exception:
            return {}

    return {}


def parse_duration_to_seconds(value):
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()

    if not text:
        return 0

    if ":" in text:
        parts = text.split(":")

        try:
            parts = [int(float(part)) for part in parts]
        except Exception:
            return 0

        if len(parts) == 3:
            hours, minutes, seconds = parts
            return hours * 3600 + minutes * 60 + seconds

        if len(parts) == 2:
            minutes, seconds = parts
            return minutes * 60 + seconds

    lowered = text.lower()

    try:
        number = float(
            lowered
            .replace("hours", "")
            .replace("hour", "")
            .replace("hrs", "")
            .replace("hr", "")
            .replace("minutes", "")
            .replace("minute", "")
            .replace("mins", "")
            .replace("min", "")
            .strip()
        )

        if "hour" in lowered or "hr" in lowered:
            return int(number * 3600)

        if "minute" in lowered or "min" in lowered:
            return int(number * 60)

        return int(number)

    except Exception:
        return 0

def safe_int(value):
    try:
        return int(float(value))
    except Exception:
        return 0

def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0

def format_percentage(value):
    if value <= 0:
        return "0%"

    if abs(value - round(value)) < 0.05:
        return f"{round(value)}%"

    return f"{value:.1f}%"

def format_calories(value):
    if value <= 0:
        return "0 kcal"

    if abs(value - round(value)) < 0.05:
        return f"{round(value)} kcal"

    return f"{value:.1f} kcal"

def format_duration_hours(seconds):
    hours = seconds / 3600

    if hours <= 0:
        return "0 hours"

    if hours < 1:
        return f"{hours:.1f} hours"

    if abs(hours - round(hours)) < 0.05:
        return f"{round(hours)} hours"

    return f"{hours:.1f} hours"

def get_empty_dashboard_stats():
    return {
        "completed_sessions": 0,

        "total_correct_reps": 0,
        "total_reps": 0,
        "correct_reps_percentage": 0,

        "total_calories": 0,
        "total_duration_seconds": 0,

        "correct_reps_display": "0%",
        "calories_display": "0 kcal",
        "duration_display": "0 hours",
    }