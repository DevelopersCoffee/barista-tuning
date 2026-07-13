from __future__ import annotations

from pathlib import Path

import pytest

from slm_train_eval_publish.android_ffi_packager import (
    build_android_edge_ffi,
    package_android_edge_ffi,
    parse_abi_artifact,
)


def test_parse_abi_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "libedge_ffi.so"
    artifact.write_bytes(b"edge-ffi")

    abi, path = parse_abi_artifact(f"arm64-v8a={artifact}")

    assert abi == "arm64-v8a"
    assert path == artifact


def test_parse_abi_artifact_rejects_unknown_abi(tmp_path: Path) -> None:
    artifact = tmp_path / "libedge_ffi.so"
    artifact.write_bytes(b"edge-ffi")

    with pytest.raises(ValueError, match="unsupported Android ABI"):
        parse_abi_artifact(f"mips={artifact}")


def test_package_android_edge_ffi_from_flutter_app_root(tmp_path: Path) -> None:
    flutter_app = tmp_path / "airo" / "app"
    (flutter_app / "android" / "app" / "src" / "main").mkdir(parents=True)
    artifact = tmp_path / "libedge_ffi.so"
    artifact.write_bytes(b"edge-ffi")

    result = package_android_edge_ffi(
        airo_app=flutter_app,
        artifacts={"arm64-v8a": artifact},
    )

    packaged = (
        flutter_app
        / "android"
        / "app"
        / "src"
        / "main"
        / "jniLibs"
        / "arm64-v8a"
        / "libedge_ffi.so"
    )
    assert result.jni_libs_root == packaged.parents[1]
    assert result.copied == {"arm64-v8a": packaged}
    assert packaged.read_bytes() == b"edge-ffi"


def test_package_android_edge_ffi_from_android_module_path(tmp_path: Path) -> None:
    android_module = tmp_path / "app" / "android" / "app"
    (android_module / "src" / "main").mkdir(parents=True)
    (android_module / "build.gradle.kts").write_text("plugins {}", encoding="utf-8")
    artifact = tmp_path / "libedge_ffi.so"
    artifact.write_bytes(b"edge-ffi")

    result = package_android_edge_ffi(
        airo_app=android_module,
        artifacts={"x86_64": artifact},
    )

    packaged = android_module / "src" / "main" / "jniLibs" / "x86_64" / "libedge_ffi.so"
    assert result.copied == {"x86_64": packaged}
    assert packaged.read_bytes() == b"edge-ffi"


def test_build_android_edge_ffi_discovers_ndk_from_flutter_local_properties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flutter_app = tmp_path / "airo" / "app"
    (flutter_app / "android" / "app" / "src" / "main").mkdir(parents=True)
    ndk_dir = tmp_path / "android-sdk" / "ndk" / "28.2.13676358"
    ndk_dir.mkdir(parents=True)
    (flutter_app / "android" / "local.properties").write_text(
        f"sdk.dir={tmp_path / 'android-sdk'}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANDROID_NDK_HOME", raising=False)
    monkeypatch.delenv("ANDROID_NDK_ROOT", raising=False)
    monkeypatch.delenv("NDK_HOME", raising=False)
    captured_env: dict[str, str] = {}

    def fake_run(command: list[str], **kwargs: object) -> None:
        captured_env.update(kwargs["env"])  # type: ignore[arg-type]
        output = Path(command[command.index("-o") + 1])
        artifact = output / "arm64-v8a" / "libedge_ffi.so"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"edge-ffi")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = build_android_edge_ffi(
        repo_root=tmp_path,
        airo_app=flutter_app,
        abis=["arm64-v8a"],
    )

    assert captured_env["ANDROID_NDK_HOME"] == str(ndk_dir)
    assert result.copied["arm64-v8a"].read_bytes() == b"edge-ffi"
