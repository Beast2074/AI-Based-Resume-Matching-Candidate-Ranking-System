"""
Bundle size calculator for Vercel deployment limits.
Verifies that backend code + bundled models + production dependencies <= 350 MB.
"""
import sys
import os
from pathlib import Path
import importlib.metadata
try:
    import tomllib
except ImportError:
    import tomli as tomllib

def get_dir_size_mb(path: Path, exclude_names=None) -> float:
    if not path.exists():
        return 0.0
    if exclude_names is None:
        exclude_names = {".venv", "venv", "__pycache__", ".pytest_cache", ".git"}
    
    total_bytes = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude_names]
        for f in files:
            fp = Path(root) / f
            try:
                if not fp.is_symlink():
                    total_bytes += fp.stat().st_size
            except OSError:
                pass
    return total_bytes / (1024 * 1024)

def check_bundle_size():
    base_dir = Path(__file__).resolve().parent.parent
    backend_dir = base_dir / "backend"
    pyproject_path = backend_dir / "pyproject.toml"
    
    # 1. Read production dependencies from pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    
    prod_raw_deps = pyproject.get("project", {}).get("dependencies", [])
    direct_deps = [
        d.split(">=")[0].split("<")[0].split("==")[0].split("[")[0].strip()
        for d in prod_raw_deps
    ]
    
    # 2. Trace all production dependency distributions transitively
    visited = set()
    to_visit = list(direct_deps)
    while to_visit:
        dep = to_visit.pop(0)
        canonical = dep.lower().replace("-", "_")
        if canonical in visited:
            continue
        visited.add(canonical)
        try:
            dist = importlib.metadata.distribution(dep)
            if dist.requires:
                for req in dist.requires:
                    if "extra ==" not in req:
                        req_name = (
                            req.split(" ")[0]
                            .split(";")[0]
                            .split(">=")[0]
                            .split("<")[0]
                            .split("==")[0]
                            .split("[")[0]
                            .strip()
                            .lower()
                            .replace("-", "_")
                        )
                        if req_name and req_name not in visited:
                            to_visit.append(req_name)
        except Exception:
            pass

    # 3. Locate site-packages in local environment
    site_packages = None
    for candidate in [
        base_dir / ".venv" / "Lib" / "site-packages",
        backend_dir / ".venv" / "Lib" / "site-packages",
        base_dir / ".venv" / "lib",
        backend_dir / ".venv" / "lib",
    ]:
        if candidate.exists():
            if candidate.name == "lib":
                for sp in candidate.glob("python*/site-packages"):
                    if sp.exists():
                        site_packages = sp
                        break
            else:
                site_packages = candidate
                break

    prod_deps_bytes = 0
    if site_packages and site_packages.exists():
        for d in visited:
            try:
                dist = importlib.metadata.distribution(d)
                if dist.files:
                    for f in dist.files:
                        fp = site_packages / f
                        if fp.exists() and fp.is_file():
                            prod_deps_bytes += fp.stat().st_size
            except Exception:
                pass

    prod_deps_mb = prod_deps_bytes / (1024 * 1024)
    backend_code_mb = get_dir_size_mb(backend_dir / "app")
    models_mb = get_dir_size_mb(backend_dir / "models")
    total_bundle_mb = backend_code_mb + models_mb + prod_deps_mb

    print("=" * 60)
    print("TALENTRANK BACKEND BUNDLE SIZE AUDIT")
    print("=" * 60)
    print(f"Backend application code:          {backend_code_mb:.2f} MB")
    print(f"Bundled ONNX model (backend/models):{models_mb:.2f} MB")
    print(f"Production dependencies ({len(visited)} pkgs): {prod_deps_mb:.2f} MB")
    print("-" * 60)
    print(f"Total production bundle size:      {total_bundle_mb:.2f} MB")
    print(f"Vercel Hard Limit:                500.00 MB")
    print(f"TalentRank Safety Limit:          350.00 MB")
    print("=" * 60)

    SAFETY_LIMIT_MB = 350.0
    if total_bundle_mb > SAFETY_LIMIT_MB:
        print(f"FAILED: Bundle size ({total_bundle_mb:.2f} MB) exceeds limit ({SAFETY_LIMIT_MB} MB)!")
        sys.exit(1)
    else:
        print(f"PASSED: Bundle size is safely within the {SAFETY_LIMIT_MB} MB limit.")
        sys.exit(0)

if __name__ == "__main__":
    check_bundle_size()
