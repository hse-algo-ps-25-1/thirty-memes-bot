import unittest

from thirty_memes_bot.session import SessionStore


class TestSessionStore(unittest.TestCase):
    """Окна истории: длина, изоляция диалогов, сброс."""

    def test_window_keeps_last_five(self):
        """Шестая реплика вытесняет первую: в окне остаются только последние пять."""
        store = SessionStore(window=5)
        for index in range(6):
            history = store.push(1, 10, f"m{index}")
        self.assertEqual(history, ["m1", "m2", "m3", "m4", "m5"])

    def test_keys_are_independent(self):
        """Пары (chat_id, user_id) не делят очередь: сосед в том же чате видит своё окно."""
        store = SessionStore()
        store.push(1, 10, "a")
        other = store.push(1, 11, "b")
        self.assertEqual(other, ["b"])
        self.assertEqual(store.push(1, 10, "c"), ["a", "c"])

    def test_clear_all(self):
        """После clear_all следующее сообщение начинает новое окно, без старого хвоста."""
        store = SessionStore()
        store.push(1, 10, "a")
        store.clear_all()
        self.assertEqual(store.push(1, 10, "b"), ["b"])
