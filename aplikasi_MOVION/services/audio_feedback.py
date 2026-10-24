from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtMultimedia import QSoundEffect

from pathlib import Path
from time import perf_counter

class AudioFeedback(QObject):
    PRIORITY = {
        "valid": 1,
        "wrong": 2,
        "finished": 3,
    }

    def __init__(
        self,
        base_dir: Path,
        volume: float = 0.7,
        parent=None,
    ):
        super().__init__(parent)

        self.enabled = True
        self.volume = volume

        self.single_cooldown_sec = 0.35
        self.multi_cooldown_sec = 0.70

        self.effects = {}
        self._last_user_audio_at = {
            "user1": 0.0,
            "user2": 0.0,
        }

        self._last_global_audio_at = 0.0
        self._last_global_status = None

        self._load_sounds(base_dir)

    def _load_sounds(self, base_dir: Path):
        sound_dir = base_dir / "assets" / "sounds"

        sound_map = {
            "valid": sound_dir / "correct.wav",
            "wrong": sound_dir / "wrong.wav",
            "finished": sound_dir / "finished.wav",
        }

        for status, path in sound_map.items():
            if not path.exists():
                #print(f"[AUDIO_MISSING] {status}: {path}")
                continue

            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(float(self.volume))

            self.effects[status] = effect

    def play(self, status: str, mode: str = "single", user_key: str = "user1"):
        if not self.enabled:
            return

        effect = self.effects.get(status)

        if effect is None:
            return

        if mode == "multi":
            if not self._allow_multi_audio(status):
                return
        else:
            if not self._allow_single_audio(user_key):
                return

        self._play_effect(status)

    def _allow_single_audio(self, user_key: str) -> bool:
        now = perf_counter()
        last = self._last_user_audio_at.get(user_key, 0.0)

        if now - last < self.single_cooldown_sec:
            return False

        self._last_user_audio_at[user_key] = now
        return True

    def _allow_multi_audio(self, status: str) -> bool:
        now = perf_counter()
        elapsed = now - self._last_global_audio_at

        if elapsed >= self.multi_cooldown_sec:
            self._last_global_audio_at = now
            self._last_global_status = status
            return True

        previous_priority = self.PRIORITY.get(self._last_global_status, 0)
        current_priority = self.PRIORITY.get(status, 0)

        if current_priority > previous_priority:
            self._last_global_audio_at = now
            self._last_global_status = status
            return True

        return False

    def _play_effect(self, status: str):
        effect = self.effects.get(status)

        if effect is None:
            return

        try:
            if effect.isPlaying():
                effect.stop()

            effect.play()

        except Exception as e:
            print("")
            #print(f"[AUDIO_FEEDBACK_ERROR] {status}: {e}")