import io

from stage0_launch.launchpad_compare import compare_launchpads


def test_compare_identical(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "f.txt").write_text("x", encoding="utf-8")
    (b / "f.txt").write_text("x", encoding="utf-8")
    buf = io.StringIO()
    assert compare_launchpads(a, b, out=buf) == 0
    assert "OK" in buf.getvalue()


def test_compare_differs(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "f.txt").write_text("x", encoding="utf-8")
    (b / "f.txt").write_text("y", encoding="utf-8")
    assert compare_launchpads(a, b) == 1


def test_compare_ignores_git(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "f.txt").write_text("x", encoding="utf-8")
    (b / "f.txt").write_text("x", encoding="utf-8")
    (a / ".git" / "config").parent.mkdir(parents=True)
    (a / ".git" / "config").write_text("x", encoding="utf-8")
    (b / ".git" / "config").parent.mkdir(parents=True)
    (b / ".git" / "config").write_text("different", encoding="utf-8")
    assert compare_launchpads(a, b) == 0


def test_compare_ignore_file(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "secret.env").write_text("1", encoding="utf-8")
    (b / "secret.env").write_text("2", encoding="utf-8")
    ign = tmp_path / "ignore"
    ign.write_text("secret.env\n", encoding="utf-8")
    assert compare_launchpads(a, b, ignore_file=ign) == 0


def test_compare_ignores_dependency_lock_basenames(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "f.txt").write_text("x", encoding="utf-8")
    (b / "f.txt").write_text("x", encoding="utf-8")
    (a / "Pipfile.lock").write_text("aaa", encoding="utf-8")
    (b / "Pipfile.lock").write_text("bbb", encoding="utf-8")
    (a / "package-lock.json").write_text("1", encoding="utf-8")
    (b / "package-lock.json").write_text("2", encoding="utf-8")
    assert compare_launchpads(a, b) == 0


def test_compare_respects_gitignore(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / ".gitignore").write_text("*.secret\n", encoding="utf-8")
    (b / ".gitignore").write_text("*.secret\n", encoding="utf-8")
    (a / "real.txt").write_text("ok", encoding="utf-8")
    (b / "real.txt").write_text("ok", encoding="utf-8")
    (a / "hidden.secret").write_text("1", encoding="utf-8")
    (b / "hidden.secret").write_text("2", encoding="utf-8")
    buf = io.StringIO()
    assert compare_launchpads(a, b, out=buf) == 0
    assert "OK" in buf.getvalue()
