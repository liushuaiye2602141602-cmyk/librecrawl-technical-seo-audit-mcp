"""Offline 100/1000/5000-page Master Audit benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audit_rules.registry import load_registry  # noqa: E402
from audit_rules.runner import RuleRunner  # noqa: E402


def _pages(count: int) -> list[dict]:
    return [{
        "url": f"https://example.com/page-{index}", "status_code": 200,
        "title": f"Unique page title {index}",
        "meta_description": (
            f"Unique description for synthetic page {index} with enough useful "
            "detail for deterministic audit benchmarking."),
        "h1": f"Page {index}",
        "canonical_url": f"https://example.com/page-{index}",
        "robots": "index, follow", "word_count": 500,
        "depth": min(index % 5, 4), "content_hash": f"{index:016x}",
        "links_detailed": [],
    } for index in range(count)]


def benchmark(page_counts: tuple[int, ...] = (100, 1000, 5000)) -> list[dict]:
    results = []
    for count in page_counts:
        runner = RuleRunner(load_registry())
        tracemalloc.start()
        started = time.perf_counter()
        findings, coverage = runner.run(
            pages=_pages(count), base_url="https://example.com")
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append({
            "pages": count, "seconds": round(elapsed, 3),
            "peak_mb": round(peak / 1024 / 1024, 2),
            "findings": len(findings), "coverage_rows": len(coverage),
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", nargs="+", type=int, default=[100, 1000, 5000])
    args = parser.parse_args()
    if any(value < 1 for value in args.pages):
        parser.error("page counts must be positive")
    print(json.dumps(benchmark(tuple(args.pages)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
