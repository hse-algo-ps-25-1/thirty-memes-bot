import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from thirty_memes_bot.text import lemmatize, normalize, tokenize

FEATURES_NAME = "features.txt"
MEMES_DIR_NAME = "memes"
SECTION_NAMES = ("params", "fallback", "stopwords", "synonyms", "groups", "memes")
PARAM_NAMES = ("smoothing", "switch", "stay", "group", "after", "next")
MEME_FIELDS = ("file", "group", "phrases")
WORDLESS_MARKS = frozenset({"?", ")", "("})
SYMBOL_CATEGORIES = frozenset({"So", "Sc"})
INVISIBLE_CATEGORY = "Cf"
DROPPED_MARKS = frozenset(
    {
        "\N{COMBINING GRAVE ACCENT}",
        "\N{COMBINING ACUTE ACCENT}",
        "\N{COMBINING LOW LINE}",
    }
)
STRETCHED_LETTER = re.compile(r"([^\W\d_])\1{2,}")
REPEATED_SYLLABLE = re.compile(r"([^\W\d_]{2})\1{2,}")
NEGATIONS = frozenset({"не", "без"})
NEGATION_JOINER = "_"
MIN_TYPO_LENGTH = 5
LONG_WORD_LENGTH = 8
SHORT_WORD_EDITS = 1
LONG_WORD_EDITS = 2
TIE_TOLERANCE = 1e-12
MODEL_CACHE_SIZE = 8
CORRECTION_CACHE_SIZE = 4096


@dataclass(frozen=True)
class TextRules:
    synonyms: dict[str, str]
    stopwords: frozenset[str]
    terms: tuple[tuple[str, str], ...]
    known_lemmas: frozenset[str]


@dataclass(frozen=True)
class Model:
    files: list[str]
    feature_counts: list[dict[str, int]]
    feature_totals: list[int]
    collection_counts: dict[str, int]
    collection_total: int
    transitions: list[list[float]]
    rules: TextRules
    smoothing: float
    fallback: str


def _features_path() -> Path:
    return Path(__file__).resolve().parent / FEATURES_NAME


def _cleaned_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    kept = [
        char
        for char in decomposed
        if char not in DROPPED_MARKS
        and unicodedata.category(char) != INVISIBLE_CATEGORY
    ]
    return unicodedata.normalize("NFC", "".join(kept))


def _squeezed_token(token: str) -> str:
    squeezed_letters = STRETCHED_LETTER.sub(r"\1", token)
    return REPEATED_SYLLABLE.sub(r"\1\1", squeezed_letters)


def _symbol_features(text: str, has_meaningful_words: bool) -> list[str]:
    return [
        char
        for char in text
        if unicodedata.category(char) in SYMBOL_CATEGORIES
        or (char in WORDLESS_MARKS and not has_meaningful_words)
    ]


def _join_negations(words: list[str]) -> list[str]:
    joined = []
    index = 0
    while index < len(words):
        if words[index] in NEGATIONS and index + 1 < len(words):
            joined.append(words[index] + NEGATION_JOINER + words[index + 1])
            index += 2
        else:
            joined.append(words[index])
            index += 1
    return joined


def edit_distance(first: str, second: str, limit: int) -> int:
    previous = list(range(len(second) + 1))
    for row in range(1, len(first) + 1):
        current = [row] + [0] * len(second)
        for column in range(1, len(second) + 1):
            replace_cost = 0 if first[row - 1] == second[column - 1] else 1
            current[column] = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + replace_cost,
            )
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


@lru_cache(maxsize=CORRECTION_CACHE_SIZE)
def _corrected_token(token: str, terms: tuple[tuple[str, str], ...]) -> str:
    limit = LONG_WORD_EDITS if len(token) >= LONG_WORD_LENGTH else SHORT_WORD_EDITS
    best_term = token
    best_distance = limit + 1
    best_canonicals = set()
    for term, canonical in terms:
        if abs(len(term) - len(token)) > limit:
            continue
        distance = edit_distance(token, term, limit)
        if distance > limit:
            continue
        if distance < best_distance:
            best_term = term
            best_distance = distance
            best_canonicals = {canonical}
        elif distance == best_distance:
            best_canonicals.add(canonical)
    if len(best_canonicals) != 1:
        return token
    return best_term


def _needs_correction(token: str, lemma: str, rules: TextRules) -> bool:
    if len(token) < MIN_TYPO_LENGTH:
        return False
    return lemma not in rules.known_lemmas and lemma not in rules.stopwords


def _spell_checked_lemmas(text: str, rules: TextRules) -> list[str]:
    tokens = tokenize(text)
    squeezed_tokens = [_squeezed_token(token) for token in tokens]
    lemmas = lemmatize(squeezed_tokens)
    checked = []
    for token, squeezed_token, lemma in zip(
        tokens, squeezed_tokens, lemmas, strict=True
    ):
        if _needs_correction(token, lemma, rules):
            corrected = _corrected_token(squeezed_token, rules.terms)
            checked.append(lemmatize([corrected])[0])
        else:
            checked.append(lemma)
    return checked


def _reply_features(text: str, rules: TextRules) -> list[str]:
    cleaned = _cleaned_text(text)
    words = [
        rules.synonyms.get(word, word) for word in _spell_checked_lemmas(cleaned, rules)
    ]
    meaningful = [
        word
        for word in _join_negations(words)
        if word not in rules.stopwords and not word.isdigit()
    ]
    symbols = _symbol_features(cleaned, bool(meaningful))
    return list(dict.fromkeys(symbols + meaningful))


def _one_lemma_per_word(words: list[str], label: str) -> list[str]:
    lemmas = []
    for word in words:
        word_lemmas = normalize(word)
        if len(word_lemmas) != 1:
            raise ValueError(f"{label}: {word!r} должно быть одним словом")
        lemmas.append(word_lemmas[0])
    return lemmas


def _validate_sections(description: dict) -> None:
    for name in SECTION_NAMES:
        if name not in description:
            raise ValueError(f"в {FEATURES_NAME} нет раздела {name}")


def _validate_params(params: dict) -> None:
    for name in PARAM_NAMES:
        if name not in params:
            raise ValueError(f"нет параметра {name}")
        if params[name] < 0:
            raise ValueError(f"параметр {name} не может быть отрицательным")
    if params["smoothing"] == 0:
        raise ValueError("параметр smoothing должен быть больше нуля")
    if not 0 < params["switch"] <= 1:
        raise ValueError("параметр switch должен быть больше 0 и не больше 1")


def _validate_groups(groups: dict) -> None:
    for name, group in groups.items():
        unknown = [target for target in group.get("after", []) if target not in groups]
        if unknown:
            raise ValueError(f"группа {name}: в after неизвестные группы {unknown}")


def _validate_meme_fields(memes: list[dict]) -> None:
    for position, meme in enumerate(memes, start=1):
        missing = [field for field in MEME_FIELDS if field not in meme]
        if missing:
            raise ValueError(f"мем номер {position} в списке: нет полей {missing}")


def _validate_memes(description: dict, memes_dir: Path) -> None:
    files = [meme["file"] for meme in description["memes"]]
    if len(set(files)) != len(files):
        raise ValueError("имена файлов мемов повторяются")
    for meme in description["memes"]:
        if not (memes_dir / meme["file"]).is_file():
            raise ValueError(f"нет картинки {meme['file']} в {MEMES_DIR_NAME}/")
        if meme["group"] not in description["groups"]:
            raise ValueError(f"мем {meme['file']}: неизвестная группа {meme['group']}")
        if not meme["phrases"]:
            raise ValueError(f"мем {meme['file']}: нет фраз")
        unknown = [target for target in meme.get("next", []) if target not in files]
        if unknown:
            raise ValueError(f"мем {meme['file']}: в next неизвестные мемы {unknown}")
    if description["fallback"] not in files:
        raise ValueError(f"запасной мем {description['fallback']} не описан в memes")


def _register_synonyms(lemmas: list[str], canonical_by_lemma: dict[str, str]) -> None:
    for lemma in lemmas:
        registered = canonical_by_lemma.setdefault(lemma, lemmas[0])
        if registered != lemmas[0]:
            raise ValueError(f"слово {lemma!r} попало в два ряда синонимов")


def _validate_synonyms(rows: list[list[str]]) -> None:
    canonical_by_lemma = {}
    for row in rows:
        if not row:
            raise ValueError("пустой ряд синонимов")
        _register_synonyms(_one_lemma_per_word(row, "синоним"), canonical_by_lemma)


def _validate_stopwords(words: list[str]) -> None:
    _one_lemma_per_word(words, "стоп-слово")


def _validate_features(description: dict, memes_dir: Path) -> None:
    _validate_sections(description)
    _validate_params(description["params"])
    _validate_groups(description["groups"])
    _validate_meme_fields(description["memes"])
    _validate_memes(description, memes_dir)
    _validate_synonyms(description["synonyms"])
    _validate_stopwords(description["stopwords"])


def _validate_messages(messages: object) -> None:
    if not isinstance(messages, list):
        raise TypeError("messages должен быть списком строк")
    if not messages:
        raise ValueError("окно реплик не может быть пустым")
    if not all(isinstance(message, str) for message in messages):
        raise TypeError("каждая реплика должна быть строкой")


def _known_lemmas(description: dict) -> frozenset[str]:
    known = set()
    for meme in description["memes"]:
        for phrase in meme["phrases"]:
            known.update(normalize(phrase))
    for row in description["synonyms"]:
        known.update(_one_lemma_per_word(row, "синоним"))
    return frozenset(known)


def _build_rules(description: dict) -> TextRules:
    synonyms = {}
    terms = set()
    for row in description["synonyms"]:
        lemmas = _one_lemma_per_word(row, "синоним")
        canonical = lemmas[0]
        for word, lemma in zip(row, lemmas, strict=True):
            synonyms[lemma] = canonical
            terms.add((tokenize(word)[0], canonical))
    return TextRules(
        synonyms=synonyms,
        stopwords=frozenset(
            _one_lemma_per_word(description["stopwords"], "стоп-слово")
        ),
        terms=tuple(sorted(terms)),
        known_lemmas=_known_lemmas(description),
    )


def _count_features(phrases: list[str], rules: TextRules) -> dict[str, int]:
    counts = {}
    for phrase in phrases:
        for feature in _reply_features(phrase, rules):
            counts[feature] = counts.get(feature, 0) + 1
    return counts


def _collection_counts(feature_counts: list[dict[str, int]]) -> dict[str, int]:
    collection = {}
    for counts in feature_counts:
        for feature, count in counts.items():
            collection[feature] = collection.get(feature, 0) + count
    return collection


def _transition_weight(
    source: dict, target: dict, following_groups: dict, params: dict
) -> float:
    weight = 0.0
    if target["file"] == source["file"]:
        weight += params["stay"]
    elif target["group"] == source["group"]:
        weight += params["group"]
    if target["group"] in following_groups[source["group"]]:
        weight += params["after"]
    if target["file"] in source.get("next", []):
        weight += params["next"]
    return weight


def _transition_row(
    source: dict, memes: list[dict], following_groups: dict, params: dict
) -> list[float]:
    weights = [
        _transition_weight(source, target, following_groups, params) for target in memes
    ]
    total = sum(weights)
    if total == 0:
        weights = [1.0] * len(memes)
        total = float(len(memes))
    switch = params["switch"]
    return [(1 - switch) * weight / total + switch / len(memes) for weight in weights]


@lru_cache(maxsize=MODEL_CACHE_SIZE)
def _load_model(path: Path, modified_ns: int) -> Model:
    description = json.loads(path.read_text(encoding="utf-8"))
    _validate_features(description, path.parent / MEMES_DIR_NAME)
    memes = sorted(description["memes"], key=lambda meme: meme["file"])
    rules = _build_rules(description)
    following_groups = {
        name: group.get("after", []) for name, group in description["groups"].items()
    }
    params = description["params"]
    feature_counts = [_count_features(meme["phrases"], rules) for meme in memes]
    collection_counts = _collection_counts(feature_counts)
    return Model(
        files=[meme["file"] for meme in memes],
        feature_counts=feature_counts,
        feature_totals=[sum(counts.values()) for counts in feature_counts],
        collection_counts=collection_counts,
        collection_total=sum(collection_counts.values()),
        transitions=[
            _transition_row(meme, memes, following_groups, params) for meme in memes
        ],
        rules=rules,
        smoothing=params["smoothing"],
        fallback=description["fallback"],
    )


def load_model(path: Path) -> Model:
    return _load_model(path, path.stat().st_mtime_ns)


def _log_likelihoods(features: list[str], model: Model) -> list[float]:
    known_features = [
        feature for feature in features if feature in model.collection_counts
    ]
    log_likelihoods = []
    for index in range(len(model.files)):
        counts = model.feature_counts[index]
        smoothed_total = model.feature_totals[index] + model.smoothing
        log_likelihood = 0.0
        for feature in known_features:
            background_probability = (
                model.collection_counts[feature] / model.collection_total
            )
            smoothed_count = (
                counts.get(feature, 0) + model.smoothing * background_probability
            )
            log_likelihood += math.log(smoothed_count / smoothed_total)
        log_likelihoods.append(log_likelihood)
    return log_likelihoods


def _propagate(belief: list[float], transitions: list[list[float]]) -> list[float]:
    prior = [0.0] * len(belief)
    for source in range(len(belief)):
        for target in range(len(belief)):
            prior[target] += belief[source] * transitions[source][target]
    return prior


def _bayes_update(prior: list[float], log_likelihoods: list[float]) -> list[float]:
    max_log_likelihood = max(log_likelihoods)
    weights = [
        prior_probability * math.exp(log_likelihood - max_log_likelihood)
        for prior_probability, log_likelihood in zip(
            prior, log_likelihoods, strict=True
        )
    ]
    total = sum(weights)
    return [weight / total for weight in weights]


def _window_features(messages: list[str], model: Model) -> list[list[str]]:
    return [_reply_features(message, model.rules) for message in messages]


def _has_known_feature(features: list[str], model: Model) -> bool:
    return any(feature in model.collection_counts for feature in features)


def _forward(window: list[list[str]], model: Model) -> list[list[float]]:
    belief = [1 / len(model.files)] * len(model.files)
    trace = [belief]
    for position, features in enumerate(window):
        prior = belief if position == 0 else _propagate(belief, model.transitions)
        belief = _bayes_update(prior, _log_likelihoods(features, model))
        trace.append(belief)
    return trace


def _first_max_index(values: list[float]) -> int:
    best = 0
    for index in range(1, len(values)):
        if values[index] > values[best] * (1 + TIE_TOLERANCE):
            best = index
    return best


def belief_trace(messages: list[str], model: Model) -> list[list[float]]:
    _validate_messages(messages)
    return _forward(_window_features(messages, model), model)[1:]


def choose_with_model(messages: list[str], model: Model) -> str:
    _validate_messages(messages)
    last_features = _reply_features(messages[-1], model.rules)
    if not _has_known_feature(last_features, model):
        return model.fallback
    window = _window_features(messages[:-1], model) + [last_features]
    return model.files[_first_max_index(_forward(window, model)[-1])]


def choose_meme(messages: list[str]) -> str:
    """Выбирает имя файла мема по окну реплик.

    messages — реплики по времени, последняя — текущая, список непустой.
    Возвращает имя файла из memes/, например "04_base_case.jpg".
    Детерминировано: одинаковый messages даёт одинаковый файл.

    :param messages: непустой список текстовых реплик
    :return: имя существующего файла из memes/
    """
    return choose_with_model(messages, load_model(_features_path()))
