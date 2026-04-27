#!/usr/bin/env python3
"""
Test All LLM Backends
Validates all LLM backends before competition demo

This script tests each LLM backend individually and measures:
- Success rate
- Average latency
- Response quality
- Failover behavior

Usage:
    python scripts/test_all_llm_backends.py
    python scripts/test_all_llm_backends.py --verbose
    python scripts/test_all_llm_backends.py --backend nova
"""

import argparse
import json
import logging
import sys
import time
from statistics import mean, median
from typing import Any, Dict, List

# Add src to path
sys.path.insert(0, ".")

from src.multi_backend_llm import MultiBackendLLM

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Test scenarios
TEST_SCENARIOS = [
    {
        "name": "Warfarin - CYP2C9 Poor Metabolizer",
        "context": "CYP2C9 metabolizes warfarin. Poor metabolizers have reduced enzyme activity.",
        "query": "What is the effect of CYP2C9 *2/*3 genotype on warfarin dosing?",
        "pgx_data": {
            "gene": "CYP2C9",
            "genotype": "*2/*3",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Reduce warfarin dose by 50% and monitor INR closely",
        },
    },
    {
        "name": "Clopidogrel - CYP2C19 Poor Metabolizer",
        "context": "CYP2C19 activates clopidogrel. Poor metabolizers have reduced drug efficacy.",
        "query": "What is the effect of CYP2C19 *2/*2 genotype on clopidogrel?",
        "pgx_data": {
            "gene": "CYP2C19",
            "genotype": "*2/*2",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Consider alternative antiplatelet therapy (prasugrel or ticagrelor)",
        },
    },
    {
        "name": "Codeine - CYP2D6 Ultra-Rapid Metabolizer",
        "context": "CYP2D6 converts codeine to morphine. Ultra-rapid metabolizers have increased toxicity risk.",
        "query": "What is the effect of CYP2D6 *1/*2xN genotype on codeine?",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*1/*2xN",
            "phenotype": "Ultra-Rapid Metabolizer",
            "risk": "High",
            "recommendation": "Avoid codeine, use alternative analgesic",
        },
    },
]


def test_single_backend(
    backend_name: str,
    backend_func: callable,
    scenarios: List[Dict[str, Any]],
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Test a single backend with multiple scenarios

    Args:
        backend_name: Name of the backend
        backend_func: Backend function to test
        scenarios: List of test scenarios
        verbose: Print detailed output

    Returns:
        Dict with test results
    """
    results = {
        "backend": backend_name,
        "total_tests": len(scenarios),
        "successes": 0,
        "failures": 0,
        "latencies": [],
        "errors": [],
    }

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            print(f"\n  Test {i}/{len(scenarios)}: {scenario['name']}")

        try:
            start = time.time()

            # Call backend
            if backend_name in ["nova", "bedrock_claude"]:
                response = backend_func(
                    scenario["context"], scenario["query"], scenario["pgx_data"]
                )
            else:
                response = backend_func(
                    scenario["context"], scenario["query"], scenario["pgx_data"]
                )

            latency = (time.time() - start) * 1000
            results["latencies"].append(latency)
            results["successes"] += 1

            if verbose:
                print(f"    ✅ Success: {latency:.0f}ms")
                print(f"    Response: {response[:100]}...")

        except Exception as e:
            results["failures"] += 1
            error_msg = str(e)[:200]
            results["errors"].append(error_msg)

            if verbose:
                print(f"    ❌ Failed: {error_msg}")

    # Calculate statistics
    if results["latencies"]:
        results["avg_latency_ms"] = round(mean(results["latencies"]), 2)
        results["median_latency_ms"] = round(median(results["latencies"]), 2)
        results["min_latency_ms"] = round(min(results["latencies"]), 2)
        results["max_latency_ms"] = round(max(results["latencies"]), 2)
    else:
        results["avg_latency_ms"] = None
        results["median_latency_ms"] = None
        results["min_latency_ms"] = None
        results["max_latency_ms"] = None

    results["success_rate"] = results["successes"] / results["total_tests"]

    return results


def test_failover_behavior(
    llm: MultiBackendLLM, scenarios: List[Dict[str, Any]], verbose: bool = False
) -> Dict[str, Any]:
    """
    Test automatic failover behavior

    Args:
        llm: MultiBackendLLM instance
        scenarios: List of test scenarios
        verbose: Print detailed output

    Returns:
        Dict with failover test results
    """
    results = {
        "total_tests": len(scenarios),
        "successes": 0,
        "failures": 0,
        "backend_usage": {},
        "fallback_occurred": 0,
        "latencies": [],
    }

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            print(f"\n  Test {i}/{len(scenarios)}: {scenario['name']}")

        try:
            start = time.time()

            result = llm.generate_with_fallback(
                scenario["context"], scenario["query"], scenario["pgx_data"]
            )

            latency = (time.time() - start) * 1000
            results["latencies"].append(latency)
            results["successes"] += 1

            # Track backend usage
            backend_used = result.get("backend_used", "unknown")
            results["backend_usage"][backend_used] = (
                results["backend_usage"].get(backend_used, 0) + 1
            )

            if result.get("fallback_occurred"):
                results["fallback_occurred"] += 1

            if verbose:
                print(f"    ✅ Success: {latency:.0f}ms")
                print(f"    Backend: {backend_used}")
                print(f"    Attempts: {result.get('attempts', 1)}")

        except Exception as e:
            results["failures"] += 1

            if verbose:
                print(f"    ❌ Failed: {str(e)[:200]}")

    # Calculate statistics
    if results["latencies"]:
        results["avg_latency_ms"] = round(mean(results["latencies"]), 2)
        results["median_latency_ms"] = round(median(results["latencies"]), 2)
    else:
        results["avg_latency_ms"] = None
        results["median_latency_ms"] = None

    results["success_rate"] = results["successes"] / results["total_tests"]

    return results


def print_summary(all_results: Dict[str, Any]) -> None:
    """Print test summary"""
    print("\n" + "=" * 80)
    print("LLM Backend Test Summary")
    print("=" * 80)

    # Individual backend results
    print("\nIndividual Backend Results:")
    print("-" * 80)
    print(f"{'Backend':<25} {'Success Rate':<15} {'Avg Latency':<15} {'Status':<10}")
    print("-" * 80)

    for backend_name, result in all_results.get("individual_backends", {}).items():
        success_rate = f"{result['success_rate']*100:.1f}%"
        avg_latency = (
            f"{result['avg_latency_ms']:.0f}ms" if result["avg_latency_ms"] else "N/A"
        )
        status = "✅ PASS" if result["success_rate"] == 1.0 else "❌ FAIL"

        print(f"{backend_name:<25} {success_rate:<15} {avg_latency:<15} {status:<10}")

    # Failover results
    if "failover" in all_results:
        failover = all_results["failover"]
        print("\nAutomatic Failover Results:")
        print("-" * 80)
        print(f"Total Tests: {failover['total_tests']}")
        print(
            f"Successes: {failover['successes']} ({failover['success_rate']*100:.1f}%)"
        )
        print(f"Failures: {failover['failures']}")
        print(
            f"Fallback Occurred: {failover['fallback_occurred']} ({failover['fallback_occurred']/failover['total_tests']*100:.1f}%)"
        )
        print(f"Avg Latency: {failover['avg_latency_ms']:.0f}ms")

        print("\nBackend Usage Distribution:")
        for backend, count in failover["backend_usage"].items():
            percentage = count / failover["total_tests"] * 100
            print(f"  {backend}: {count} ({percentage:.1f}%)")

    # Overall status
    print("\n" + "=" * 80)
    all_passed = all(
        r["success_rate"] == 1.0
        for r in all_results.get("individual_backends", {}).values()
    )
    failover_passed = all_results.get("failover", {}).get("success_rate", 0) == 1.0

    if all_passed and failover_passed:
        print("✅ ALL TESTS PASSED - System ready for competition demo")
    else:
        print("❌ SOME TESTS FAILED - Review errors before demo")
    print("=" * 80)


def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(description="Test all LLM backends")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--backend", "-b", type=str, help="Test specific backend only")
    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    print("=" * 80)
    print("LLM Backend Testing Suite")
    print("=" * 80)
    print(f"Test Scenarios: {len(TEST_SCENARIOS)}")
    print(f"Verbose Mode: {args.verbose}")
    print("=" * 80)

    # Initialize multi-backend LLM
    llm = MultiBackendLLM()

    # Get available backends
    backends = llm._get_backends()
    print(f"\nAvailable Backends: {len(backends)}")
    for backend_name, _ in backends:
        print(f"  - {backend_name}")

    all_results = {
        "individual_backends": {},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Test individual backends
    if args.backend:
        # Test specific backend only
        backend_found = False
        for backend_name, backend_func in backends:
            if backend_name == args.backend:
                print(f"\n{'='*80}")
                print(f"Testing Backend: {backend_name}")
                print(f"{'='*80}")

                result = test_single_backend(
                    backend_name, backend_func, TEST_SCENARIOS, args.verbose
                )
                all_results["individual_backends"][backend_name] = result
                backend_found = True
                break

        if not backend_found:
            print(f"\n❌ Backend '{args.backend}' not found")
            print(f"Available backends: {[b[0] for b in backends]}")
            sys.exit(1)
    else:
        # Test all backends
        for backend_name, backend_func in backends:
            print(f"\n{'='*80}")
            print(f"Testing Backend: {backend_name}")
            print(f"{'='*80}")

            result = test_single_backend(
                backend_name, backend_func, TEST_SCENARIOS, args.verbose
            )
            all_results["individual_backends"][backend_name] = result

        # Test deterministic fallback
        print(f"\n{'='*80}")
        print("Testing Deterministic Fallback")
        print(f"{'='*80}")

        fallback_results = {
            "backend": "deterministic_fallback",
            "total_tests": len(TEST_SCENARIOS),
            "successes": 0,
            "failures": 0,
            "latencies": [],
        }

        for scenario in TEST_SCENARIOS:
            try:
                start = time.time()
                result = llm.generate_deterministic_fallback(
                    scenario["query"], scenario["pgx_data"]
                )
                latency = (time.time() - start) * 1000
                fallback_results["latencies"].append(latency)
                fallback_results["successes"] += 1
            except Exception as e:
                fallback_results["failures"] += 1

        if fallback_results["latencies"]:
            fallback_results["avg_latency_ms"] = round(
                mean(fallback_results["latencies"]), 2
            )
            fallback_results["median_latency_ms"] = round(
                median(fallback_results["latencies"]), 2
            )

        fallback_results["success_rate"] = (
            fallback_results["successes"] / fallback_results["total_tests"]
        )
        all_results["individual_backends"]["deterministic_fallback"] = fallback_results

        # Test automatic failover
        print(f"\n{'='*80}")
        print("Testing Automatic Failover")
        print(f"{'='*80}")

        failover_result = test_failover_behavior(llm, TEST_SCENARIOS, args.verbose)
        all_results["failover"] = failover_result

    # Print summary
    print_summary(all_results)

    # Save results to file
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")

    # Exit with appropriate code
    all_passed = all(
        r["success_rate"] == 1.0
        for r in all_results.get("individual_backends", {}).values()
    )
    failover_passed = all_results.get("failover", {}).get("success_rate", 0) >= 0.999

    sys.exit(0 if (all_passed and failover_passed) else 1)


if __name__ == "__main__":
    main()
