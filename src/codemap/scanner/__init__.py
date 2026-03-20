from __future__ import annotations

import logging
from pathlib import Path

from codemap.config import CodemapConfig
from codemap.models import ScanResult, DatabaseSchema, ApiSchema, DependencySchema, FrontendSchema

logger = logging.getLogger(__name__)


def _glob_files(project_path: Path, patterns: list[str]) -> list[Path]:
    files = []
    for pattern in patterns:
        files.extend(sorted(project_path.glob(pattern)))
    return files


def run_scan(project_path: Path, config: CodemapConfig, targets: set[str]) -> ScanResult:
    scan_all = "all" in targets
    result = ScanResult(project=config.project.name or project_path.name)

    if scan_all or "db" in targets:
        from codemap.scanner.sql_scanner import scan_sql
        sql_files = _glob_files(project_path, config.scan.database.paths)
        tables = scan_sql(sql_files)
        result.database = DatabaseSchema(tables=tables)
        logger.info(f"Scanned {len(sql_files)} SQL files, found {len(tables)} tables")

    if scan_all or "api" in targets or "deps" in targets:
        from codemap.scanner.java_scanner import scan_java
        java_files = _glob_files(project_path, config.scan.backend.paths)
        endpoints, modules = scan_java(java_files)
        if scan_all or "api" in targets:
            result.api = ApiSchema(endpoints=endpoints)
        if scan_all or "deps" in targets:
            result.dependencies.modules = modules
        logger.info(f"Scanned {len(java_files)} Java files")

    if scan_all or "deps" in targets:
        from codemap.scanner.external_scanner import scan_external_calls
        java_files = _glob_files(project_path, config.scan.backend.paths)
        external_calls = scan_external_calls(java_files, config.scan.external.patterns)
        result.dependencies.externalCalls = external_calls

    if scan_all or "frontend" in targets:
        from codemap.scanner.ts_scanner import scan_typescript
        ts_files = _glob_files(project_path, config.scan.frontend.paths)
        components, api_calls = scan_typescript(ts_files)
        result.frontend = FrontendSchema(components=components, apiCalls=api_calls)
        logger.info(f"Scanned {len(ts_files)} TS/TSX files")

    return result
