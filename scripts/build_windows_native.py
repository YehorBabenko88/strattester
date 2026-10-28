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
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

PACKAGES = (
    ("microsoft.net.compilers", "3.11.0", "e4a540a9cb41d15e6e1cc05fa2cadb847454df9ebe49d683cded2780506ef880"),
    ("microsoft.netframework.referenceassemblies.net472", "1.0.3", "ffa0a5570a39f911399164d0581ffddef99b5e3dfbaa5f220e5ce22969bcf57c"),
    ("bouncycastle.cryptography", "2.7.0", "f091ffccab4d03993e660bace277659a79dee0972f54d7f1f4bd46d680966241"),
)


def sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_snapshot(root):
    """Compile immutable Git objects, never a mutable working-tree glob."""
    def git(*args, binary=False):
        # Replacement refs can change blob bytes while retaining the original
        # source/tree IDs. Read the actual objects named by the captured commit.
        result = subprocess.run(['git', '--no-replace-objects', '-C', str(root), *args], check=True, capture_output=True)
        return result.stdout if binary else result.stdout.decode().strip()
    head = git('rev-parse', 'HEAD')
    tree = git('rev-parse', head + '^{tree}')
    if any(len(s) != 40 or any(c not in '0123456789abcdef' for c in s) for s in (head, tree)):
        raise ValueError('invalid Git source identity')
    names = git('ls-tree', '-r', '--name-only', head, 'native/windows', 'scripts/build_windows_native.py').splitlines()
    names = [n for n in names if n.endswith('.cs') or n == 'scripts/build_windows_native.py']
    if 'native/windows/Broker.cs' not in names or 'scripts/build_windows_native.py' not in names:
        raise ValueError('versioned native source required')
    files = {n: git('show', head + ':' + n, binary=True) for n in names}
    dirty = bool(git('status', '--porcelain'))
    actual = {p.relative_to(root).as_posix() for p in (root/'native/windows').glob('*.cs')}
    if actual != {n for n in names if n.endswith('.cs')}:
        dirty = True
    for name, expected in files.items():
        path = root/name
        if not path.is_file() or path.read_bytes().replace(b'\r\n', b'\n') != expected.replace(b'\r\n', b'\n'):
            dirty = True
    return dict(source_sha=head, tree_sha=tree, dirty=dirty), files


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


def remove_cached_package(cache, destination):
    """Delete only a checked direct child; never follow a junction/symlink."""
    cache_root = cache.resolve(strict=True)
    resolved = destination.resolve(strict=True)
    if resolved == cache_root or resolved.parent != cache_root:
        raise ValueError("cache cleanup target is outside the intended cache")
    attributes = destination.lstat()
    if destination.is_symlink() or getattr(attributes, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise ValueError("cache cleanup refuses reparse/symlink targets")
    if not destination.is_dir():
        raise ValueError("cache cleanup requires an ordinary directory")
    shutil.rmtree(destination)


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
            remove_cached_package(cache, destination)
        destination.mkdir()
        extract_verified(archive, digest, destination)
        unpacked.append(destination)
    compiler = unpacked[0] / "tools/csc.exe"
    references = unpacked[1] / "build/.NETFramework/v4.7.2"
    crypto = unpacked[2] / "lib/net461/BouncyCastle.Cryptography.dll"
    identity, objects = source_snapshot(root)
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(name for name in objects if name.endswith('.cs'))
    binaries = []
    with tempfile.TemporaryDirectory(prefix="native-rebuild-", dir=output) as scratch:
        snapshot = Path(scratch)/'source'
        for name, data in objects.items():
            path = snapshot/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        context = Path(scratch) / 'BuildIdentity.cs'
        context.write_text('namespace StratTester.Native { internal static class BuildIdentity {'
            + 'internal const string SourceSha="' + identity['source_sha'] + '";'
            + 'internal const string TreeSha="' + identity['tree_sha'] + '";'
            + 'internal static readonly bool Dirty=' + str(identity['dirty']).lower() + ';'
            + 'internal const string CryptoSha256="' + sha256(crypto) + '";}}', encoding='ascii')
        for iteration in ("one", "two"):
            folder = Path(scratch) / iteration
            folder.mkdir()
            binary = folder / "StratTester.Native.exe"
            command = [str(compiler), "/nologo", "/noconfig", "/nostdlib+", "/target:exe",
                       "/platform:x64", "/optimize+", "/deterministic+", "/debug-",
                       "/warnaserror+", "/langversion:7.3", "/out:" + str(binary),
                       "/reference:" + str(references / "mscorlib.dll"),
                       "/reference:" + str(references / "System.dll"),
                       "/resource:" + str(crypto) + ",StratTester.BouncyCastle.dll", str(context)] + [str(snapshot/name) for name in sources]
            subprocess.run(command, check=True, cwd=root)
            binaries.append(binary.read_bytes())
        if binaries[0] != binaries[1]:
            raise RuntimeError("deterministic rebuild mismatch")
    target = output / "StratTester.Native.exe"
    target.write_bytes(binaries[0])
    manifest = {"schema": 1, "binary_sha256": sha256(target), "source_sha256": hashlib.sha256(objects['native/windows/Broker.cs']).hexdigest(),
                "sources": {name: hashlib.sha256(objects[name]).hexdigest() for name in sources},
                "deterministic_rebuild_equal": True, "target": "net472-windows-x64",
                "packages": [{"id": n, "version": v, "sha256": h} for n, v, h in PACKAGES],
                "native_enforcement": False, "component_tests": "NOTRUN", "research_execution": "BLOCKED"}
    manifest.update(identity)
    manifest['embedded_verifier_sha256'] = sha256(crypto)
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output.resolve(), args.cache.resolve())
