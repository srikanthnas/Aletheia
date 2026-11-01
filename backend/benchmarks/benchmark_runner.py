"""
benchmark_runner.py — Orchestrates detector evaluation across a labeled dataset.

Architecture
------------
The BenchmarkRunner is decoupled from all detector implementations.
It accepts any AIForensicDetector plugin and any Dataset implementation,
making it fully compatible with the existing plugin architecture.

Design
------
- No knowledge of specific detector internals.
- Runs each detector against every sample independently.
- Isolates detector failures — one crash does not abort the benchmark.
- Computes metrics via MetricsAccumulator (clean separation of concerns).
- Returns a BenchmarkReport (see report_generator.py).

Usage::

    from benchmarks import BenchmarkRunner, SyntheticDataset

    runner = BenchmarkRunner()
    report = runner.run(SyntheticDataset())
    report.print_summary()
"""
from __future__ import annotations

import logging
import time
from typing import Sequence

from benchmarks.dataset_loader import Dataset, LabeledSample
from benchmarks.metrics import MetricsAccumulator, Prediction
from benchmarks.report_generator import BenchmarkReport

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Evaluates a set of AIForensicDetector plugins against a labeled dataset.

    Each detector is run on every sample independently. Failures are caught
    and logged — they do not abort the overall benchmark.

    Args:
        threshold: Score threshold for binary classification (default 0.5).
                   Scores >= threshold → AI-generated.
                   Scores <  threshold → authentic.

    Usage::

        runner = BenchmarkRunner(threshold=0.5)
        report = runner.run(dataset, detectors=[...])
    """

    def __init__(self, threshold: float = 0.5) -> None:
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")
        self._threshold = threshold

    def run(
        self,
        dataset: Dataset,
        detectors: Sequence | None = None,
    ) -> "BenchmarkReport":
        """
        Run the full benchmark.

        Args:
            dataset:   Dataset instance yielding LabeledSample objects.
            detectors: List of AIForensicDetector instances to evaluate.
                       If None, uses the default DetectionEngine plugin set.

        Returns:
            BenchmarkReport with per-detector metrics and summary statistics.
        """
        if detectors is None:
            detectors = self._load_default_detectors()

        logger.info(
            "[BenchmarkRunner] Starting benchmark: dataset='%s', detectors=%d, samples=%d",
            dataset.name,
            len(detectors),  # type: ignore[arg-type]
            len(dataset),
        )

        # Initialize an accumulator per detector
        accumulators: dict[str, MetricsAccumulator] = {
            d.name: MetricsAccumulator(engine=d.name, threshold=self._threshold)
            for d in detectors  # type: ignore[union-attr]
        }

        # Iterate samples
        samples_processed = 0
        for sample in dataset:
            samples_processed += 1
            if samples_processed % 10 == 0:
                logger.info(
                    "[BenchmarkRunner] Progress: %d / %d",
                    samples_processed, len(dataset)
                )

            for detector in detectors:  # type: ignore[union-attr]
                self._evaluate_detector(detector, sample, accumulators[detector.name])

        # Compute metrics from each accumulator
        all_metrics = [acc.compute() for acc in accumulators.values()]

        logger.info(
            "[BenchmarkRunner] Benchmark complete. %d samples processed.",
            samples_processed,
        )

        return BenchmarkReport(
            dataset_name=dataset.name,
            n_samples=samples_processed,
            threshold=self._threshold,
            detector_metrics=all_metrics,
        )

    def _evaluate_detector(
        self,
        detector,
        sample: LabeledSample,
        accumulator: MetricsAccumulator,
    ) -> None:
        """
        Run a single detector on a single sample and record the prediction.

        Failures are caught and logged; the accumulator is not updated on failure.
        """
        try:
            t0 = time.perf_counter()
            result = detector.analyze(sample.image)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            accumulator.record(Prediction(
                engine=detector.name,
                score=result.score,
                confidence=result.confidence,
                label=sample.label,
                source_path=sample.source_path,
                elapsed_ms=elapsed_ms,
            ))

        except Exception as exc:
            logger.error(
                "[BenchmarkRunner] Detector '%s' failed on sample '%s': %s",
                detector.name, sample.source_path, exc, exc_info=True,
            )

    @staticmethod
    def _load_default_detectors() -> list:
        """
        Load the default set of detector plugins for benchmarking.

        Mirrors DetectionEngine.default() but returns a plain list
        so the runner can iterate them with timing isolation.
        """
        from app.services.ai_forensics.detectors.foundation_detector import FoundationDetector
        from app.services.ai_forensics.detectors.statistical_detector import StatisticalDetector
        from app.services.ai_forensics.detectors.artifact_detector import ArtifactDetector
        from app.services.ai_forensics.detectors.frequency_detector import FrequencyDetector

        return [
            FoundationDetector(),
            StatisticalDetector(),
            ArtifactDetector(),
            FrequencyDetector(),
        ]
