# Publishing xp

Package name on PyPI: **`xp-harness`**  
CLI entry point: **`xp`**

## One-time: Trusted Publisher (recommended)

1. Create a PyPI project (or first upload creates it).
2. PyPI → Account settings → Publishing → **Add a new pending publisher**:
   - Owner: `245678000000`
   - Repository: `xp`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. On GitHub: Settings → Environments → create **`pypi`** (optional protection rules).

## Release steps

```bash
# 1. Bump version in src/xp/__init__.py  (e.g. 0.7.0)
# 2. Update CHANGELOG.md
# 3. Commit & push main
git tag v0.7.0
git push origin v0.7.0
```

Tag push runs `.github/workflows/publish.yml`: test → build → PyPI → GitHub Release.

## Install from PyPI (after first publish)

```bash
pip install xp-harness
xp --version
```

## Install from Git (always works)

```bash
pip install -U "git+https://github.com/245678000000/xp.git"
```

## Local build check

```bash
bash scripts/sync_data.sh
pip install build
python -m build
ls dist/
```
