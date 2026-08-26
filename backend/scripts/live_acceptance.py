#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import json
import mimetypes
import os
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models import EditChange, EditPlanResponse, GenerationResponse  # noqa: E402
from app.providers import GeminiImageProvider  # noqa: E402


LOCKED_REGIONS = [
    "身份",
    "眼睛",
    "眼距",
    "眉毛",
    "鼻子",
    "嘴唇",
    "牙齿",
    "颧骨",
    "颧弓",
    "肤色",
    "表情",
    "视线",
    "发型",
    "发际线",
    "服装",
    "配饰",
    "背景",
    "构图",
    "画幅",
    "裁切",
    "光线方向",
]


@dataclass
class CaseResult:
    case_id: str
    source: str
    result: str
    elapsed_seconds: float
    response: GenerationResponse

    @property
    def accepted(self) -> bool:
        verdict = self.response.quality_verdict
        return bool(
            self.response.result_mode == "gemini_edit"
            and verdict
            and verdict.eligible
            and not verdict.hard_failures
        )

    def as_json(self) -> dict[str, Any]:
        verdict = self.response.quality_verdict
        return {
            "id": self.case_id,
            "accepted": self.accepted,
            "result_mode": self.response.result_mode,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "source": self.source,
            "result": self.result,
            "candidate_count": self.response.candidate_count,
            "correction_rounds": self.response.correction_rounds,
            "semantic_judge_count": self.response.semantic_judge_count,
            "deterministic_reject_count": self.response.deterministic_reject_count,
            "generation_provider": self.response.generation_provider,
            "quality_verdict": verdict.model_dump() if verdict else None,
            "quality_notes": self.response.quality_notes,
        }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _build_plan(case: dict[str, Any]) -> EditPlanResponse:
    return EditPlanResponse(
        id=str(uuid4()),
        headline="明显但仍是本人的轮廓优化",
        summary="只执行用户确认的轮廓目标；身份、五官、颧骨、背景和构图全部锁定。",
        changes=[
            EditChange(
                id=f"acceptance-{case['id']}",
                area=case["target_area"],
                title=case["title"],
                rationale="验收明显变化与身份保持能否同时成立。",
                instruction=case["instruction"],
            )
        ],
        locked_regions=LOCKED_REGIONS,
        prompt_version="live-acceptance-v1",
        intensity="visible",
    )


async def _run_case(
    case: dict[str, Any],
    manifest_dir: Path,
    output_dir: Path,
) -> CaseResult:
    source_path = (manifest_dir / case["source"]).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source image: {source_path}")
    source_data = source_path.read_bytes()
    mime_type = mimetypes.guess_type(source_path.name)[0] or "image/jpeg"

    def capture_candidate(data: bytes, candidate_mime: str, index: int) -> None:
        extension = mimetypes.guess_extension(candidate_mime) or ".jpg"
        (output_dir / f"{case['id']}-candidate-{index}{extension}").write_bytes(data)

    provider = GeminiImageProvider(candidate_observer=capture_candidate)
    started = time.perf_counter()
    response = await provider.generate(
        (source_data, mime_type),
        _build_plan(case),
        locale="zh-Hans",
    )
    elapsed = time.perf_counter() - started
    extension = mimetypes.guess_extension(response.result_mime_type or "image/jpeg") or ".jpg"
    result_name = f"{case['id']}-result{extension}"
    result_path = output_dir / result_name
    if response.result_image_base64:
        result_path.write_bytes(base64.b64decode(response.result_image_base64))
    else:
        result_path.write_bytes(source_data)
    return CaseResult(
        case_id=case["id"],
        source=os.path.relpath(source_path, output_dir),
        result=result_name,
        elapsed_seconds=elapsed,
        response=response,
    )


def _evaluate(results: list[CaseResult], acceptance: dict[str, float]) -> dict[str, Any]:
    latencies = [item.elapsed_seconds for item in results]
    accepted_count = sum(item.accepted for item in results)
    eligible_rate = accepted_count / len(results) if results else 0.0
    # The product never displays an ineligible candidate: a failed live result is
    # required to return the original. Verify that invariant independently.
    unsafe_displays = sum(
        item.response.result_mode == "gemini_edit" and not item.accepted for item in results
    )
    unsafe_rate = unsafe_displays / len(results) if results else 1.0
    metrics = {
        "case_count": len(results),
        "accepted_count": accepted_count,
        "eligible_rate": round(eligible_rate, 4),
        "hard_failure_display_rate": round(unsafe_rate, 4),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0.0,
            "p50": round(_percentile(latencies, 0.5), 2),
            "p95": round(_percentile(latencies, 0.95), 2),
        },
    }
    gates = {
        "eligible_rate": eligible_rate >= acceptance["eligible_rate_min"],
        "hard_failure_display_rate": unsafe_rate <= acceptance["hard_failure_display_rate_max"],
        "p50_latency": metrics["latency_seconds"]["p50"]
        <= acceptance["p50_latency_seconds_max"],
        "p95_latency": metrics["latency_seconds"]["p95"]
        <= acceptance["p95_latency_seconds_max"],
    }
    return {"passed": all(gates.values()), "gates": gates, "metrics": metrics}


def _score(verdict: Any, name: str) -> str:
    return str(getattr(verdict, name, "—")) if verdict else "—"


def _write_html(
    output_dir: Path,
    evaluation: dict[str, Any],
    results: list[CaseResult],
) -> None:
    status = "通过" if evaluation["passed"] else "未通过"
    metrics = evaluation["metrics"]
    cards: list[str] = []
    for item in results:
        verdict = item.response.quality_verdict
        failures = "、".join(verdict.hard_failures) if verdict and verdict.hard_failures else "无"
        cards.append(
            f"""
            <section class="case {'pass' if item.accepted else 'fail'}">
              <h2>{html.escape(item.case_id)} · {'通过' if item.accepted else '未通过/安全回退'}</h2>
              <div class="images">
                <figure><img src="{html.escape(item.source)}"><figcaption>原图</figcaption></figure>
                <figure><img src="{html.escape(item.result)}"><figcaption>结果</figcaption></figure>
              </div>
              <div class="scores">
                <span>身份 {_score(verdict, 'identity_score')}</span>
                <span>目标变化 {_score(verdict, 'target_change_score')}</span>
                <span>锁定区 {_score(verdict, 'locked_region_score')}</span>
                <span>画幅 {_score(verdict, 'framing_score')}</span>
                <span>耗时 {item.elapsed_seconds:.1f}s</span>
                <span>候选 {item.response.candidate_count}</span>
                <span>生成引擎 {html.escape(item.response.generation_provider)}</span>
              </div>
              <p><strong>失败码：</strong>{html.escape(failures)}</p>
              <p>{html.escape(verdict.summary if verdict else item.response.message)}</p>
            </section>
            """
        )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>小美说真实模型验收报告</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:32px;background:#f6f4f2;color:#222}}
.summary,.case{{max-width:1100px;margin:0 auto 24px;background:white;border-radius:18px;padding:24px;box-shadow:0 5px 22px #0001}}
.summary h1{{margin-top:0}} .pass{{border-left:8px solid #239b56}} .fail{{border-left:8px solid #c0392b}}
.images{{display:grid;grid-template-columns:1fr 1fr;gap:20px}} figure{{margin:0}} img{{width:100%;max-height:680px;object-fit:contain;background:#eee;border-radius:12px}}
figcaption{{text-align:center;margin-top:8px}} .scores{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}
.scores span{{background:#f1ece8;border-radius:999px;padding:8px 12px}} @media(max-width:720px){{.images{{grid-template-columns:1fr}}body{{margin:12px}}}}
</style></head><body>
<section class="summary {'pass' if evaluation['passed'] else 'fail'}">
<h1>小美说真实模型验收：{status}</h1>
<p>通过 {metrics['accepted_count']}/{metrics['case_count']}，有效结果率 {metrics['eligible_rate']:.0%}，不安全结果展示率 {metrics['hard_failure_display_rate']:.0%}。</p>
<p>耗时 P50 {metrics['latency_seconds']['p50']:.1f}s，P95 {metrics['latency_seconds']['p95']:.1f}s。</p>
</section>
{''.join(cards)}
</body></html>"""
    (output_dir / "report.html").write_text(document, encoding="utf-8")


async def _main(args: argparse.Namespace) -> int:
    if os.getenv("MODEL_MODE") != "live":
        raise RuntimeError("set MODEL_MODE=live before running acceptance")
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "OPENAI_ANALYSIS_MODEL", "GEMINI_IMAGE_MODEL"):
        if not os.getenv(variable):
            raise RuntimeError(f"missing required environment variable: {variable}")

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir or BACKEND_ROOT / "acceptance_runs" / timestamp).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    cases = manifest["cases"][: args.limit or None]
    results: list[CaseResult] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        results.append(await _run_case(case, manifest_path.parent, output_dir))

    evaluation = _evaluate(results, manifest["acceptance"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "models": {
            "analysis_and_judge": os.environ["OPENAI_ANALYSIS_MODEL"],
            "quality_judge": os.getenv("OPENAI_JUDGE_MODEL")
            or os.environ["OPENAI_ANALYSIS_MODEL"],
            "image_generation": os.environ["GEMINI_IMAGE_MODEL"],
            "image_fallback": os.getenv("OPENAI_IMAGE_MODEL") or None,
        },
        "acceptance": manifest["acceptance"],
        "evaluation": evaluation,
        "cases": [item.as_json() for item in results],
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_html(output_dir, evaluation, results)
    print(json.dumps(evaluation, ensure_ascii=False, indent=2))
    print(f"report: {output_dir / 'report.html'}")
    return 0 if evaluation["passed"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live Xiaomeishuo image acceptance")
    parser.add_argument(
        "--manifest",
        default=str(BACKEND_ROOT / "tests" / "live_acceptance_manifest.json"),
    )
    parser.add_argument("--output-dir")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(parse_args())))
