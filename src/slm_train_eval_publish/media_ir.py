from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MediaAssetIr:
    id: str
    title: str
    provider: str
    type: str
    language: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    subgenres: list[str] = field(default_factory=list)
    country: str | None = None
    region: str | None = None
    keywords: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    director: str | None = None
    year: int | None = None
    duration: int | None = None
    rating: float | None = None
    age_rating: str | None = None
    mood: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    availability: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    stream_uri: str | None = None
    thumbnail: str | None = None
    metadata_version: str = "1.0.0"

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "provider": self.provider,
            "type": self.type,
            "language": self.language,
            "genres": self.genres,
            "subgenres": self.subgenres,
            "country": self.country,
            "region": self.region,
            "keywords": self.keywords,
            "cast": self.cast,
            "director": self.director,
            "year": self.year,
            "duration": self.duration,
            "rating": self.rating,
            "age_rating": self.age_rating,
            "mood": self.mood,
            "themes": self.themes,
            "availability": self.availability,
            "quality": self.quality,
            "stream_uri": self.stream_uri,
            "thumbnail": self.thumbnail,
            "metadata_version": self.metadata_version,
        }

