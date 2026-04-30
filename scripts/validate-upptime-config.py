#!/usr/bin/env python3
"""Validate that Upptime config, generated artifacts, and docs do not drift."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".upptimerc.yml"
CHECKS_WORKFLOW = ROOT / ".github" / "workflows" / "upptime-checks.yml"


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    global FAILED
    FAILED = True


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def site_names(config_text: str) -> list[str]:
    match = re.search(r"^sites:\n(?P<body>.*?)(?=^status-website:)", config_text, re.M | re.S)
    if not match:
        fail("Could not find sites block in .upptimerc.yml")
        return []

    names = []
    for line in match.group("body").splitlines():
        name_match = re.match(r"\s{2}- name:\s*(.+?)\s*$", line)
        if name_match:
            names.append(name_match.group(1))
    return names


def slugify(name: str) -> str:
    without_emoji = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    asciiish = without_emoji.encode("ascii", "ignore").decode("ascii")
    lower = asciiish.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    return re.sub(r"-+", "-", collapsed)


def configured_total(config_text: str) -> int | None:
    match = re.search(r"Total services:\s*(\d+)", config_text)
    return int(match.group(1)) if match else None


def checks_cron_from_config(config_text: str) -> str | None:
    match = re.search(r'^\s+checks:\s+"([^"]+)"', config_text, re.M)
    return match.group(1) if match else None


def checks_cron_from_workflow(workflow_text: str) -> str | None:
    match = re.search(r'^\s+- cron:\s+"([^"]+)"', workflow_text, re.M)
    return match.group(1) if match else None


def dir_slugs(path: Path) -> set[str]:
    if not path.exists():
        fail(f"Missing generated artifact directory: {path.relative_to(ROOT)}")
        return set()
    return {child.name for child in path.iterdir() if child.is_dir()}


def history_slugs() -> set[str]:
    history_dir = ROOT / "history"
    if not history_dir.exists():
        fail("Missing history directory")
        return set()
    return {
        child.stem
        for child in history_dir.iterdir()
        if child.is_file() and child.suffix == ".yml"
    }


def compare_slugs(label: str, expected: set[str], actual: set[str]) -> None:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        fail(f"{label} missing slugs: {', '.join(missing)}")
    if extra:
        fail(f"{label} has stale slugs: {', '.join(extra)}")


FAILED = False


def main() -> int:
    config_text = read(CONFIG)
    workflow_text = read(CHECKS_WORKFLOW)
    names = site_names(config_text)
    expected_slugs = {slugify(name) for name in names}

    total = configured_total(config_text)
    if total != len(names):
        fail(f".upptimerc.yml Total services is {total}, but sites contains {len(names)} entries")

    config_cron = checks_cron_from_config(config_text)
    workflow_cron = checks_cron_from_workflow(workflow_text)
    if config_cron != workflow_cron:
        fail(f"workflowSchedule.checks is {config_cron!r}, but upptime-checks.yml uses {workflow_cron!r}")

    compare_slugs("history", expected_slugs, history_slugs())
    compare_slugs("api", expected_slugs, dir_slugs(ROOT / "api"))
    compare_slugs("graphs", expected_slugs, dir_slugs(ROOT / "graphs"))

    if FAILED:
        return 1

    print(f"Upptime config validation passed for {len(names)} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
