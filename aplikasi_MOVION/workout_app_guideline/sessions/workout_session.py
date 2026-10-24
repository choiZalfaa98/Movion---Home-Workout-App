from services.workout_backends.duration import WorkoutDurationTracker
from services.workout_backends.calorie_calculator import CalorieCalculator

class WorkoutSessionTemp:
    def __init__(self):
        self.current_page = None # page guide or in session
        self.mode = None
        self.camera = None

        self.current_index = 0
        self.workouts = []

        self.user1 = {}
        self.user2 = None

        self.results = []
        self.runtime_reps = {}
        self.remaining_guide_time = None

        self.duration_tracker = WorkoutDurationTracker()
        self.calorie_calculator = CalorieCalculator()

        self.remote_session_id = None
        self.report_uploaded = False

    def set_config(self, mode, camera):
        self.mode = mode
        self.camera = camera

    def set_workouts(self, workouts):
        self.workouts = workouts
        self.current_index = 0

    def get_current_workout(self):
        if not self.workouts:
            return None
        return self.workouts[self.current_index]

    def next_workout(self):
        if self.current_index < len(self.workouts) - 1:
            self.current_index += 1
            return True
        return False

    def set_user1(self, user):
        self.user1 = user or {}

    def set_user2(self, user):
        self.user2 = user
    
    def add_workout_result(self, result):
        if not hasattr(self, "results") or self.results is None:
            self.results = []

        exercise_id = result.get("exercise_id")
        exercise_name = result.get("exercise")

        self.results = [
            r for r in self.results
            if r.get("exercise_id") != exercise_id
            and r.get("exercise") != exercise_name
        ]

        self.results.append(result)
        #print("[SESSION_RESULTS]", self.results)

    def get_workout_result(self, exercise_id=None, exercise_name=None):
        if not hasattr(self, "results") or self.results is None:
            self.results = []

        for result in self.results:
            if exercise_id and result.get("exercise_id") == exercise_id:
                return result
            if exercise_name and result.get("exercise") == exercise_name:
                return result

        return None

    def add_exercise_result(self, result):
        self.add_workout_result(result)

    def get_exercise_result(self, exercise_id=None, exercise_name=None):
        return self.get_workout_result(
            exercise_id=exercise_id,
            exercise_name=exercise_name
        )

    @property
    def exercise_results(self):
        return self.results

    @exercise_results.setter
    def exercise_results(self, value):
        self.results = value or []

    def reset(self):
        self.current_page = None # page guide or in session
        self.mode = None
        self.camera = None

        self.current_index = 0
        self.workouts = []

        self.user1 = {}
        self.user2 = None

        self.results = []
        self.runtime_reps = {}
        self.remaining_guide_time = None

        self.duration_tracker = WorkoutDurationTracker()
        self.calorie_calculator = CalorieCalculator()

        self.remote_session_id = None
        self.report_uploaded = False

    def start_timer(self):
        self.duration_tracker.start()

    def pause_timer(self):
        self.duration_tracker.pause()

    def resume_timer(self):
        self.duration_tracker.resume()

    def stop_timer(self):
        self.duration_tracker.stop()

    def get_duration_seconds(self):
        return self.duration_tracker.get_seconds()

    def get_duration_minutes(self):
        return self.duration_tracker.get_minutes()

    def get_duration_formatted(self):
        return self.duration_tracker.get_formatted()
    
    def set_remote_session_id(self, session_id):
        self.remote_session_id = session_id

    def mark_report_uploaded(self):
        self.report_uploaded = True
