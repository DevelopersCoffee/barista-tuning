from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ANDROID_ABIS = {
    "arm64-v8a": "aarch64-linux-android",
    "armeabi-v7a": "armv7-linux-androideabi",
    "x86_64": "x86_64-linux-android",
    "x86": "i686-linux-android",
}


@dataclass(frozen=True)
class AndroidFfiPackageResult:
    jni_libs_root: Path
    copied: dict[str, Path]


def parse_abi_artifact(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError("artifact must use ABI=PATH format")
    abi, artifact = spec.split("=", 1)
    abi = abi.strip()
    if abi not in ANDROID_ABIS:
        raise ValueError(f"unsupported Android ABI: {abi}")
    artifact_path = Path(artifact.strip()).expanduser()
    if not artifact_path.is_file():
        raise FileNotFoundError(f"edge-ffi artifact not found: {artifact_path}")
    return abi, artifact_path


def package_android_edge_ffi(
    airo_app: Path,
    artifacts: dict[str, Path],
) -> AndroidFfiPackageResult:
    if not artifacts:
        raise ValueError("at least one ABI artifact is required")

    jni_libs_root = _jni_libs_root(airo_app)
    copied: dict[str, Path] = {}
    for abi, artifact in artifacts.items():
        if abi not in ANDROID_ABIS:
            raise ValueError(f"unsupported Android ABI: {abi}")
        if not artifact.is_file():
            raise FileNotFoundError(f"edge-ffi artifact not found: {artifact}")
        destination = jni_libs_root / abi / "libedge_ffi.so"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact, destination)
        copied[abi] = destination

    return AndroidFfiPackageResult(jni_libs_root=jni_libs_root, copied=copied)


def build_android_edge_ffi(
    repo_root: Path,
    airo_app: Path,
    abis: list[str],
    release: bool = True,
    cargo: str = "cargo",
) -> AndroidFfiPackageResult:
    if not abis:
        raise ValueError("at least one ABI is required")
    for abi in abis:
        if abi not in ANDROID_ABIS:
            raise ValueError(f"unsupported Android ABI: {abi}")

    jni_libs_root = _jni_libs_root(airo_app)
    command = [cargo, "ndk"]
    for abi in abis:
        command.extend(["-t", abi])
    command.extend(["-o", str(jni_libs_root), "build", "-p", "edge-ffi"])
    if release:
        command.append("--release")

    env = os.environ.copy()
    if not any(env.get(name) for name in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT", "NDK_HOME")):
        ndk_home = _discover_android_ndk(airo_app)
        if ndk_home is not None:
            env["ANDROID_NDK_HOME"] = str(ndk_home)

    try:
        subprocess.run(command, cwd=repo_root, env=env, check=True)
    except FileNotFoundError as error:
        raise RuntimeError("cargo was not found while packaging edge-ffi") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "failed to build edge-ffi for Android; install cargo-ndk and Android NDK"
        ) from error

    copied = {
        abi: jni_libs_root / abi / "libedge_ffi.so"
        for abi in abis
        if (jni_libs_root / abi / "libedge_ffi.so").is_file()
    }
    missing = sorted(set(abis) - set(copied))
    if missing:
        raise FileNotFoundError(
            "cargo-ndk finished but did not produce libedge_ffi.so for: "
            + ", ".join(missing)
        )

    return AndroidFfiPackageResult(jni_libs_root=jni_libs_root, copied=copied)


def _jni_libs_root(airo_app: Path) -> Path:
    app = airo_app.expanduser().resolve()
    android_app_module = app / "android" / "app"
    if (android_app_module / "src" / "main").is_dir():
        return android_app_module / "src" / "main" / "jniLibs"

    if (app / "src" / "main").is_dir() and (
        (app / "build.gradle").is_file() or (app / "build.gradle.kts").is_file()
    ):
        return app / "src" / "main" / "jniLibs"

    raise FileNotFoundError(
        "could not locate Android app module; pass the Flutter app root "
        "or the android/app module path"
    )


def _discover_android_ndk(airo_app: Path) -> Path | None:
    for ndk_dir in _ndk_dirs_from_local_properties(airo_app):
        if ndk_dir.is_dir():
            return ndk_dir

    for sdk_env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_dir = os.environ.get(sdk_env)
        if sdk_dir:
            ndk_dir = _latest_ndk_under(Path(sdk_dir).expanduser())
            if ndk_dir is not None:
                return ndk_dir

    return None


def _ndk_dirs_from_local_properties(airo_app: Path) -> list[Path]:
    app = airo_app.expanduser().resolve()
    local_properties_candidates = [
        app / "android" / "local.properties",
        app / "local.properties",
        app.parent / "local.properties",
        app.parent.parent / "local.properties",
    ]

    ndk_dirs: list[Path] = []
    for local_properties in dict.fromkeys(local_properties_candidates):
        if not local_properties.is_file():
            continue

        properties = _read_local_properties(local_properties)
        if ndk_dir := properties.get("ndk.dir"):
            ndk_dirs.append(Path(ndk_dir).expanduser())
        if sdk_dir := properties.get("sdk.dir"):
            latest_ndk = _latest_ndk_under(Path(sdk_dir).expanduser())
            if latest_ndk is not None:
                ndk_dirs.append(latest_ndk)

    return ndk_dirs


def _read_local_properties(path: Path) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        properties[key.strip()] = value.strip()
    return properties


def _latest_ndk_under(sdk_dir: Path) -> Path | None:
    ndk_root = sdk_dir / "ndk"
    if not ndk_root.is_dir():
        return None
    versions = sorted((path for path in ndk_root.iterdir() if path.is_dir()), reverse=True)
    return versions[0] if versions else None
