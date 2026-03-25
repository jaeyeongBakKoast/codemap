# src/codemap/config.py
from __future__ import annotations

import os
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


class AiConfig(BaseModel):
    enabled: bool = True
    base_url: str = Field(default_factory=lambda: os.getenv("CODEMAP_AI_URL", ""))
    model: str = Field(default_factory=lambda: os.getenv("CODEMAP_AI_MODEL", ""))
    language: str = "ko"


class CodemapConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    ai: AiConfig = Field(default_factory=AiConfig)


DEFAULT_CONFIG = CodemapConfig()


def _auto_detect(project_path: Path) -> dict:
    """Auto-detect project structure when no config file exists."""
    data: dict = {"scan": {}}

    # --- Project name ---
    data["project"] = {"name": project_path.name}

    # --- SQL: search common DDL locations ---
    sql_patterns: list[str] = []
    for candidate in ["doc/database", "db", "sql", "database"]:
        if (project_path / candidate).is_dir():
            sql_patterns.append(f"{candidate}/**/*.sql")
    if not sql_patterns:
        # Fallback: any .sql anywhere
        if list(project_path.glob("**/*.sql"))[:1]:
            sql_patterns = ["**/*.sql"]
    if sql_patterns:
        data["scan"]["database"] = {"paths": sql_patterns}

    # --- Java: detect Gradle/Maven projects ---
    java_patterns: list[str] = []
    gradle_or_maven = (
        list(project_path.glob("**/build.gradle*"))
        + list(project_path.glob("**/pom.xml"))
    )
    if gradle_or_maven:
        # Find all src/main/java directories relative to project root
        java_src_dirs = sorted(project_path.glob("**/src/main/java"))
        for java_dir in java_src_dirs:
            rel = java_dir.relative_to(project_path)
            java_patterns.append(f"{rel}/**/*.java")
    if java_patterns:
        data["scan"]["backend"] = {"paths": java_patterns, "framework": "spring"}

    # --- Frontend: detect package.json with src/ ---
    ts_patterns: list[str] = []
    for pkg_json in sorted(project_path.glob("**/package.json")):
        pkg_dir = pkg_json.parent
        src_dir = pkg_dir / "src"
        if src_dir.is_dir():
            rel = src_dir.relative_to(project_path)
            ts_patterns.append(f"{rel}/**/*.ts")
            ts_patterns.append(f"{rel}/**/*.tsx")
    if ts_patterns:
        data["scan"]["frontend"] = {"paths": ts_patterns, "framework": "react"}

    return data


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
        # No config found — auto-detect project structure
        auto_data = _auto_detect(project_path)
        if auto_data.get("scan"):
            return CodemapConfig(**auto_data)
        return DEFAULT_CONFIG

    return CodemapConfig(**base_data)
