# src/codemap/scanner/external_scanner.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from codemap.config import ExternalPattern
from codemap.models import ExternalCall

logger = logging.getLogger(__name__)

# Regex to find class declarations
_CLASS_RE = re.compile(r"\bclass\s+(\w+)")

# Regex to find method declarations
_METHOD_RE = re.compile(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(")

# Regex to detect start of ProcessBuilder or Runtime.exec on a line
_PROCESS_BUILDER_START_RE = re.compile(r"new\s+ProcessBuilder\s*\(")
_RUNTIME_EXEC_START_RE = re.compile(r"Runtime\.getRuntime\(\)\.exec\s*\(")


def scan_external_calls(
    files: list[Path],
    patterns: list[ExternalPattern],
) -> list[ExternalCall]:
    """Scan Java files for external process invocations."""
    if not files:
        return []

    calls: list[ExternalCall] = []

    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            continue

        lines = source.splitlines()
        class_name = _find_class_name(source)

        for i, line in enumerate(lines, start=1):
            detected_keyword: str | None = None

            if _PROCESS_BUILDER_START_RE.search(line):
                detected_keyword = "ProcessBuilder"
            elif _RUNTIME_EXEC_START_RE.search(line):
                detected_keyword = "exec"

            if detected_keyword:
                command_str = _extract_multiline_args(lines, i - 1, detected_keyword)
                method_name = _find_enclosing_method(lines, i - 1)
                source_label = _make_source(class_name, method_name)
                call_type = _classify(command_str, patterns)
                calls.append(
                    ExternalCall(
                        source=source_label,
                        type=call_type,
                        command=command_str,
                        file=str(file_path),
                        line=i,
                    )
                )

    return calls


def _find_class_name(source: str) -> str:
    match = _CLASS_RE.search(source)
    return match.group(1) if match else "Unknown"


def _find_enclosing_method(lines: list[str], line_idx: int) -> str:
    """Walk backwards from line_idx to find the nearest method declaration."""
    for i in range(line_idx, -1, -1):
        match = _METHOD_RE.search(lines[i])
        if match:
            return match.group(1)
    return "unknown"


def _make_source(class_name: str, method_name: str) -> str:
    return f"{class_name}.{method_name}"


def _extract_multiline_args(lines: list[str], start_idx: int, keyword: str) -> str:
    """Extract the argument string from a call that may span multiple lines."""
    # Join from start line onward
    combined = " ".join(lines[start_idx : start_idx + 10])

    # Find the keyword and then extract balanced parens
    if keyword == "ProcessBuilder":
        match = re.search(r"new\s+ProcessBuilder\s*\(", combined)
    elif keyword == "exec":
        match = re.search(r"\.exec\s*\(", combined)
    else:
        return ""

    if not match:
        return ""

    # Find the balanced closing paren starting after the opening paren
    open_pos = match.end() - 1  # position of '('
    depth = 0
    end_pos = open_pos
    for j in range(open_pos, len(combined)):
        if combined[j] == "(":
            depth += 1
        elif combined[j] == ")":
            depth -= 1
            if depth == 0:
                end_pos = j
                break

    raw = combined[open_pos + 1 : end_pos].strip()

    # Extract string literals from the args
    strings = re.findall(r'"([^"]*)"', raw)
    if strings:
        return " ".join(strings)
    return raw


def _classify(command: str, patterns: list[ExternalPattern]) -> str:
    """Classify a command string using the configured patterns.

    More specific patterns (gdal, python) are checked before generic ones (process).
    """
    # Sort so that specific types come first (non-"process" types first)
    sorted_patterns = sorted(patterns, key=lambda p: (p.type == "process", p.type))

    for pattern in sorted_patterns:
        for keyword in pattern.keywords:
            if keyword.lower() in command.lower():
                return pattern.type
    return "process"
