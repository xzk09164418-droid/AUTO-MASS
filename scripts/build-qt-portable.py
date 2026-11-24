"""Build a clean Qt portable directory from tracked source and installed dependencies.

Run with the validated Python 3.12 build environment. Never copies user data.
"""

import argparse
import importlib.metadata as metadata
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = args.output.resolve()
    if target.exists():
        raise RuntimeError("Output must be a new directory")
    runtime = args.python_runtime.resolve()
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Use the Python 3.12 build environment")
    tracked = (
        subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
        .decode()
        .split("\0")
    )
    source_roots = {"app", "res", "qt", "scripts", "licenses"}
    source_files = {
        "main.py",
        "child_session_wrapper.py",
        "remote_script_controller.py",
        "LICENSE",
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "README-UPSTREAM.md",
        "README-RELEASE.md",
        "THIRD-PARTY-NOTICES.md",
        "RELEASE-NOTES.md",
        "docs/QT-PORTABLE.md",
    }
    target.mkdir(parents=True)
    for name in tracked:
        if not name:
            continue
        rel = Path(name)
        if rel.parts[0] not in source_roots and name not in source_files:
            continue
        if rel.name == "AGENTS.md" or any(
            p in {"__pycache__", ".agents", "tests", "test"} for p in rel.parts
        ):
            continue
        if rel.suffix.lower() in {".exe", ".pyc", ".pyo"}:
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest)
    shutil.copytree(
        runtime,
        target / "python",
        ignore=shutil.ignore_patterns("site-packages", "__pycache__", "*.pyc", "*.pyo"),
    )
    packages = {
        canonicalize_name(d.metadata["Name"]): d for d in metadata.distributions()
    }
    requirements = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["dependencies"]
    pending = list(requirements) + ["PySide6-Essentials==6.9.3", "pip"]
    seen = {}
    while pending:
        req = Requirement(pending.pop())
        if req.marker and not req.marker.evaluate():
            continue
        name = canonicalize_name(req.name)
        dist = packages[name]
        if req.specifier and dist.version not in req.specifier:
            raise RuntimeError(f"Dependency version mismatch: {req.name}")
        extras = set(req.extras) | {""}
        if name in seen and extras <= seen[name]:
            continue
        seen.setdefault(name, set()).update(extras)
        for child in dist.requires or []:
            dependency = Requirement(child)
            if dependency.marker is None or any(
                dependency.marker.evaluate({"extra": e}) for e in seen[name]
            ):
                dependency.marker = None
                pending.append(str(dependency))
    for name in sorted(seen):
        dist = packages[name]
        base = Path(dist.locate_file("")).resolve()
        for rel in dist.files or []:
            source = Path(dist.locate_file(rel)).resolve()
            if not source.is_relative_to(base) or not source.is_file():
                continue
            relative = source.relative_to(base)
            if relative.parts[:2] in (
                ("Crypto", "SelfTest"),
                ("Cryptodome", "SelfTest"),
            ):
                continue
            if (
                "__pycache__" in source.parts
                or source.suffix in {".pyc", ".pyo"}
                or source.name == "direct_url.json"
            ):
                continue
            dest = target / "python/Lib/site-packages" / source.relative_to(base)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    csc = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    common = [
        str(csc),
        "/nologo",
        "/codepage:65001",
        "/target:winexe",
        "/platform:x64",
        "/optimize+",
        "/r:System.dll",
        "/r:System.Core.dll",
        "/r:System.Drawing.dll",
        "/r:System.Windows.Forms.dll",
    ]
    jobs = [
        (
            "AUTO-MAS.exe",
            [root / "res/Launcher/AutoMassQtLauncher.cs"],
            [f"/win32icon:{root / 'res/icons/AUTO-MAS.ico'}"],
        ),
        (
            "res/ChildSessionHost/AutoMas.ChildSessionHost.exe",
            sorted((root / "res/ChildSessionHost").glob("*.cs")),
            [
                "/r:Microsoft.CSharp.dll",
                f"/win32icon:{root / 'res/icons/AUTO-MAS.ico'}",
                f"/win32manifest:{root / 'res/ChildSessionHost/app.manifest'}",
            ],
        ),
        (
            "res/QueueControlToast/QueueControlToast.exe",
            [root / "res/QueueControlToast/Program.cs"],
            ["/r:System.Web.Extensions.dll"],
        ),
        (
            "res/BackendAgent/AutoMas.BackendAgent.exe",
            [root / "res/BackendAgent/Program.cs"],
            [],
        ),
    ]
    for output, sources, options in jobs:
        subprocess.run(
            common + options + [f"/out:{target / output}"] + [str(p) for p in sources],
            check=True,
        )
    manifest = {
        "sourceCommit": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"]
        )
        .decode()
        .strip(),
        "python": sys.version.split()[0],
        "packages": {n: packages[n].version for n in sorted(seen)},
        "userConfigurationIncluded": False,
    }
    (target / "PACKAGE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (target / "START-HERE.txt").write_text(
        "AUTO-MASS 0.1.0 Qt / Windows x64\n\nExtract the complete directory to a writable location, then run AUTO-MAS.exe.\nPython 3.12, Qt Essentials and backend production dependencies are included.\nNo Node.js installation is required. Optional Qt 3D enhancement is not included.\nNo user configuration, login credentials, logs or recovery state is included.\nWindows RDP and .NET Framework are OS components; external scripts, games and UU are not included.\nThe Qt/RDP exit cleanup path has not been validated against real running tasks.\nClosing the Qt window keeps the tray and backend running. Use the tray menu for complete shutdown.\nSource and license: https://github.com/xzk09164418-droid/AUTO-MASS\n",
        encoding="utf-8",
    )
    print(json.dumps({"directory": str(target), "packages": len(seen)}))


if __name__ == "__main__":
    main()
