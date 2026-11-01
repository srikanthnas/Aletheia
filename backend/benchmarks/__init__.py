"""
benchmarks/__init__.py — Aletheia AI Forensics Benchmarking Framework.

Public API:

    from benchmarks import BenchmarkRunner, DirectoryDataset, SyntheticDataset

Usage (with a real labeled dataset)::

    from benchmarks import BenchmarkRunner, DirectoryDataset

    dataset = DirectoryDataset(
        real_dir="path/to/real_images",
        fake_dir="path/to/ai_images",
    )
    runner = BenchmarkRunner()
    report = runner.run(dataset)
    report.print_summary()
    report.save_json("benchmark_results.json")

Usage (with synthetic test data, no dataset required)::

    from benchmarks import BenchmarkRunner, SyntheticDataset

    dataset = SyntheticDataset(n_real=20, n_fake=20, seed=42)
    runner = BenchmarkRunner()
    report = runner.run(dataset)
    report.print_summary()
"""
from benchmarks.dataset_loader import Dataset, DirectoryDataset, SyntheticDataset, LabeledSample
from benchmarks.benchmark_runner import BenchmarkRunner
from benchmarks.report_generator import BenchmarkReport

__all__ = [
    "Dataset",
    "DirectoryDataset",
    "SyntheticDataset",
    "LabeledSample",
    "BenchmarkRunner",
    "BenchmarkReport",
]
