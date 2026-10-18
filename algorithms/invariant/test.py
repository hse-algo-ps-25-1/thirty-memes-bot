import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from algorithm import (
    belief_trace,
    choose_meme,
    choose_with_model,
    edit_distance,
    load_model,
)

MEME_NAME = re.compile(r"^(0[1-9]|[12]\d|30)_[A-Za-z0-9_]+\.(jpg|png)$")
MEMES_DIR = Path(__file__).resolve().parent / "memes"
FEATURES_PATH = Path(__file__).resolve().parent / "features.txt"

HISTORY_A = ["завтра собес", "да"]
HISTORY_B = ["я выгорел на работе", "да"]

MEMES_COUNT = 30
FALLBACK = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))["fallback"]
ONE_SECOND_NS = 1_000_000_000
PROBABILITY_PLACES = 6
TEST_PARAMS = {
    "smoothing": 1.0,
    "switch": 0.3,
    "stay": 0.1,
    "group": 1.0,
    "after": 0.3,
    "next": 2.0,
}
TEST_GROUP = "Общая"

AUTO_REJECT_MEME = 4
CALL_BACK_MEME = 15
OFFER_MEME = 16
SALARY_MEME = 17
PROD_DOWN_MEME = 22
BURNOUT_MEME = 25
LAUGH_MEME = 29

DISGUISED_REJECTIONS = (
    "мне н\N{ZERO WIDTH SPACE}е дали оффер",
    "мне не да\N{COMBINING ACUTE ACCENT}ли оффер",
    "мне не да\N{COMBINING GRAVE ACCENT}ли оффер",
    "мне не д\N{COMBINING LOW LINE}а\N{COMBINING LOW LINE}ли оффер",
)

REACHING_PHRASES = {
    1: "требуют опыт три года для джуна",
    2: "разослал резюме, а в ответ тишина",
    3: "что указать в резюме",
    4: "опять пришел отказ",
    5: "какой у вас график работы",
    6: "всю ночь решал литкод",
    7: "прошел курсы и получил сертификат",
    8: "прислали тестовое на неделю",
    9: "готовлюсь к собеседованию",
    10: "кажется у меня синдром самозванца",
    11: "завтра первый собес",
    12: "на собесе был лайвкодинг",
    13: "спросили где я вижу себя через пять лет",
    14: "спросил почему у них свободна вакансия",
    15: "сказали что перезвонят",
    16: "ура, получил оффер",
    17: "сколько платят джунам",
    18: "обещают печеньки и дружный коллектив",
    19: "торгуюсь с hr за зарплату",
    20: "боюсь не пройти испытательный срок",
    21: "первый день на новой работе",
    22: "в пятницу упал прод",
    23: "разбираюсь в легаси без документации",
    24: "говорят контору скоро закроют",
    25: "походу я выгорел",
    26: "привет, бот",
    27: "да",
    28: "нет, спасибо",
    29: "ахахах",
    30: "не понял",
}

DIALOGS = (
    (["отправил сто резюме", "да"], AUTO_REJECT_MEME),
    (["мы вам перезвоним", "да"], AUTO_REJECT_MEME),
    (["завтра собес", "прод упал"], PROD_DOWN_MEME),
    (["прод упал", "ахахах"], LAUGH_MEME),
    (["завтра собес", "хм", "да"], CALL_BACK_MEME),
    (["прод упал", "хм", "да"], BURNOUT_MEME),
    (["привет", "оффер"], OFFER_MEME),
)

DEMO_HISTORY_A = ["мне тяжело сдать", "да"]
DEMO_HISTORY_B = ["сдал с первой попытки", "да"]

SAME_MEANING_PAIRS = (
    ("собеседование", "собес"),
    ("на собеседовании", "собес"),
    ("получил офер", "получил оффер"),
    ("получил offer", "получил оффер"),
    ("leetcode", "литкод"),
    ("деплой", "задеплоил"),
    ("legacy", "легаси"),
    ("колл", "созвон"),
    ("cv", "резюме"),
    ("interview", "собес"),
    ("prod", "прод"),
)

NEGATION_PAIRS = (
    ("прошел собес", "не прошел собес"),
    ("получил оффер", "не получил оффер"),
    ("прод упал", "прод не упал"),
    ("оффер", "без оффера"),
)

SERVICE_PHRASES = ("какая сегодня погода", "что делать", "без понятия")

STRETCHED_PAIRS = (
    ("дааааа", "да"),
    ("нееет", "нет"),
    ("оффффер", "оффер"),
    ("ДАааа", "да"),
    ("offffer", "offer"),
    ("helllo", "hello"),
)

LAUGH_VARIANTS = (
    "ахахахахахах",
    "ХАХАХАХАХА",
    "ахахаххаха",
    "ха-ха-ха",
    "хех",
    "xD",
    "hahaha",
)

TYPO_PAIRS = (
    ("собез", "собес"),
    ("лайфкодинг", "лайвкодинг"),
    ("выгарание", "выгорание"),
    ("рузюме", "резюме"),
    ("легасии", "легаси"),
    ("хотфик", "хотфикс"),
    ("стажеровку", "стажировку"),
    ("дедлаин", "дедлайн"),
)

ORDINARY_WORDS = ("вилла", "погода", "тесто", "кола", "пруд", "пион")

EDIT_DISTANCES = (
    ("собес", "собес", 1, 0),
    ("собез", "собес", 1, 1),
    ("kitten", "sitting", 5, 3),
    ("абв", "где", 1, 2),
    ("", "abc", 5, 3),
    ("abc", "", 5, 3),
)

HAND_PROBABILITIES = (
    (0, 0, 0.75),
    (0, 1, 0.25),
    (1, 0, 0.1388559),
    (1, 1, 0.8611441),
)

FRESH_PROCESS_SCRIPT = (
    "from algorithm import choose_meme\n"
    "for window in ({windows!r}):\n"
    "    print(choose_meme(list(window)))\n"
)


def _meme_names() -> set[str]:
    """Имена jpg/png в memes/ этой папки."""
    return {
        path.name
        for path in MEMES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".png"}
    }


def _features() -> dict:
    return json.loads(FEATURES_PATH.read_text(encoding="utf-8"))


def _number(file: str) -> int:
    return int(file.split("_", 1)[0])


def _meme(
    file: str,
    phrases: list[str],
    group: str = TEST_GROUP,
    next_files: tuple[str, ...] = (),
) -> dict:
    return {"file": file, "group": group, "phrases": phrases, "next": list(next_files)}


def _write_features(
    path: Path,
    memes: list[dict],
    groups: dict | None = None,
    synonyms: list[list[str]] | None = None,
    params: dict | None = None,
) -> None:
    description = {
        "params": params or TEST_PARAMS,
        "fallback": memes[-1]["file"],
        "stopwords": [],
        "synonyms": synonyms or [],
        "groups": groups or {TEST_GROUP: {"after": []}},
        "memes": memes,
    }
    path.write_text(json.dumps(description, ensure_ascii=False), encoding="utf-8")


def _write_model_folder(
    folder: Path,
    memes: list[dict],
    groups: dict | None = None,
    synonyms: list[list[str]] | None = None,
    params: dict | None = None,
) -> Path:
    memes_dir = folder / "memes"
    memes_dir.mkdir()
    for meme in memes:
        (memes_dir / meme["file"]).touch()
    path = folder / "features.txt"
    _write_features(path, memes, groups, synonyms, params)
    return path


def _mark_modified_later(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + ONE_SECOND_NS))


def _answers_in_fresh_process(windows: list[list[str]], hash_seed: str) -> list[str]:
    script = FRESH_PROCESS_SCRIPT.format(
        windows=tuple(tuple(window) for window in windows)
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parent,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.split()


class TestChooseMeme(unittest.TestCase):
    """Контракт демо: форма имени, файл на диске, детерминизм, разные истории."""

    def test_filename_matches_required_pattern(self):
        """Возврат — строка вида NN_латиница.jpg или .png."""
        name = choose_meme(["база рекурсии"])
        self.assertIsInstance(name, str)
        self.assertRegex(name, MEME_NAME)

    def test_deterministic_on_repeated_call(self):
        """Одинаковое окно на двух вызовах даёт одно и то же имя."""
        messages = ["локально зелёные", "Checks красные"]
        self.assertEqual(choose_meme(messages), choose_meme(list(messages)))

    def test_returned_file_exists_when_memes_present(self):
        """Выбранное имя есть среди файлов в memes/; пустой каталог — пропуск."""
        names = _meme_names()
        if not names:
            self.skipTest("в memes/ ещё нет картинок")
        name = choose_meme(["контрпример"])
        self.assertIn(name, names)

    def test_returns_meme_filename(self):
        """На непустом окне функция возвращает имя в договорённом формате."""
        name = choose_meme(["забыли базу"])
        self.assertIsInstance(name, str)
        self.assertRegex(name, MEME_NAME)

    def test_same_messages_same_file(self):
        """Один и тот же список реплик не меняет выбранный файл."""
        messages = ["уже считали"]
        self.assertEqual(choose_meme(messages), choose_meme(messages))

    def test_history_changes_choice(self):
        """Одно «да» после разных предысторий даёт разные файлы.

        Предыстории заданы в HISTORY_A и HISTORY_B.
        """
        self.assertGreaterEqual(len(HISTORY_A), 2)
        self.assertGreaterEqual(len(HISTORY_B), 2)
        self.assertEqual(HISTORY_A[-1], HISTORY_B[-1])
        self.assertNotEqual(HISTORY_A[:-1], HISTORY_B[:-1])
        self.assertNotEqual(choose_meme(HISTORY_A), choose_meme(HISTORY_B))


class TestFeaturesData(unittest.TestCase):
    """Данные features.txt согласованы с картинками в memes/."""

    def test_thirty_memes_with_valid_names(self):
        """В features.txt ровно 30 мемов с разными именами нужного формата."""
        files = [meme["file"] for meme in _features()["memes"]]
        self.assertEqual(len(files), MEMES_COUNT)
        self.assertEqual(len(set(files)), MEMES_COUNT)
        for file in files:
            with self.subTest(file=file):
                self.assertRegex(file, MEME_NAME)

    def test_memes_dir_matches_features(self):
        """В memes/ лежат ровно те 30 картинок, что описаны в features.txt."""
        files = {meme["file"] for meme in _features()["memes"]}
        self.assertEqual(_meme_names(), files)

    def test_every_meme_has_reaching_phrase(self):
        """Для каждого из 30 мемов есть живая фраза, на которую он отвечает."""
        self.assertEqual(sorted(REACHING_PHRASES), list(range(1, MEMES_COUNT + 1)))
        for number, phrase in REACHING_PHRASES.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(_number(choose_meme([phrase])), number)


class TestHistory(unittest.TestCase):
    """История окна влияет на ответ через переходы между мемами."""

    def test_dialogs_give_expected_memes(self):
        """Диалоги из сценария защиты дают закрепленные мемы."""
        for window, number in DIALOGS:
            with self.subTest(window=window):
                self.assertEqual(_number(choose_meme(window)), number)

    def test_demo_histories_give_different_memes(self):
        """Пара историй из демо-теста преподавателя тоже дает разные мемы."""
        self.assertNotEqual(choose_meme(DEMO_HISTORY_A), choose_meme(DEMO_HISTORY_B))


class TestTextProcessing(unittest.TestCase):
    """Своя нарезка: формы слов, синонимы, отрицание, стоп-слова, знаки."""

    def test_word_forms_and_synonyms_match(self):
        """Падеж, сленг и латиница дают тот же мем, что и основное слово."""
        for variant, canonical in SAME_MEANING_PAIRS:
            with self.subTest(variant=variant):
                expected = choose_meme([canonical])
                self.assertNotEqual(expected, FALLBACK)
                self.assertEqual(choose_meme([variant]), expected)

    def test_negation_changes_answer(self):
        """Частицы «не» и «без» склеиваются со словом и меняют ответ."""
        for positive, negated in NEGATION_PAIRS:
            with self.subTest(negated=negated):
                self.assertNotEqual(choose_meme([positive]), choose_meme([negated]))

    def test_stopwords_do_not_drive_answer(self):
        """Служебные слова не тянут ответ к случайному мему."""
        for phrase in SERVICE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertEqual(choose_meme([phrase]), FALLBACK)

    def test_repeated_word_counts_once(self):
        """Повтор слова не перевешивает остальной смысл реплики."""
        spam = "оффер " * 20 + "прод упал"
        self.assertEqual(_number(choose_meme([spam])), PROD_DOWN_MEME)

    def test_symbols_are_features(self):
        """Эмодзи, знаки валют и скобки-смайлы не теряются и ведут к своим мемам."""
        symbols = (
            ("😂", LAUGH_MEME),
            ("🔥", OFFER_MEME),
            ("₽", SALARY_MEME),
            (")))", LAUGH_MEME),
        )
        for symbol, number in symbols:
            with self.subTest(symbol=symbol):
                self.assertEqual(_number(choose_meme([symbol])), number)

    def test_question_after_topic_means_confusion(self):
        """Вопрос без слов после темы дает «не понял», а не мем темы."""
        self.assertEqual(choose_meme(["прод упал", "?"]), FALLBACK)

    def test_wordless_question_is_feature(self):
        """Вопрос без слов это признак: он ведет к мему, где есть такая фраза."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [_meme("01_question.png", ["?"]), _meme("02_rest.png", ["кот"])],
            )
            answer = choose_with_model(["?"], load_model(path))
        self.assertEqual(answer, "01_question.png")

    def test_unknown_last_reply_after_topic_gives_fallback(self):
        """Незнакомая последняя реплика дает «не понял», даже если тема была раньше."""
        self.assertEqual(choose_meme(["мы вам перезвоним", "йцуйцу"]), FALLBACK)

    def test_question_mark_next_to_words_is_ignored(self):
        """Вопрос со словами решают слова, а не знак вопроса."""
        self.assertEqual(
            choose_meme(["какая у вас вилка?"]), choose_meme(["какая у вас вилка"])
        )

    def test_invisible_marks_do_not_split_words(self):
        """Невидимый символ, ударение и подчеркивание не разрывают слово."""
        expected = choose_meme(["мне не дали оффер"])
        for disguised in DISGUISED_REJECTIONS:
            with self.subTest(disguised=disguised):
                self.assertEqual(choose_meme([disguised]), expected)

    def test_stretched_letters_are_squeezed(self):
        """Растянутые буквы не мешают: «дааааа» понимается как «да»."""
        for stretched, plain in STRETCHED_PAIRS:
            with self.subTest(stretched=stretched):
                expected = choose_meme([plain])
                self.assertNotEqual(expected, FALLBACK)
                self.assertEqual(choose_meme([stretched]), expected)

    def test_laugh_variants_give_laugh_meme(self):
        """Длинный смех, смех через дефис и короткие смешки ведут к мему про смех."""
        for laugh in LAUGH_VARIANTS:
            with self.subTest(laugh=laugh):
                self.assertEqual(_number(choose_meme([laugh])), LAUGH_MEME)


class TestTypos(unittest.TestCase):
    """Опечатки исправляются только в терминах из таблицы синонимов."""

    def test_edit_distance_examples(self):
        """Расстояние Левенштейна на классических примерах и остановка после порога."""
        for first, second, limit, expected in EDIT_DISTANCES:
            with self.subTest(first=first, second=second):
                self.assertEqual(edit_distance(first, second, limit), expected)

    def test_slang_typos_are_corrected(self):
        """Термин с опечаткой дает тот же мем, что и без нее."""
        for typo, correct in TYPO_PAIRS:
            with self.subTest(typo=typo):
                expected = choose_meme([correct])
                self.assertNotEqual(expected, FALLBACK)
                self.assertEqual(choose_meme([typo]), expected)

    def test_ordinary_words_are_not_corrected(self):
        """Обычные и короткие слова не подгоняются под близкие термины."""
        for word in ORDINARY_WORDS:
            with self.subTest(word=word):
                self.assertEqual(choose_meme([word]), FALLBACK)

    def test_stopword_is_not_corrected_to_term(self):
        """Стоп-слово не исправляется в термин: «вроде» не становится «прод»."""
        self.assertEqual(choose_meme(["вроде"]), FALLBACK)

    def test_ambiguous_typo_is_not_corrected(self):
        """Опечатка на равном расстоянии от двух терминов не исправляется."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_kotik.png", ["котик"]),
                    _meme("02_kotel.png", ["котел"]),
                    _meme("03_rest.png", ["слон"]),
                ],
                synonyms=[["котик"], ["котел"]],
            )
            model = load_model(path)
            ambiguous = choose_with_model(["котек"], model)
            unique = choose_with_model(["котикк"], model)
        self.assertEqual(ambiguous, "03_rest.png")
        self.assertEqual(unique, "01_kotik.png")

    def test_typo_between_spellings_of_one_word_is_corrected(self):
        """Опечатка на равном расстоянии от двух написаний одного слова исправляется."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [_meme("01_kotik.png", ["котик"]), _meme("02_rest.png", ["слон"])],
                synonyms=[["котик", "котек"]],
            )
            answer = choose_with_model(["котак"], load_model(path))
        self.assertEqual(answer, "01_kotik.png")


class TestRobustness(unittest.TestCase):
    """Функция определена на любом окне и не меняет вход."""

    def test_window_without_known_words_gives_fallback(self):
        """Окно без единого знакомого признака дает запасной мем."""
        windows = (
            ["абырвалг", "qwerty uiop"],
            ["!!!"],
            ["🙂"],
            ["12345"],
            ["9.9.2026"],
            [""],
            ["а" * 4000],
        )
        for window in windows:
            with self.subTest(window=window[0][:20]):
                self.assertEqual(choose_meme(window), FALLBACK)

    def test_empty_message_does_not_break_window(self):
        """Пустая реплика в окне не мешает разобрать остальные."""
        self.assertEqual(choose_meme(["", "да"]), choose_meme(["да"]))

    def test_many_distinct_words_do_not_underflow(self):
        """Реплика с сотнями разных известных слов дает существующий мем."""
        phrases = [
            phrase for meme in _features()["memes"] for phrase in meme["phrases"]
        ]
        self.assertIn(choose_meme([" ".join(phrases)]), _meme_names())

    def test_window_not_modified(self):
        """Функция не меняет переданный список реплик."""
        messages = ["завтра собес", "да"]
        snapshot = list(messages)
        choose_meme(messages)
        self.assertEqual(messages, snapshot)

    def test_same_answers_in_fresh_processes(self):
        """Ответы совпадают в процессах с разным порядком хеширования строк."""
        windows = [window for window, _ in DIALOGS] + [HISTORY_A, HISTORY_B]
        expected = [choose_meme(window) for window in windows]
        self.assertEqual(_answers_in_fresh_process(windows, "1"), expected)
        self.assertEqual(_answers_in_fresh_process(windows, "2"), expected)


class TestInputValidation(unittest.TestCase):
    """Окно, нарушающее контракт, отвергается понятной ошибкой."""

    def test_empty_window_rejected(self):
        """Пустой список реплик нарушает контракт и дает ValueError."""
        with self.assertRaises(ValueError):
            choose_meme([])

    def test_wrong_types_rejected(self):
        """Не список реплик или реплика не строкой дают понятный TypeError."""
        for window in ("завтра собес", ("завтра собес",), [None], ["ок", 5]):
            with self.subTest(window=window):
                with self.assertRaisesRegex(TypeError, "строк"):
                    choose_meme(window)


class TestDataDrivenModel(unittest.TestCase):
    """Ответы задаются данными features.txt, а не кодом."""

    def test_forward_step_matches_hand_calculation(self):
        """Прямой ход на модели из двух мемов совпадает с ручным расчетом."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_cat.png", ["кот"], next_files=("02_dog.png",)),
                    _meme("02_dog.png", ["собака"]),
                ],
            )
            trace = belief_trace(["кот", "собака"], load_model(path))
        for step, meme, probability in HAND_PROBABILITIES:
            with self.subTest(step=step, meme=meme):
                self.assertAlmostEqual(
                    trace[step][meme], probability, places=PROBABILITY_PLACES
                )

    def test_after_moves_to_next_stage(self):
        """Связь after ведет нейтральную реплику на следующий этап."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_cat.png", ["кот", "животное"], group="A"),
                    _meme("02_dog.png", ["собака", "животное"], group="B"),
                    _meme("03_fish.png", ["рыба", "животное"], group="C"),
                ],
                groups={"A": {"after": ["B"]}, "B": {"after": []}, "C": {"after": []}},
            )
            answer = choose_with_model(["кот", "животное"], load_model(path))
        self.assertEqual(answer, "02_dog.png")

    def test_lonely_meme_keeps_state(self):
        """Мем без соседей по этапу остается текущим состоянием за счет stay."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_dog.png", ["собака", "животное"], group="B"),
                    _meme("02_fish.png", ["рыба", "животное"], group="B"),
                    _meme("03_cat.png", ["кот", "животное"], group="A"),
                    _meme("04_rest.png", ["слон"], group="B"),
                ],
                groups={"A": {"after": []}, "B": {"after": []}},
            )
            answer = choose_with_model(["кот", "животное"], load_model(path))
        self.assertEqual(answer, "03_cat.png")

    def test_short_description_is_not_outweighed(self):
        """Длинное описание мема не дает преимущества перед коротким."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_long.png", ["кот", "собака", "рыба", "птица", "мышь"]),
                    _meme("02_short.png", ["кот"]),
                    _meme("03_rest.png", ["слон"]),
                ],
            )
            answer = choose_with_model(["кот"], load_model(path))
        self.assertEqual(answer, "02_short.png")

    def test_tie_goes_to_smaller_number(self):
        """При ничьей выигрывает меньший номер, даже если в файле он записан вторым."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("02_second.png", ["кот"]),
                    _meme("01_first.png", ["кот"]),
                    _meme("03_rest.png", ["собака"]),
                ],
            )
            answer = choose_with_model(["кот"], load_model(path))
        self.assertEqual(answer, "01_first.png")

    def test_features_edit_changes_answer(self):
        """Правка features.txt меняет ответ без правки кода и перезапуска."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_first.png", ["кот"]),
                    _meme("02_second.png", ["собака"]),
                    _meme("03_rest.png", ["рыба"]),
                ],
            )
            before = choose_with_model(["кот"], load_model(path))
            _write_features(
                path,
                [
                    _meme("01_first.png", ["собака"]),
                    _meme("02_second.png", ["кот"]),
                    _meme("03_rest.png", ["рыба"]),
                ],
            )
            _mark_modified_later(path)
            after = choose_with_model(["кот"], load_model(path))
        self.assertEqual(before, "01_first.png")
        self.assertEqual(after, "02_second.png")

    def test_missing_image_rejected(self):
        """Мем без картинки в memes/ не загружается."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [_meme("01_first.png", ["кот"]), _meme("02_rest.png", ["собака"])],
            )
            (Path(folder) / "memes" / "01_first.png").unlink()
            with self.assertRaises(ValueError):
                load_model(path)

    def test_zero_switch_rejected(self):
        """Нулевой switch отвергается: знаменатель шага Байеса мог бы обнулиться."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [_meme("01_first.png", ["кот"]), _meme("02_rest.png", ["собака"])],
                params={**TEST_PARAMS, "switch": 0.0},
            )
            with self.assertRaises(ValueError):
                load_model(path)

    def test_meme_without_field_rejected(self):
        """Мем без обязательного поля дает понятный ValueError, а не KeyError."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    {"file": "01_first.png", "group": TEST_GROUP},
                    _meme("02_rest.png", ["собака"]),
                ],
            )
            with self.assertRaises(ValueError):
                load_model(path)

    def test_unknown_group_rejected(self):
        """Мем с группой, которой нет в groups, не загружается."""
        with tempfile.TemporaryDirectory() as folder:
            path = _write_model_folder(
                Path(folder),
                [
                    _meme("01_first.png", ["кот"], group="Нет такой"),
                    _meme("02_rest.png", ["собака"]),
                ],
            )
            with self.assertRaises(ValueError):
                load_model(path)


if __name__ == "__main__":
    unittest.main()
