from __future__ import annotations

import json
import zipfile
from pathlib import Path

from slm_train_eval_publish.iptv_compiler import compile_iptv_source_to_media_ir
from slm_train_eval_publish.pack_compiler import compile_media_pack
from slm_train_eval_publish.pack_validator import validate_media_pack


def test_validate_compiled_iptv_pack(tmp_path: Path) -> None:
    pack_path = _compile_pack(tmp_path)

    result = validate_media_pack(pack_path)

    assert result.valid is True
    assert result.errors == []
    assert result.asset_count == 2
    assert result.manifest is not None
    assert result.manifest["pack"]["id"] == "media.iptv.test"


def test_validate_rejects_corrupted_pack_checksum(tmp_path: Path) -> None:
    pack_path = _compile_pack(tmp_path)
    corrupted = tmp_path / "corrupted.pack"

    with zipfile.ZipFile(pack_path) as source, zipfile.ZipFile(
        corrupted,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "indexes/search.idx":
                payload = json.dumps({"tampered": ["iptv_aajtak_in"]}).encode("utf-8")
            target.writestr(name, payload)

    result = validate_media_pack(corrupted)

    assert result.valid is False
    assert "manifest checksum does not match pack contents" in result.errors


def _compile_pack(tmp_path: Path) -> Path:
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
        ),
        encoding="utf-8",
    )
    ir = compile_iptv_source_to_media_ir(str(source), tmp_path / "ir")
    pack_path = tmp_path / "media.iptv.test-0.1.0.pack"
    compile_media_pack(
        media_ir=ir.media_ir,
        output=pack_path,
        pack_id="media.iptv.test",
        pack_name="Test IPTV",
        compile_report=ir.report,
    )
    return pack_path
