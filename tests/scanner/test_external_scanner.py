from pathlib import Path

from codemap.scanner.external_scanner import scan_external_calls
from codemap.config import DEFAULT_CONFIG

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_external_calls():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    assert len(calls) >= 2


def test_scan_external_gdal():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    gdal_calls = [c for c in calls if c.type == "gdal" or "gdal_translate" in c.command]
    assert len(gdal_calls) >= 1
    assert gdal_calls[0].source.endswith(".convert") or "GdalService" in gdal_calls[0].source


def test_scan_external_python():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    python_calls = [c for c in calls if c.type == "python" or "python" in c.command]
    assert len(python_calls) >= 1


def test_scan_external_empty():
    calls = scan_external_calls([], DEFAULT_CONFIG.scan.external.patterns)
    assert calls == []
