from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from pathlib import Path
from datetime import datetime
import re

def _downloads_dir():
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads

def _safe_filename(text):
    text = str(text or "workout-report")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "workout-report"

def _unique_path(path: Path):
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

def generate_workout_report_pdf(report_data):
    try:
        mode = report_data.get("mode", "workout")
        date_text = report_data.get("date", "")
        users = report_data.get("users", [])

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"movion-{_safe_filename(mode)}-report-{timestamp}.pdf"
        file_path = _unique_path(_downloads_dir() / filename)

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "MovionTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            spaceAfter=12,
        )

        heading_style = ParagraphStyle(
            "MovionHeading",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=8,
        )

        normal_style = styles["BodyText"]

        elements = []

        elements.append(Paragraph("MOVION Workout Report", title_style))
        elements.append(Paragraph(f"Date: {date_text}", normal_style))
        elements.append(Paragraph(f"Mode: {str(mode).title()}", normal_style))
        elements.append(Spacer(1, 12))

        for idx, user in enumerate(users, start=1):
            name = user.get("name", f"User {idx}")
            duration = user.get("duration", "00:00:00")
            calories = user.get("calories", 0)
            exercises = user.get("exercises", {})

            elements.append(Paragraph(name, heading_style))

            summary_data = [
                ["Total Workout Duration", str(duration)],
                ["Estimated Calories Burned", f"{calories} kcal"],
            ]

            summary_table = Table(
                summary_data,
                colWidths=[7 * cm, 7 * cm],
            )

            summary_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )

            elements.append(summary_table)
            elements.append(Spacer(1, 12))

            exercise_rows = [
                ["Exercise", "Correct", "Total", "Percentage"]
            ]

            for exercise_name, stats in exercises.items():
                correct = int(stats.get("correct", 0) or 0)
                total = int(stats.get("total", 0) or 0)

                percentage = 0
                if total > 0:
                    percentage = correct / total * 100

                exercise_rows.append(
                    [
                        exercise_name,
                        str(correct),
                        str(total),
                        f"{percentage:.1f}%",
                    ]
                )

            exercise_table = Table(
                exercise_rows,
                colWidths=[7 * cm, 2.5 * cm, 2.5 * cm, 3 * cm],
                repeatRows=1,
            )

            exercise_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )

            elements.append(exercise_table)
            elements.append(Spacer(1, 18))

        doc.build(elements)

        return {
            "success": True,
            "file_path": str(file_path),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }