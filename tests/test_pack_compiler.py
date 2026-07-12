from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from slm_train_eval_publish.pack_compiler import compile_media_pack


def test_compile_media_pack(tmp_path: Path) -> None:
    media_ir = tmp_path / "media_ir.jsonl"
    media_ir.write_text(
        json.dumps(
            {
                "id": "iptv_aajtak_in",
                "title": "Aaj Tak",
                "provider": "iptv",
                "type": "live_channel",
                "language": ["hi"],
                "genres": ["news"],
                "subgenres": [],
                "country": "IN",
                "region": "india",
                "keywords": ["aaj tak", "news", "hindi"],
                "cast": [],
                "director": None,
                "year": None,
                "duration": None,
                "rating": None,
                "age_rating": None,
                "mood": ["informative"],
                "themes": ["current affairs"],
                "availability": {"live": True, "playable": True},
                "quality": {},
                "stream_uri": "https://example.test/aajtak.m3u8",
                "thumbnail": None,
                "metadata_version": "1.0.0",
            }
        )
        + "\n"
    )

    output = tmp_path / "media.iptv.india-0.1.0.pack"
    result = compile_media_pack(
        media_ir=media_ir,
        output=output,
        pack_id="media.iptv.india",
        pack_name="India IPTV",
    )

    assert result.asset_count == 1
    assert output.exists()

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "media.db" in names
        assert "indexes/search.idx" in names
        assert "indexes/recommendation.idx" in names

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["pack"]["id"] == "media.iptv.india"
        assert manifest["metadata"]["asset_count"] == 1

        db_path = tmp_path / "media.db"
        db_path.write_bytes(archive.read("media.db"))

    connection = sqlite3.connect(db_path)
    try:
        count = connection.execute("select count(*) from media_assets").fetchone()[0]
    finally:
        connection.close()
    assert count == 1

