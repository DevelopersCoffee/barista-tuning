from __future__ import annotations

import json
from pathlib import Path

from slm_train_eval_publish.iptv_compiler import (
    compile_iptv_source_to_media_ir,
    compile_iptv_to_media_ir,
)


def test_compile_iptv_to_media_ir(tmp_path: Path) -> None:
    source = tmp_path / "channels.json"
    source.write_text(
        json.dumps(
            {
                "version": "test",
                "generatedAt": "2026-07-12T00:00:00Z",
                "channels": [
                    {
                        "id": "AajTak.in",
                        "name": "Aaj Tak",
                        "streamUrl": "https://example.test/aajtak/master.m3u8",
                        "logoUrl": None,
                        "category": "news",
                        "country": "IN",
                        "languages": ["hi"],
                        "flavor": "hindiNews",
                        "group": "news",
                        "qualityUrls": {},
                        "altNames": ["AajTak"],
                        "sources": ["test"],
                    },
                    {
                        "id": "SonyMarathi.in",
                        "name": "Sony Marathi",
                        "streamUrl": "https://example.test/sony/hd.m3u8",
                        "logoUrl": None,
                        "category": "entertainment",
                        "country": "IN",
                        "languages": ["en"],
                        "flavor": "hindiEntertainment",
                        "group": "entertainment",
                        "qualityUrls": {},
                        "altNames": [],
                        "sources": ["test"],
                    },
                ],
            }
        )
    )

    result = compile_iptv_to_media_ir(source, tmp_path / "out")

    assert result.asset_count == 2
    rows = [json.loads(line) for line in result.media_ir.read_text().splitlines()]
    assert rows[0]["id"] == "iptv_aajtak_in"
    assert rows[0]["type"] == "live_channel"
    assert rows[0]["genres"] == ["news"]
    assert rows[0]["language"] == ["hi"]
    assert rows[0]["availability"] == {"live": True, "playable": True}

    assert "mr" in rows[1]["language"]
    assert rows[1]["region"] == "maharashtra"
    assert rows[1]["quality"] == {"resolution": "hd"}

    report = json.loads(result.report.read_text())
    assert report["asset_count"] == 2
    assert report["genre_counts"]["news"] == 1


def test_compile_m3u_to_media_ir(tmp_path: Path) -> None:
    source = tmp_path / "channels.m3u"
    source.write_text(
        "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="AajTak.in" tvg-name="Aaj Tak" '
                'group-title="news" tvg-country="IN" tvg-language="hi",Aaj Tak',
                "https://example.test/aajtak.m3u8",
                '#EXTINF:-1 tvg-id="SonyMax.in" tvg-name="Sony Max HD" '
                'group-title="movies" tvg-country="IN" tvg-language="hi",Sony Max HD',
                "https://example.test/sonymax/hd.m3u8",
                "",
            ]
        )
    )

    result = compile_iptv_source_to_media_ir(str(source), tmp_path / "out")
    rows = [json.loads(line) for line in result.media_ir.read_text().splitlines()]

    assert result.asset_count == 2
    assert rows[0]["title"] == "Aaj Tak"
    assert rows[0]["genres"] == ["news"]
    assert rows[1]["quality"] == {"resolution": "hd"}
