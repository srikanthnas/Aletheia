"""
metrics.py — Evaluation metric computation for the AI Forensics benchmarking framework.

All metrics are computed from raw binary predictions (threshold applied to scores)
and ground truth labels, following standard information retrieval conventions.

Label convention (matches dataset_loader.py):
    label=0 → real/authentic  (negative class)
    label=1 → AI-generated    (positive class)

Metric Definitions
------------------
True Positive  (TP): AI image correctly predicted as AI.
True Negative  (TN): Real image correctly predicted as real.
False Positive (FP): Real image incorrectly predicted as AI.
False Negative (FN): AI image incorrectly predicted as real.

Accuracy  = (TP + TN) / (TP + TN + FP + FN)
Precision = TP / (TP + FP)       [among predicted AI, how many are actually AI?]
Recall    = TP / (TP + FN)       [among actual AI images, how many were found?]
F1-score  = 2 * Precision * Recall / (Precision + Recall)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Per-sample prediction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Prediction:
    """
    A single detector prediction with ground truth.

    Fields
    ------
    engine      : Detector engine name (e.g. "foundation_clip").
    score       : Raw AI probability in [0.0, 1.0].
    confidence  : Detector self-reported confidence in [0.0, 1.0].
    label       : Ground truth (0 = real, 1 = AI).
    source_path : Image source (for debugging).
    elapsed_ms  : Inference time in milliseconds.
    """
    engine: str
    score: float
    confidence: float
    label: int
    source_path: str
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Aggregated metrics
# ---------------------------------------------------------------------------

@dataclass
class DetectorMetrics:
    """
    Aggregated evaluation metrics for a single detector.

    All metrics are computed at a configurable score threshold.
    """
    engine: str
    threshold: float = 0.5
    roc_auc: float = 0.0

    # Confusion matrix counts
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0

    # Runtime statistics
    total_samples: int = 0
    total_time_ms: float = 0.0

    # Confidence statistics
    confidence_sum: float = 0.0

    @property
    def accuracy(self) -> float:
        """Proportion of all predictions that are correct."""
        total = self.tp + self.tn + self.fp + self.fn
        return (self.tp + self.tn) / total if total > 0 else 0.0

    @property
    def precision(self) -> float:
        """Of all images predicted AI, what fraction are actually AI?"""
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        """Of all actual AI images, what fraction were correctly detected?"""
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """Harmonic mean of precision and recall."""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        """Of all actual real images, what fraction were incorrectly flagged as AI?"""
        denom = self.fp + self.tn
        return self.fp / denom if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        """Of all actual AI images, what fraction were missed?"""
        denom = self.fn + self.tp
        return self.fn / denom if denom > 0 else 0.0

    @property
    def avg_time_ms(self) -> float:
        """Average inference time per sample in milliseconds."""
        return self.total_time_ms / self.total_samples if self.total_samples > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        """Average self-reported confidence across all samples."""
        return self.confidence_sum / self.total_samples if self.total_samples > 0 else 0.0

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON reporting."""
        return {
            "engine":             self.engine,
            "threshold":          self.threshold,
            "samples":            self.total_samples,
            "tp":                 self.tp,
            "tn":                 self.tn,
            "fp":                 self.fp,
            "fn":                 self.fn,
            "accuracy":           round(self.accuracy, 4),
            "precision":          round(self.precision, 4),
            "recall":             round(self.recall, 4),
            "f1_score":           round(self.f1_score, 4),
            "roc_auc":            round(self.roc_auc, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "avg_time_ms":        round(self.avg_time_ms, 3),
            "avg_confidence":     round(self.avg_confidence, 4),
        }


# ---------------------------------------------------------------------------
# Metrics accumulator
# ---------------------------------------------------------------------------

class MetricsAccumulator:
    """
    Accumulates per-sample predictions and computes aggregate metrics.

    Usage::

        acc = MetricsAccumulator(engine="foundation_clip", threshold=0.5)
        acc.record(prediction)
        ...
        metrics = acc.compute()
    """

    def __init__(self, engine: str, threshold: float = 0.5) -> None:
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")
        self._engine = engine
        self._threshold = threshold
        self._predictions: list[Prediction] = []

    def record(self, prediction: Prediction) -> None:
        """Record a single prediction."""
        self._predictions.append(prediction)

    def compute(self) -> DetectorMetrics:
        """
        Compute aggregated metrics from all recorded predictions.

        Returns:
            DetectorMetrics with confusion matrix, accuracy, precision, recall,
            F1, time statistics, and confidence statistics.
        """
        metrics = DetectorMetrics(engine=self._engine, threshold=self._threshold)

        for pred in self._predictions:
            predicted = 1 if pred.score >= self._threshold else 0
            actual = pred.label

            metrics.total_samples += 1
            metrics.total_time_ms += pred.elapsed_ms
            metrics.confidence_sum += pred.confidence

            if predicted == 1 and actual == 1:
                metrics.tp += 1
            elif predicted == 0 and actual == 0:
                metrics.tn += 1
            elif predicted == 1 and actual == 0:
                metrics.fp += 1
            else:  # predicted == 0 and actual == 1
                metrics.fn += 1

        # Compute ROC-AUC
        if self._predictions:
            # Sort predictions by score descending
            sorted_preds = sorted(self._predictions, key=lambda p: p.score, reverse=True)
            tpr_list = [0.0]
            fpr_list = [0.0]
            
            total_p = sum(1 for p in sorted_preds if p.label == 1)
            total_n = sum(1 for p in sorted_preds if p.label == 0)
            
            if total_p > 0 and total_n > 0:
                tp_count = 0
                fp_count = 0
                prev_score = float('inf')
                
                for pred in sorted_preds:
                    if pred.score != prev_score:
                        tpr_list.append(tp_count / total_p)
                        fpr_list.append(fp_count / total_n)
                        prev_score = pred.score
                        
                    if pred.label == 1:
                        tp_count += 1
                    else:
                        fp_count += 1
                        
                tpr_list.append(tp_count / total_p)
                fpr_list.append(fp_count / total_n)
                
                # Trapezoidal rule for AUC
                auc = 0.0
                for i in range(1, len(tpr_list)):
                    auc += 0.5 * (fpr_list[i] - fpr_list[i-1]) * (tpr_list[i] + tpr_list[i-1])
                metrics.roc_auc = auc
            else:
                # If only one class is present, AUC is undefined/meaningless, default to 0.0
                metrics.roc_auc = 0.0

        return metrics

    def predictions(self) -> list[Prediction]:
        """Return a copy of all recorded predictions."""
        return list(self._predictions)
