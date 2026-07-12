from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaIntentResult:
    intent: str
    tool: str
    confidence: float
    constraints: dict[str, Any]
    missing_fields: list[str]
    clarification_required: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "tool": self.tool,
            "confidence": self.confidence,
            "constraints": self.constraints,
            "missing_fields": self.missing_fields,
            "clarification_required": self.clarification_required,
        }


def parse_media_intent(utterance: str) -> MediaIntentResult:
    text = " ".join(utterance.lower().split())
    language = _language(text)
    quality = _quality(text)

    if text in {"play sony", "put on news", "show the match"}:
        return MediaIntentResult(
            intent="clarify",
            tool="media.clarify",
            confidence=0.62,
            constraints={},
            missing_fields=["specific_media"],
            clarification_required=True,
        )

    if any(phrase in text for phrase in ["add this to favorites", "favorite this channel"]):
        return _result("favorite", "media.favorite", {"target": "current"}, 0.87)
    if "save this for later" in text:
        return _result("favorite", "media.favorite", {"target": "current"}, 0.87)

    if any(phrase in text for phrase in ["continue", "resume"]):
        return _result("resume", "media.resume", {"continue_watching": True}, 0.91)

    if any(phrase in text for phrase in ["what's live", "show live channels", "browse live tv"]):
        return _result("browse", "media.browse", {"live": True}, 0.9)

    direct_title = _direct_title(text)
    if direct_title is not None:
        return _result("play", "media.play", {"query": direct_title, "live": True}, 0.94)

    if "cricket" in text or "india match" in text:
        constraints: dict[str, Any] = {
            "genre": "sports",
            "subgenre": "cricket",
            "live": True,
        }
        if quality is not None:
            constraints["quality"] = quality
        return _result(
            "play",
            "media.play",
            constraints,
            0.89,
        )

    if "sports" in text:
        constraints = {"genre": "sports"}
        if quality is not None:
            constraints["quality"] = quality
        return _result("search", "media.search", constraints, 0.86)

    if "violent" in text or "violence" in text:
        return _result(
            "recommend",
            "media.recommend",
            {"parental_control": True, "avoid": "violence"},
            0.82,
        )

    if "kid" in text or "cartoon" in text or "5 year old" in text:
        return _result(
            "recommend",
            "media.recommend",
            {"audience": "kids", "genre": "kids", "age_safe": True},
            0.88,
        )

    if "movie" in text or "movies" in text or "film" in text:
        constraints = {"genre": "movies"}
        if language is not None:
            constraints["language"] = language
        if quality is not None:
            constraints["quality"] = quality
        if "latest" in text or "recent" in text:
            constraints["sort"] = "recent"
        intent = "play" if "play" in text else "search"
        tool = "media.play" if intent == "play" else "media.search"
        return _result(intent, tool, constraints, 0.86)

    if "news" in text:
        genre = "business_news" if "business" in text else "news"
        constraints = {"genre": genre, "live": True}
        if language is not None:
            constraints["language"] = language
        if quality is not None:
            constraints["quality"] = quality
        return _result("search", "media.search", constraints, 0.92)

    if any(token in text for token in ["devotional", "religious", "bhajan"]):
        constraints = {"genre": "religious"}
        if language is not None:
            constraints["language"] = language
        return _result("recommend", "media.recommend", constraints, 0.84)

    if any(token in text for token in ["educational", "education", "class 8"]):
        constraints = {"genre": "education"}
        if "class 8" in text:
            constraints["grade"] = "8"
        return _result("recommend", "media.recommend", constraints, 0.84)

    if "free" in text:
        return _result("search", "media.search", {"subscription": "free"}, 0.76)

    mood = _mood(text)
    if mood is not None:
        return _result("recommend", "media.recommend", {"mood": mood}, 0.84)

    return _result("recommend", "media.recommend", {}, 0.58)


def evaluate_media_actions_jsonl(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError("evaluation file has no rows")

    metrics = {
        "total": len(rows),
        "intent_correct": 0,
        "tool_correct": 0,
        "constraints_exact": 0,
        "clarification_correct": 0,
    }

    failures: list[dict[str, Any]] = []
    for row in rows:
        expected = json.loads(row["output"])
        actual = parse_media_intent(row["input"]).to_json()

        metrics["intent_correct"] += int(actual["intent"] == expected["intent"])
        metrics["tool_correct"] += int(actual["tool"] == expected["tool"])
        metrics["constraints_exact"] += int(actual["constraints"] == expected["constraints"])
        metrics["clarification_correct"] += int(
            actual["clarification_required"] == expected["clarification_required"]
        )

        if actual["tool"] != expected["tool"] or actual["constraints"] != expected["constraints"]:
            failures.append(
                {
                    "input": row["input"],
                    "expected": expected,
                    "actual": actual,
                }
            )

    total = metrics["total"]
    return {
        **metrics,
        "intent_accuracy": metrics["intent_correct"] / total,
        "tool_accuracy": metrics["tool_correct"] / total,
        "constraint_exact_accuracy": metrics["constraints_exact"] / total,
        "clarification_accuracy": metrics["clarification_correct"] / total,
        "failures": failures[:20],
    }


def _result(
    intent: str,
    tool: str,
    constraints: dict[str, Any],
    confidence: float,
) -> MediaIntentResult:
    return MediaIntentResult(
        intent=intent,
        tool=tool,
        confidence=confidence,
        constraints=constraints,
        missing_fields=[],
        clarification_required=False,
    )


def _direct_title(text: str) -> str | None:
    titles = {
        "aaj tak": "Aaj Tak",
        "sony max": "Sony Max",
        "pbs kids": "PBS Kids",
        "india cricket live": "India cricket live",
    }
    if not text.startswith(("play ", "put on ", "open ")):
        return None
    for needle, title in titles.items():
        if needle in text:
            return title
    return None


def _language(text: str) -> str | None:
    languages = {
        "hindi": "hi",
        "english": "en",
        "marathi": "mr",
        "tamil": "ta",
        "telugu": "te",
    }
    for name, code in languages.items():
        if name in text:
            return code
    return None


def _quality(text: str) -> str | None:
    if any(token in text for token in ["hd", "1080p", "fhd"]):
        return "hd"
    if any(token in text for token in ["sd", "480p"]):
        return "sd"
    return None


def _mood(text: str) -> str | None:
    moods = {
        "funny": "funny",
        "comedy": "funny",
        "calm": "calm",
        "inspiring": "inspiring",
        "educational": "educational",
        "relax": "relaxing",
        "relaxing": "relaxing",
        "bored": "entertainment",
    }
    for token, mood in moods.items():
        if token in text:
            return mood
    return None
