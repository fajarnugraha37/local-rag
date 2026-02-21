from __future__ import annotations

from app.config.runtime_settings import load_settings


def test_docling_defaults_are_present(tmp_path) -> None:
    cfg = load_settings(config_file=str(tmp_path / "missing-config.yaml"))
    assert cfg["ingest_docling_enabled"] is True
    assert cfg["ingest_docling_export_format"] == "markdown"
    assert cfg["ingest_docling_device"] == "cpu"
    assert cfg["ingest_docling_enable_ocr"] is False
    assert cfg["ingest_docling_timeout_s"] == 30
    assert cfg["ingest_docling_max_pages"] == 200
    assert cfg["ingest_docling_max_slides"] == 300
    assert cfg["ingest_docling_max_tables"] == 2000
    assert cfg["ingest_docling_max_images"] == 200
