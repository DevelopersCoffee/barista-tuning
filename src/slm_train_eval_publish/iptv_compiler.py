from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from slm_train_eval_publish.media_ir import MediaAssetIr

LANGUAGE_NAME_HINTS = {
    "hindi": "hi",
    "marathi": "mr",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "gujarati": "gu",
    "bangla": "bn",
    "bengali": "bn",
    "punjabi": "pa",
    "malayalam": "ml",
}

GENRE_MAP = {
    "animation": "kids",
    "auto": "lifestyle",
    "business": "business",
    "classic": "movies",
    "comedy": "comedy",
    "cooking": "lifestyle",
    "culture": "documentary",
    "documentary": "documentary",
    "education": "education",
    "entertainment": "entertainment",
    "family": "entertainment",
    "general": "general",
    "kids": "kids",
    "legislative": "news",
    "lifestyle": "lifestyle",
    "movies": "movies",
    "music": "music",
    "news": "news",
    "outdoor": "lifestyle",
    "regional": "entertainment",
    "religious": "religious",
    "science": "education",
    "series": "entertainment",
    "shop": "shopping",
    "sports": "sports",
    "travel": "lifestyle",
    "weather": "weather",
}


@dataclass(frozen=True)
class IptvCompileResult:
    media_ir: Path
    report: Path
    asset_count: int


def compile_iptv_source_to_media_ir(
    source: str,
    output: Path,
    provider: str = "iptv",
    metadata_version: str = "1.0.0",
    limit: int | None = None,
) -> IptvCompileResult:
    source_payload = _load_source(source)
    if source_payload.lstrip().startswith("#EXTM3U"):
        source_data = _m3u_to_source(source_payload, source=source, limit=limit)
    else:
        source_data = json.loads(source_payload)
        if limit is not None:
            source_data["channels"] = source_data.get("channels", [])[:limit]

    return compile_iptv_source_data_to_media_ir(
        source=source_data,
        output=output,
        provider=provider,
        metadata_version=metadata_version,
    )


def compile_iptv_to_media_ir(
    channels_json: Path,
    output: Path,
    provider: str = "iptv",
    metadata_version: str = "1.0.0",
) -> IptvCompileResult:
    source = json.loads(channels_json.read_text(encoding="utf-8"))
    return compile_iptv_source_data_to_media_ir(
        source=source,
        output=output,
        provider=provider,
        metadata_version=metadata_version,
    )


def compile_iptv_source_data_to_media_ir(
    source: dict[str, Any],
    output: Path,
    provider: str = "iptv",
    metadata_version: str = "1.0.0",
) -> IptvCompileResult:
    channels = source.get("channels", [])
    if not isinstance(channels, list):
        raise ValueError("channels JSON must contain a channels list")

    output.mkdir(parents=True, exist_ok=True)
    media_ir_path = output / "media_ir.jsonl"
    report_path = output / "compile-report.json"

    assets = [
        _channel_to_media_asset(channel, provider=provider, metadata_version=metadata_version)
        for channel in channels
    ]

    with media_ir_path.open("w", encoding="utf-8") as handle:
        for asset in assets:
            handle.write(json.dumps(asset.to_json(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    report = _compile_report(assets, source)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return IptvCompileResult(
        media_ir=media_ir_path,
        report=report_path,
        asset_count=len(assets),
    )


def _load_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=30) as response:
            return response.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def _m3u_to_source(m3u: str, source: str, limit: int | None = None) -> dict[str, Any]:
    channels: list[dict[str, Any]] = []
    lines = [line.strip() for line in m3u.splitlines() if line.strip()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("#EXTINF"):
            index += 1
            continue

        stream_url = ""
        if index + 1 < len(lines) and not lines[index + 1].startswith("#"):
            stream_url = lines[index + 1]

        attrs = _parse_extinf_attrs(line)
        display_name = _parse_extinf_display_name(line)
        name = attrs.get("tvg-name") or display_name or attrs.get("tvg-id") or f"Channel {index}"
        group = attrs.get("group-title") or "general"
        languages = [
            part.strip().lower()
            for part in (attrs.get("tvg-language") or "und").split(";")
            if part.strip()
        ]

        channels.append(
            {
                "id": attrs.get("tvg-id") or name,
                "name": name,
                "streamUrl": stream_url,
                "logoUrl": attrs.get("tvg-logo"),
                "category": group.split(",")[0].strip().lower() or "general",
                "country": attrs.get("tvg-country"),
                "languages": languages,
                "flavor": "general",
                "group": group,
                "qualityUrls": {},
                "altNames": [display_name] if display_name and display_name != name else [],
                "sources": ["m3u"],
            }
        )

        if limit is not None and len(channels) >= limit:
            break
        index += 2

    return {
        "version": "m3u",
        "generatedAt": None,
        "source": source,
        "channels": channels,
    }


def _parse_extinf_attrs(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'([\w-]+)="([^"]*)"', line)
    }


def _parse_extinf_display_name(line: str) -> str:
    if "," not in line:
        return ""
    return line.rsplit(",", 1)[1].strip()


def _channel_to_media_asset(
    channel: dict[str, Any],
    provider: str,
    metadata_version: str,
) -> MediaAssetIr:
    title = str(channel.get("name") or channel.get("id") or "").strip()
    if not title:
        raise ValueError("channel requires name or id")

    raw_id = str(channel.get("id") or title)
    category = _normalize_token(str(channel.get("category") or channel.get("group") or "general"))
    genre = GENRE_MAP.get(category, "general")
    languages = _languages(channel, title)
    keywords = _keywords(title, channel, genre, languages)

    return MediaAssetIr(
        id=_stable_media_id(provider, raw_id),
        title=title,
        provider=provider,
        type="live_channel",
        language=languages,
        genres=[genre],
        subgenres=[] if category == genre else [category],
        country=channel.get("country"),
        region=_region(channel.get("country"), languages, title),
        keywords=keywords,
        mood=_moods_for_genre(genre),
        themes=_themes_for_genre(genre, title),
        availability={"live": True, "playable": bool(channel.get("streamUrl"))},
        quality=_quality(title, channel.get("streamUrl")),
        stream_uri=channel.get("streamUrl"),
        thumbnail=channel.get("logoUrl"),
        metadata_version=metadata_version,
    )


def _languages(channel: dict[str, Any], title: str) -> list[str]:
    values = [str(value).lower() for value in channel.get("languages", []) if value]
    lowered = title.lower()
    for hint, code in LANGUAGE_NAME_HINTS.items():
        if hint in lowered:
            values.append(code)

    flavor = str(channel.get("flavor") or "").lower()
    if "hindi" in flavor:
        values.append("hi")

    return _dedupe(values or ["und"])


def _keywords(title: str, channel: dict[str, Any], genre: str, languages: list[str]) -> list[str]:
    values = [
        title,
        _normalize_text(title),
        genre,
        "live",
        "24x7",
        *languages,
        str(channel.get("country") or "").lower(),
    ]
    values.extend(str(value) for value in channel.get("altNames", []) if value)
    values.extend(_split_words(title))
    return _dedupe([_normalize_text(value) for value in values if value])


def _quality(title: str, stream_url: str | None) -> dict[str, Any]:
    value = f"{title} {stream_url or ''}".lower()
    if "4k" in value or "uhd" in value:
        return {"resolution": "4k"}
    if re.search(r"\b(fhd|hd|1080)\b", value):
        return {"resolution": "hd"}
    return {}


def _moods_for_genre(genre: str) -> list[str]:
    return {
        "comedy": ["funny"],
        "education": ["educational"],
        "kids": ["safe", "playful"],
        "movies": ["entertaining"],
        "music": ["energetic"],
        "news": ["informative"],
        "religious": ["devotional", "calm"],
        "sports": ["energetic"],
    }.get(genre, [])


def _themes_for_genre(genre: str, title: str) -> list[str]:
    themes = {
        "business": ["markets", "finance"],
        "news": ["current affairs"],
        "religious": ["devotional"],
        "sports": ["live sports"],
    }.get(genre, [])
    lowered = title.lower()
    if "cricket" in lowered:
        themes.append("cricket")
    if "kids" in lowered:
        themes.append("children")
    return _dedupe(themes)


def _region(country: str | None, languages: list[str], title: str) -> str | None:
    lowered = title.lower()
    if country == "IN":
        if "marathi" in lowered or "mr" in languages:
            return "maharashtra"
        if "tamil" in lowered or "ta" in languages:
            return "tamil_nadu"
        if "telugu" in lowered or "te" in languages:
            return "andhra_telangana"
        if "kannada" in lowered or "kn" in languages:
            return "karnataka"
        if "gujarati" in lowered or "gu" in languages:
            return "gujarat"
        return "india"
    if country == "US":
        return "united_states"
    return None


def _compile_report(assets: list[MediaAssetIr], source: dict[str, Any]) -> dict[str, Any]:
    genre_counts = Counter(asset.genres[0] if asset.genres else "unknown" for asset in assets)
    language_counts = Counter(language for asset in assets for language in asset.language)
    return {
        "source_version": source.get("version"),
        "source_generated_at": source.get("generatedAt"),
        "asset_count": len(assets),
        "genre_counts": dict(sorted(genre_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
    }


def _stable_media_id(provider: str, raw_id: str) -> str:
    return f"{provider}_{_normalize_token(raw_id).replace('.', '_')}"


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", value.lower()).strip("_") or "unknown"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip().lower()


def _split_words(value: str) -> list[str]:
    return [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
