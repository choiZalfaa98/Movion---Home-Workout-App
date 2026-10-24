from .person_tracker import PersonTracker

class WorkoutController:
    """
    Controls the user tracking flow during a workout session.

    The controller manages two main phases:
    - position_check:
        Detects and registers users before the workout starts.
        Each detected person is assigned to a user key ("user1"/"user2").

    - tracking:
        Uses the registered person-track mapping to identify users
        consistently across workout frames.

    The controller coordinates user readiness state and delegates
    track ID management to PersonTracker.
    """

    PHASE_POSITION_CHECK = "position_check"
    PHASE_TRACKING = "tracking"

    def __init__(self):
        self.tracker = PersonTracker()
        self.phase = self.PHASE_POSITION_CHECK

        self.ready_users = {
            "user1": False,
            "user2": False,
        }

    @property
    def is_position_check(self):
        return self.phase == self.PHASE_POSITION_CHECK

    @property
    def is_tracking(self):
        return self.phase == self.PHASE_TRACKING

    def enter_tracking_phase(self):
        self.phase = self.PHASE_TRACKING

    def enter_position_check_phase(self):
        self.phase = self.PHASE_POSITION_CHECK

    def try_register_user(self, user_key, track_id):
        if self.ready_users.get(user_key):
            return False

        registered = self.tracker.register_user(
            user_key,
            track_id,
        )

        if not registered:
            return False

        self.ready_users[user_key] = True
        return True

    def is_user_ready(self, user_key):
        return self.ready_users.get(user_key, False)

    def is_all_ready(self, mode):
        if mode == "single":
            return self.ready_users["user1"]

        return (
            self.ready_users["user1"]
            and self.ready_users["user2"]
        )

    def get_user_key(self, track_id):
        return self.tracker.get_user_key(track_id)

    def get_track_id(self, user_key):
        return self.tracker.get_track_id(user_key)

    def update_user_track(self, user_key, new_track_id):
        return self.tracker.update_user_track(user_key, new_track_id)

    def reset_for_resume(self):
        self.tracker.reset()

        self.ready_users = {
            "user1": False,
            "user2": False,
        }

        self.phase = self.PHASE_POSITION_CHECK

    def reset_for_next_exercise(self):
        self.tracker.reset()

        self.ready_users = {
            "user1": False,
            "user2": False,
        }

        self.phase = self.PHASE_POSITION_CHECK

    def reset_full(self):
        self.tracker.reset()

        self.ready_users = {
            "user1": False,
            "user2": False,
        }

        self.phase = self.PHASE_POSITION_CHECK

    def debug_info(self):
        return {
            "phase": self.phase,
            "ready": dict(self.ready_users),
            "tracks": self.tracker.get_all(),
        }
