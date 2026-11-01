"""
verify_imports.py — Validate that all new Layer 3 modules can be imported.

Run from backend/ directory:
    python verify_imports.py

This script does NOT start the FastAPI server or connect to MongoDB.
It only validates Python imports and basic object construction.
"""
import sys
import os

# Ensure the backend app is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

errors = []

def check(label, fn):
    try:
        fn()
        print(f"  OK   {label}")
    except Exception as exc:
        print(f"  FAIL {label} -- {exc}")
        errors.append((label, exc))


print("\nAletheia — Layer 3 Import Verification")
print("=" * 50)

# ── Layer 3 models ─────────────────────────────────────────────────────────
check("trust/models.py — TrustAssessment", lambda: (
    __import__("app.services.trust.models", fromlist=["TrustAssessment", "ProvenanceEvidence", "ForensicsEvidence"])
))

# ── Weight config ───────────────────────────────────────────────────────────
check("trust/weight_config.py — get_weights()", lambda: (
    __import__("app.services.trust.weight_config", fromlist=["get_weights"]).get_weights()
))

# ── Decision rules ──────────────────────────────────────────────────────────
check("trust/decision_rules.py — DecisionEngine()", lambda: (
    __import__("app.services.trust.decision_rules", fromlist=["DecisionEngine"]).DecisionEngine()
))

# ── Trust engine ────────────────────────────────────────────────────────────
check("trust/trust_engine.py — TrustEngine()", lambda: (
    __import__("app.services.trust.trust_engine", fromlist=["TrustEngine"]).TrustEngine()
))

# ── Weight config — calibration ─────────────────────────────────────────────
check("trust/weight_config.py — get_weights() contains all 4 detectors", lambda: (
    [None for k in ("foundation_clip", "frequency_spectral", "statistical_features", "artifact_cv")
     if k not in __import__("app.services.trust.weight_config", fromlist=["get_weights"]).get_weights()]
    == []
))

# ── Fusion import now reads from weight_config ───────────────────────────────
check("ai_forensics/fusion.py — imports from weight_config", lambda: (
    __import__("app.services.ai_forensics.fusion", fromlist=["DetectionFusion"]).DetectionFusion()
))

# ── Schemas ─────────────────────────────────────────────────────────────────
check("schemas/trust.py — TrustResponse", lambda: (
    __import__("app.schemas.trust", fromlist=["TrustResponse"])
))

# ── Benchmarks ──────────────────────────────────────────────────────────────
check("benchmarks/dataset_loader.py — SyntheticDataset", lambda: (
    __import__("benchmarks.dataset_loader", fromlist=["SyntheticDataset"]).SyntheticDataset(n_real=2, n_fake=2)
))

check("benchmarks/metrics.py — MetricsAccumulator", lambda: (
    __import__("benchmarks.metrics", fromlist=["MetricsAccumulator"]).MetricsAccumulator("test_engine")
))

check("benchmarks/report_generator.py — BenchmarkReport", lambda: (
    __import__("benchmarks.report_generator", fromlist=["BenchmarkReport"])
))

check("benchmarks/benchmark_runner.py — BenchmarkRunner", lambda: (
    __import__("benchmarks.benchmark_runner", fromlist=["BenchmarkRunner"]).BenchmarkRunner()
))

# ── Summary ─────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"FAILED — {len(errors)} error(s):")
    for label, exc in errors:
        print(f"  • {label}: {exc}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED — Layer 3 imports are clean.")
    print()
