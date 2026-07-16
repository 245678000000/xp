from __future__ import annotations

from pathlib import Path

from xp.patch import apply_patch_text


def test_add_and_update(tmp_path: Path):
    def resolve(rel: str) -> Path:
        return (tmp_path / rel).resolve()

    def read(p: Path) -> str:
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def write(p: Path, content: str) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    add = """\
*** Begin Patch
*** Add File: hello.txt
+hello
+world
*** End Patch
"""
    r = apply_patch_text(add, resolve=resolve, read_text=read, write_text=write)
    assert r.ok
    assert (tmp_path / "hello.txt").read_text().startswith("hello")

    (tmp_path / "x.py").write_text("a = 1\n", encoding="utf-8")
    upd = """\
*** Update File: x.py
@@
-a = 1
+a = 2
"""
    r2 = apply_patch_text(upd, resolve=resolve, read_text=read, write_text=write)
    assert r2.ok
    assert (tmp_path / "x.py").read_text() == "a = 2\n"


def test_unified_diff(tmp_path: Path):
    (tmp_path / "f.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")

    def resolve(rel: str) -> Path:
        return (tmp_path / rel).resolve()

    def read(p: Path) -> str:
        return p.read_text(encoding="utf-8")

    def write(p: Path, content: str) -> None:
        p.write_text(content, encoding="utf-8")

    patch = """\
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,3 @@
 one
-two
+TWO
 three
"""
    r = apply_patch_text(patch, resolve=resolve, read_text=read, write_text=write)
    assert r.ok, r.message
    assert "TWO" in (tmp_path / "f.txt").read_text()
