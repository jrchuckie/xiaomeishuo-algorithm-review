#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.providers import (  # noqa: E402
    GeminiImageProvider,
    _openai_revision_judge,
)
from scripts.live_acceptance import _build_plan  # noqa: E402


def _image(path: Path) -> tuple[bytes, str]:
    return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg"


async def _run(args: argparse.Namespace) -> int:
    if os.getenv("MODEL_MODE") != "live":
        raise RuntimeError("set MODEL_MODE=live before running acceptance")
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir = Path(
        args.output_dir
        or BACKEND_ROOT
        / "acceptance_runs"
        / f"revision-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    base_cases = {item["id"]: item for item in manifest["cases"]}
    results: list[dict[str, object]] = []

    for index, revision in enumerate(manifest.get("revision_cases", []), start=1):
        base = base_cases[revision["base_case"]]
        source_path = (manifest_path.parent / base["source"]).resolve()
        previous_path = (manifest_path.parent / revision["previous"]).resolve()
        source = _image(source_path)
        previous = _image(previous_path)
        started = time.perf_counter()
        generated = await GeminiImageProvider().generate(
            source,
            _build_plan(base),
            previous_image=previous,
            feedback=revision["feedback"],
            locale="zh-Hans",
        )
        elapsed = time.perf_counter() - started
        revision_data = (
            base64.b64decode(generated.result_image_base64)
            if generated.result_image_base64
            else source[0]
        )
        revision_mime = generated.result_mime_type or source[1]
        suffix = mimetypes.guess_extension(revision_mime) or ".jpg"
        result_name = f"{revision['id']}-result{suffix}"
        (output_dir / result_name).write_bytes(revision_data)
        verdict = await _openai_revision_judge(
            source,
            previous,
            (revision_data, revision_mime),
            feedback=revision["feedback"],
            locked_regions=_build_plan(base).locked_regions,
        )
        accepted = generated.result_mode == "gemini_edit" and verdict.eligible
        results.append(
            {
                "id": revision["id"],
                "accepted": accepted,
                "feedback": revision["feedback"],
                "elapsed_seconds": round(elapsed, 2),
                "result": result_name,
                "result_mode": generated.result_mode,
                "generation_provider": generated.generation_provider,
                "candidate_count": generated.candidate_count,
                "correction_rounds": generated.correction_rounds,
                "generation_quality": (
                    generated.quality_verdict.model_dump()
                    if generated.quality_verdict
                    else None
                ),
                "revision_verdict": verdict.model_dump(),
            }
        )
        print(f"[{index}] {revision['id']}: {'PASS' if accepted else 'FAIL'}", flush=True)

    case_count = len(results)
    passed_count = sum(bool(item["accepted"]) for item in results)
    correct_rate = passed_count / case_count if case_count else 0.0
    fallback_rate = (
        sum(item["result_mode"] == "safe_original" for item in results) / case_count
        if case_count
        else 1.0
    )
    within_two_rate = (
        sum(
            bool(item["accepted"]) and int(item["correction_rounds"]) <= 2
            for item in results
        )
        / case_count
        if case_count
        else 0.0
    )
    metrics = {
        "case_count": case_count,
        "passed_count": passed_count,
        "v2_v3_feedback_correct_rate": round(correct_rate, 4),
        "deliverable_within_two_corrections_rate": round(within_two_rate, 4),
        "original_fallback_rate": round(fallback_rate, 4),
    }
    gates = {
        "v2_v3_feedback_correct_rate": correct_rate >= 0.90,
        "deliverable_within_two_corrections_rate": within_two_rate >= 0.95,
        "original_fallback_rate": fallback_rate <= 0.05,
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": {"passed": all(gates.values()), "gates": gates, "metrics": metrics},
        "cases": results,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["evaluation"], ensure_ascii=False, indent=2))
    print(f"report: {output_dir / 'report.json'}")
    return 0 if report["evaluation"]["passed"] else 2


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live V2/V3 revision acceptance")
    parser.add_argument(
        "--manifest",
        default=str(BACKEND_ROOT / "tests" / "live_acceptance_manifest.json"),
    )
    parser.add_argument("--output-dir")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_args())))
