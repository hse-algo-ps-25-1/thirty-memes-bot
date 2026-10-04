from collections import deque


class SessionStore:
    def __init__(self, window: int = 5) -> None:
        self.window = window
        self._windows: dict[tuple[int, int], deque[str]] = {}

    def push(self, chat_id: int, user_id: int, text: str) -> list[str]:
        key = (chat_id, user_id)
        history = self._windows.setdefault(key, deque(maxlen=self.window))
        history.append(text)
        return list(history)

    def clear_all(self) -> None:
        self._windows.clear()
