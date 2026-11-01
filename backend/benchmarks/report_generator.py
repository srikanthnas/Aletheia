"""
report_generator.py — Structured benchmark report output.

The BenchmarkReport object holds all computed DetectorMetrics and provides:
  - Console summary (print_summary)
  - JSON export (save_json / to_dict)
  - Markdown table export (to_markdown)

Usage::

    report = runner.run(dataset)
    report.print_summary()
    report.save_json("results/benchmark_2026.json")
    print(report.to_markdown())
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.metrics import DetectorMetrics

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkReport:
    """
    Complete benchmark evaluation report.

    Contains per-detector metrics and summary statistics.
    Provides console, JSON, and Markdown output methods.

    Args:
        dataset_name     : Human-readable dataset name.
        n_samples        : Total number of samples evaluated.
        threshold        : Binary classification threshold used.
        detector_metrics : List of DetectorMetrics, one per detector.
    """

    dataset_name: str
    n_samples: int
    threshold: float
    detector_metrics: list[DetectorMetrics]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Console output
    # ------------------------------------------------------------------

    def print_summary(self) -> None:
        """Print a formatted summary table to stdout."""
        width = 100
        print()
        print("=" * width)
        print(f"  Aletheia AI Forensics — Benchmark Report")
        print(f"  Dataset : {self.dataset_name}")
        print(f"  Samples : {self.n_samples}")
        print(f"  Threshold: {self.threshold:.2f}")
        print(f"  Generated: {self.timestamp}")
        print("=" * width)
        print()

        # Header
        header = (
            f"{'Detector':<24} "
            f"{'Acc':>7} "
            f"{'Prec':>7} "
            f"{'Recall':>7} "
            f"{'F1':>7} "
            f"{'AUC':>7} "
            f"{'FPR':>7} "
            f"{'FNR':>7} "
            f"{'AvgConf':>8} "
            f"{'AvgMs':>8} "
            f"{'TP':>5} {'TN':>5} {'FP':>5} {'FN':>5}"
        )
        print(header)
        print("-" * width)

        for m in self.detector_metrics:
            row = (
                f"{m.engine:<24} "
                f"{m.accuracy:>7.3f} "
                f"{m.precision:>7.3f} "
                f"{m.recall:>7.3f} "
                f"{m.f1_score:>7.3f} "
                f"{m.roc_auc:>7.3f} "
                f"{m.false_positive_rate:>7.3f} "
                f"{m.false_negative_rate:>7.3f} "
                f"{m.avg_confidence:>8.3f} "
                f"{m.avg_time_ms:>8.1f} "
                f"{m.tp:>5} {m.tn:>5} {m.fp:>5} {m.fn:>5}"
            )
            print(row)

        print("-" * width)

        # Ensemble average
        if self.detector_metrics:
            metrics_list = self.detector_metrics
            avg_acc   = sum(m.accuracy   for m in metrics_list) / len(metrics_list)
            avg_prec  = sum(m.precision  for m in metrics_list) / len(metrics_list)
            avg_rec   = sum(m.recall     for m in metrics_list) / len(metrics_list)
            avg_f1    = sum(m.f1_score   for m in metrics_list) / len(metrics_list)
            avg_auc   = sum(m.roc_auc    for m in metrics_list) / len(metrics_list)
            avg_ms    = sum(m.avg_time_ms for m in metrics_list) / len(metrics_list)
            total_ms  = sum(m.total_time_ms for m in metrics_list)
            summary = (
                f"{'ENSEMBLE AVERAGE':<24} "
                f"{avg_acc:>7.3f} "
                f"{avg_prec:>7.3f} "
                f"{avg_rec:>7.3f} "
                f"{avg_f1:>7.3f} "
                f"{avg_auc:>7.3f} "
                f"{'—':>7} "
                f"{'—':>7} "
                f"{'—':>8} "
                f"{avg_ms:>8.1f}"
            )
            print(summary)
            print(f"\n  Total inference time: {total_ms:.0f} ms")

        print("=" * width)
        print()

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the full report to a plain dict."""
        return {
            "meta": {
                "dataset":   self.dataset_name,
                "samples":   self.n_samples,
                "threshold": self.threshold,
                "timestamp": self.timestamp,
                "framework": "Aletheia AI Forensics Benchmarking Framework",
            },
            "results": [m.to_dict() for m in self.detector_metrics],
            "ensemble_summary": self._ensemble_summary(),
        }

    def save_json(self, path: str | Path) -> None:
        """
        Save the full benchmark report to a JSON file.

        Args:
            path: Output file path. Parent directories will be created.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info("[BenchmarkReport] Report saved to %s", path)
        print(f"  Report saved -> {path}")

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        """
        Generate a Markdown table suitable for pasting into a report or README.

        Returns:
            A multi-line string containing the Markdown table.
        """
        lines = [
            f"## Aletheia AI Forensics — Benchmark Results",
            f"",
            f"**Dataset:** {self.dataset_name}  ",
            f"**Samples:** {self.n_samples}  ",
            f"**Threshold:** {self.threshold:.2f}  ",
            f"**Generated:** {self.timestamp}  ",
            f"",
            "| Detector | Accuracy | Precision | Recall | F1 | AUC | FPR | FNR | Avg Conf | Avg ms |",
            "|----------|----------|-----------|--------|----|-----|-----|-----|----------|--------|",
        ]

        for m in self.detector_metrics:
            row = (
                f"| {m.engine} "
                f"| {m.accuracy:.3f} "
                f"| {m.precision:.3f} "
                f"| {m.recall:.3f} "
                f"| {m.f1_score:.3f} "
                f"| {m.roc_auc:.3f} "
                f"| {m.false_positive_rate:.3f} "
                f"| {m.false_negative_rate:.3f} "
                f"| {m.avg_confidence:.3f} "
                f"| {m.avg_time_ms:.1f} |"
            )
            lines.append(row)

        summary = self._ensemble_summary()
        if summary:
            lines.extend([
                f"",
                f"**Ensemble Average** — Accuracy: {summary['avg_accuracy']:.3f}, "
                f"F1: {summary['avg_f1']:.3f}, "
                f"AUC: {summary['avg_auc']:.3f}, "
                f"Total inference time: {summary['total_time_ms']:.0f} ms",
            ])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensemble_summary(self) -> dict:
        """Compute ensemble-level summary statistics."""
        if not self.detector_metrics:
            return {}

        m_list = self.detector_metrics
        return {
            "avg_accuracy":   round(sum(m.accuracy   for m in m_list) / len(m_list), 4),
            "avg_precision":  round(sum(m.precision  for m in m_list) / len(m_list), 4),
            "avg_recall":     round(sum(m.recall     for m in m_list) / len(m_list), 4),
            "avg_f1":         round(sum(m.f1_score   for m in m_list) / len(m_list), 4),
            "avg_auc":        round(sum(m.roc_auc    for m in m_list) / len(m_list), 4),
            "total_time_ms":  round(sum(m.total_time_ms for m in m_list), 2),
            "avg_time_ms":    round(sum(m.avg_time_ms for m in m_list) / len(m_list), 2),
            "detector_count": len(m_list),
        }
