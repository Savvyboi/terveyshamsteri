import json

from terveyshamsteri.__main__ import main


def _regions(tmp_path, capsys, *args):
    (tmp_path / "a.yaml").write_text("id: a\nenabled: true\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("id: b\nenabled: true\nrunner: local\n", encoding="utf-8")
    (tmp_path / "c.yaml").write_text("id: c\nenabled: false\nrunner: local\n", encoding="utf-8")
    assert main(["--regions-dir", str(tmp_path), "regions", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_regions_cloud_skips_local(tmp_path, capsys):
    assert _regions(tmp_path, capsys) == ["a"]


def test_regions_local(tmp_path, capsys):
    assert _regions(tmp_path, capsys, "--runner", "local") == ["b"]
