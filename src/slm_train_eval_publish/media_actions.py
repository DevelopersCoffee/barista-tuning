from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEM_INSTRUCTION = (
    "Translate the Airo TV user request into a media action JSON object. "
    "Output JSON only. Do not answer conversationally."
)


@dataclass(frozen=True)
class MediaActionExample:
    utterance: str
    intent: str
    tool: str
    constraints: dict[str, Any]
    confidence: float = 0.9
    missing_fields: tuple[str, ...] = ()
    clarification_required: bool = False

    def to_sft_row(self) -> dict[str, str]:
        output = {
            "intent": self.intent,
            "tool": self.tool,
            "confidence": self.confidence,
            "constraints": self.constraints,
            "missing_fields": list(self.missing_fields),
            "clarification_required": self.clarification_required,
        }
        return {
            "instruction": SYSTEM_INSTRUCTION,
            "input": self.utterance,
            "output": json.dumps(output, sort_keys=True, separators=(",", ":")),
        }


def generate_media_action_examples(count: int, seed: int = 42) -> list[MediaActionExample]:
    if count < 1:
        raise ValueError("count must be >= 1")

    rng = random.Random(seed)
    templates = _base_templates()
    examples: list[MediaActionExample] = []

    while len(examples) < count:
        template = rng.choice(templates)
        examples.append(template(rng))

    return examples


def write_media_actions_jsonl(output: Path, count: int, seed: int = 42) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    examples = generate_media_action_examples(count=count, seed=seed)
    _write_examples(output, examples)
    return output


def write_media_actions_split(
    train_output: Path,
    eval_output: Path,
    train_count: int,
    eval_count: int,
    seed: int = 42,
) -> tuple[Path, Path]:
    if train_count < 1:
        raise ValueError("train_count must be >= 1")
    if eval_count < 1:
        raise ValueError("eval_count must be >= 1")

    train_examples = generate_media_action_examples(count=train_count, seed=seed)
    eval_examples = generate_media_action_examples(count=eval_count, seed=seed + 10_000)
    _write_examples(train_output, train_examples)
    _write_examples(eval_output, eval_examples)
    return train_output, eval_output


def _write_examples(output: Path, examples: list[MediaActionExample]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_sft_row(), ensure_ascii=False))
            handle.write("\n")


def _base_templates():
    languages = [
        ("Hindi", "hi"),
        ("English", "en"),
        ("Marathi", "mr"),
        ("Tamil", "ta"),
        ("Telugu", "te"),
    ]
    moods = ["funny", "calm", "inspiring", "relaxing"]
    direct_titles = ["Aaj Tak", "Sony Max", "PBS Kids", "India cricket live"]

    def search_news(rng: random.Random) -> MediaActionExample:
        label, code = rng.choice(languages)
        return MediaActionExample(
            utterance=rng.choice(
                [
                    f"Show {label} news",
                    f"I want {label.lower()} news",
                    f"Find live news in {label}",
                ]
            ),
            intent="search",
            tool="media.search",
            constraints={"genre": "news", "language": code, "live": True},
            confidence=0.92,
        )

    def play_direct(rng: random.Random) -> MediaActionExample:
        title = rng.choice(direct_titles)
        return MediaActionExample(
            utterance=rng.choice([f"Play {title}", f"Put on {title}", f"Open {title}"]),
            intent="play",
            tool="media.play",
            constraints={"query": title, "live": True},
            confidence=0.94,
        )

    def kids(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(
                [
                    "Put on cartoons for my daughter",
                    "Kids are here",
                    "Show something safe for a 5 year old",
                ]
            ),
            intent="recommend",
            tool="media.recommend",
            constraints={"audience": "kids", "genre": "kids", "age_safe": True},
            confidence=0.88,
        )

    def sports(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(
                [
                    "Play today's India match",
                    "Cricket live",
                    "Show live cricket",
                ]
            ),
            intent="play",
            tool="media.play",
            constraints={"genre": "sports", "subgenre": "cricket", "live": True},
            confidence=0.89,
        )

    def mood_recommendation(rng: random.Random) -> MediaActionExample:
        mood = rng.choice(moods)
        return MediaActionExample(
            utterance=rng.choice(
                [
                    f"I want something {mood}",
                    f"Recommend something {mood} for tonight",
                    f"Find {mood} content",
                ]
            ),
            intent="recommend",
            tool="media.recommend",
            constraints={"mood": mood},
            confidence=0.84,
        )

    def education(rng: random.Random) -> MediaActionExample:
        utterance = rng.choice(
            [
                "Something educational",
                "Find educational content",
                "Show something educational for Class 8",
            ]
        )
        constraints = {"genre": "education"}
        if "Class 8" in utterance:
            constraints["grade"] = "8"
        return MediaActionExample(
            utterance=utterance,
            intent="recommend",
            tool="media.recommend",
            constraints=constraints,
            confidence=0.84,
        )

    def resume(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(
                [
                    "Continue the movie I was watching",
                    "Resume yesterday's movie",
                    "Continue from where I stopped",
                ]
            ),
            intent="resume",
            tool="media.resume",
            constraints={"continue_watching": True},
            confidence=0.91,
        )

    def browse_live(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(
                [
                    "What's live right now?",
                    "Show live channels",
                    "Browse live TV",
                ]
            ),
            intent="browse",
            tool="media.browse",
            constraints={"live": True},
            confidence=0.9,
        )

    def favorite(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(
                [
                    "Add this to favorites",
                    "Favorite this channel",
                    "Save this for later",
                ]
            ),
            intent="favorite",
            tool="media.favorite",
            constraints={"target": "current"},
            confidence=0.87,
        )

    def clarify(rng: random.Random) -> MediaActionExample:
        return MediaActionExample(
            utterance=rng.choice(["Play Sony", "Put on news", "Show the match"]),
            intent="clarify",
            tool="media.clarify",
            constraints={},
            confidence=0.62,
            missing_fields=("specific_media",),
            clarification_required=True,
        )

    return [
        search_news,
        play_direct,
        kids,
        sports,
        mood_recommendation,
        education,
        resume,
        browse_live,
        favorite,
        clarify,
    ]
