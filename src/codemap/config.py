# src/codemap/config.py
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    name: str = ""
    description: str = ""


class DatabaseScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["doc/database/**/*.sql"])


class BackendScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["src/main/java/**/*.java"])
    framework: str = "spring"


class FrontendScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: [
        "src/frontend/**/*.ts",
        "src/frontend/**/*.tsx",
    ])
    framework: str = "react"


class ExternalPattern(BaseModel):
    type: str
    keywords: list[str]


class ExternalScanConfig(BaseModel):
    patterns: list[ExternalPattern] = Field(
        default_factory=lambda: [
            ExternalPattern(type="process", keywords=["ProcessBuilder", "Runtime.exec"]),
            ExternalPattern(type="python", keywords=["python", "python3"]),
            ExternalPattern(type="gdal", keywords=["gdal_translate", "ogr2ogr"]),
        ]
    )


class ScanConfig(BaseModel):
    database: DatabaseScanConfig = Field(default_factory=DatabaseScanConfig)
    backend: BackendScanConfig = Field(default_factory=BackendScanConfig)
    frontend: FrontendScanConfig = Field(default_factory=FrontendScanConfig)
    external: ExternalScanConfig = Field(default_factory=ExternalScanConfig)


class ExportConfig(BaseModel):
    template: str = "minimal"
    logo: str = ""


class CodemapConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)


DEFAULT_CONFIG = CodemapConfig()


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    project_path: Path,
    config_filename: str = ".codemap/config.yaml",
) -> CodemapConfig:
    config_file = project_path / config_filename
    global_config_file = Path.home() / ".codemap" / "config.yaml"

    base_data: dict = {}
    if global_config_file.exists():
        with open(global_config_file) as f:
            base_data = yaml.safe_load(f) or {}

    if config_file.exists():
        with open(config_file) as f:
            project_data = yaml.safe_load(f) or {}
        base_data = _deep_merge(base_data, project_data)

    if not base_data:
        return DEFAULT_CONFIG

    return CodemapConfig(**base_data)
