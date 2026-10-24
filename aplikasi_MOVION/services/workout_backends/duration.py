import time

class WorkoutDurationTracker:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.paused_at = None
        self.total_paused_seconds = 0.0

    def start(self):
        self.start_time = time.monotonic()
        self.end_time = None
        self.paused_at = None
        self.total_paused_seconds = 0.0

    def pause(self):
        if self.start_time is None:
            return

        if self.paused_at is None:
            self.paused_at = time.monotonic()

    def resume(self):
        if self.paused_at is None:
            return

        self.total_paused_seconds += time.monotonic() - self.paused_at
        self.paused_at = None

    def stop(self):
        if self.start_time is None:
            return

        if self.paused_at is not None:
            self.resume()

        self.end_time = time.monotonic()

    def get_seconds(self):
        if self.start_time is None:
            return 0

        current_end = self.end_time or time.monotonic()

        paused_extra = 0.0
        if self.paused_at is not None:
            paused_extra = time.monotonic() - self.paused_at

        elapsed = current_end - self.start_time
        active = elapsed - self.total_paused_seconds - paused_extra

        return max(0, int(active))

    def get_minutes(self):
        return self.get_seconds() / 60

    def get_formatted(self):
        seconds = self.get_seconds()

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60

        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
