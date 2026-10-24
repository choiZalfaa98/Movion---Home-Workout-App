class PersonTracker:
    """
    Maintains a two-directional mapping between user keys
    ("user1", "user2") and tracker-generated person IDs.

    The mapping allows workout processing to identify the same person
    across frames during workout session.
    """

    def __init__(self):
        self._user_to_track: dict[str, int] = {}
        self._track_to_user: dict[int, str] = {}

    def register_user(self, user_key: str, tracking_id: int) -> bool:
        if user_key in self._user_to_track:
            return False

        if tracking_id in self._track_to_user:
            return False

        self._user_to_track[user_key] = tracking_id
        self._track_to_user[tracking_id] = user_key

        return True

    def has_user(self, user_key: str) -> bool:
        return user_key in self._user_to_track

    def get_track_id(self, user_key: str) -> int | None:
        return self._user_to_track.get(user_key)

    def get_user_key(self, track_id: int) -> str | None:
        return self._track_to_user.get(track_id)

    def get_all(self) -> dict[str, int]:
        return dict(self._user_to_track)

    def update_user_track(self, user_key: str, new_track_id: int) -> bool:
        old_track_id = self._user_to_track.get(user_key)

        if old_track_id == new_track_id:
            return True

        existing_user = self._track_to_user.get(new_track_id)
        if existing_user is not None and existing_user != user_key:
            return False

        if old_track_id is not None:
            self._track_to_user.pop(old_track_id, None)

        self._user_to_track[user_key] = new_track_id
        self._track_to_user[new_track_id] = user_key

        return True

    def reset(self):
        self._user_to_track.clear()
        self._track_to_user.clear()
