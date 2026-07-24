import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_default_neutral_portraits_are_committed_with_fallbacks():
    manifest = json.loads((ROOT / "assets" / "manifest.json").read_text())
    expected = {"hana", "rei", "mira", "kagura"}
    portraits = [item for item in manifest["objects"] if item["kind"] == "canonical-neutral-portrait"]

    assert {item["character"] for item in portraits} == expected
    assert all(item["fallback"] == "web/src/styles.css#cast-portrait" for item in portraits)
    assert all((ROOT / item["path"]).is_file() for item in portraits)
