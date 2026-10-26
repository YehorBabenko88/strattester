"""Pinned, task-private, deterministic Windows x64 .NET Framework broker build.

Only downloads official NuGet compiler/reference packages, verifies bytes BEFORE
extraction/execution, and builds source twice. No global install or native tests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

PACKAGES = (
    ("microsoft.net.compilers", "3.11.0", "e4a540a9cb41d15e6e1cc05fa2cadb847454df9ebe49d683cded2780506ef880"),
    ("microsoft.netframework.referenceassemblies.net472", "1.0.3", "ffa0a5570a39f911399164d0581ffddef99b5e3dfbaa5f220e5ce22969bcf57c"),
)


def sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_verified(archive, expected, destination):
    if sha256(archive) != expected:
        raise ValueError("compiler/reference package SHA256 mismatch")
    with zipfile.ZipFile(archive) as package:
        # NuGet official archives only; reject extraction escapes even after hash check.
        for item in package.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("unsafe package member")
        package.extractall(destination)


def build(root, output, cache):
    if os.name != "nt":
        raise RuntimeError("Windows build requires .NET Framework 4.7.2+")
    cache.mkdir(parents=True, exist_ok=True)
    unpacked = []
    for name, version, digest in PACKAGES:
        archive = cache / (name + "." + version + ".nupkg")
        if not archive.exists():
            url = f"https://api.nuget.org/v3-flatcontainer/{name}/{version}/{name}.{version}.nupkg"
            with urllib.request.urlopen(url, timeout=90) as response:
                with archive.open("wb") as stream:
                    shutil.copyfileobj(response, stream)
        # Re-extract verified input on each build; never execute stale cache binaries.
        destination = cache / (name + "." + version)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir()
        extract_verified(archive, digest, destination)
        unpacked.append(destination)
    compiler = unpacked[0] / "tools/csc.exe"
    references = unpacked[1] / "build/.NETFramework/v4.7.2"
    output.mkdir(parents=True, exist_ok=True)
    source = root / "native/windows/Broker.cs"
    binaries = []
    with tempfile.TemporaryDirectory(prefix="native-rebuild-", dir=output) as scratch:
        for iteration in ("one", "two"):
            folder = Path(scratch) / iteration
            folder.mkdir()
            binary = folder / "StratTester.Native.exe"
            command = [str(compiler), "/nologo", "/noconfig", "/nostdlib+", "/target:exe",
                       "/platform:x64", "/optimize+", "/deterministic+", "/debug-",
                       "/warnaserror+", "/langversion:7.3", "/out:" + str(binary),
                       "/reference:" + str(references / "mscorlib.dll"),
                       "/reference:" + str(references / "System.dll"), str(source)]
            subprocess.run(command, check=True, cwd=root)
            binaries.append(binary.read_bytes())
        if binaries[0] != binaries[1]:
            raise RuntimeError("deterministic rebuild mismatch")
    target = output / "StratTester.Native.exe"
    target.write_bytes(binaries[0])
    manifest = {"schema": 1, "binary_sha256": sha256(target), "source_sha256": sha256(source),
                "deterministic_rebuild_equal": True, "target": "net472-windows-x64",
                "packages": [{"id": n, "version": v, "sha256": h} for n, v, h in PACKAGES],
                "native_enforcement": False, "component_tests": "NOTRUN", "research_execution": "BLOCKED"}
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output.resolve(), args.cache.resolve())
