class CalorieCalculator:
    MET_VALUES = {
    "squat": 5.0, # moderate strength
    "jumping_jacks": 8.0, # high cardio
    "mountain_climber": 8.0, # high intensity cardio
    "knee_push_up": 4.0, # moderate strength
    "sit_up": 4.5, # moderate core
    }

    DEFAULT_MET = 5.0

    def _safe_float(self, value, default):
        try:
            if value is None or value == "":
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _safe_int(self, value, default):
        try:
            if value is None or value == "":
                return int(default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _normalize_height_m(self, height):
        height = self._safe_float(height, 1.65)

        if height > 3:
            height = height / 100

        return height

    def get_met_value(self, exercise_id):
        key = str(exercise_id or "").strip().lower()
        return self.MET_VALUES.get(key, self.DEFAULT_MET)

    def calculate_rmr(self, gender, weight_kg, height_m, age):
        gender = str(gender or "").strip().lower()

        if gender in ["female", "wanita", "perempuan", "f"]:
            return (
                (7.38 * weight_kg)
                + (607 * height_m)
                - (2.31 * age)
                + 43
            )

        return (
            (9.65 * weight_kg)
            + (573 * height_m)
            - (5.08 * age)
            + 260
        )

    def calculate(self, met, weight_kg, duration_hours, rmr):
        calories = (
            (met - 1.0) * weight_kg * duration_hours
            + (rmr / 24) * duration_hours
        )

        return round(calories, 2)

    def calculate_total_from_session(self, session, user_info=None):
        user_info = user_info or {}

        weight_kg = self._safe_float(
            user_info.get("weight_kg", user_info.get("weight")),
            60
        )
        height_m = self._normalize_height_m(
            user_info.get("height_cm", user_info.get("height"))
        )
        age = self._safe_int(user_info.get("age"), 20)
        gender = user_info.get("gender", "male")

        duration_minutes = 0.0
        if hasattr(session, "get_duration_minutes"):
            duration_minutes = session.get_duration_minutes()

        duration_hours = duration_minutes / 60

        rmr = self.calculate_rmr(
            gender=gender,
            weight_kg=weight_kg,
            height_m=height_m,
            age=age
        )

        met_values = []

        for workout in getattr(session, "workouts", []):
            exercise_id = workout.get("id")
            met_values.append(self.get_met_value(exercise_id))

        avg_met = (
            sum(met_values) / len(met_values)
            if met_values
            else 5.0
        )

        return self.calculate(
            met=avg_met,
            weight_kg=weight_kg,
            duration_hours=duration_hours,
            rmr=rmr
        )