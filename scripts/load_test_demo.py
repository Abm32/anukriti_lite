#!/usr/bin/env python3
"""
Load Test Demo for Competition Traffic
Simulates high-traffic scenarios to validate system reliability

This script simulates competition demo traffic to ensure:
- 99.9% uptime under load
- <2s p95 latency
- Graceful degradation under stress
- Multi-backend failover works at scale

Usage:
    python scripts/load_test_demo.py
    python scripts/load_test_demo.py --users 500 --duration 300
    python scripts/load_test_demo.py --url https://anukriti.abhimanyurb.com/analyze
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from statistics import mean, median, stdev
from typing import Any, Dict, List

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Test scenarios for load testing
TEST_SCENARIOS = [
    {
        "drug_name": "Warfarin",
        "patient_profile": "African ancestry, CYP2C9 *2/*3 (Poor Metabolizer), VKORC1 -1639G>A",
        "similar_drugs": [],
    },
    {
        "drug_name": "Clopidogrel",
        "patient_profile": "Asian ancestry, CYP2C19 *2/*2 (Poor Metabolizer)",
        "similar_drugs": [],
    },
    {
        "drug_name": "Codeine",
        "patient_profile": "East African ancestry, CYP2D6 *1/*2xN (Ultra-Rapid Metabolizer)",
        "similar_drugs": [],
    },
    {
        "drug_name": "Simvastatin",
        "patient_profile": "Asian ancestry, SLCO1B1 rs4149056 T/T (Poor Function)",
        "similar_drugs": [],
    },
    {
        "drug_name": "Metoprolol",
        "patient_profile": "European ancestry, CYP2D6 *4/*4 (Poor Metabolizer)",
        "similar_drugs": [],
    },
]


async def send_request(
    session: aiohttp.ClientSession, url: str, scenario: Dict[str, Any], request_id: int
) -> Dict[str, Any]:
    """
    Send a single test request

    Args:
        session: aiohttp session
        url: API endpoint URL
        scenario: Test scenario
        request_id: Unique request identifier

    Returns:
        Dict with request result
    """
    start = time.time()

    try:
        async with session.post(
            url, json=scenario, timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            status = response.status

            if status == 200:
                data = await response.json()
                latency = (time.time() - start) * 1000

                return {
                    "request_id": request_id,
                    "success": True,
                    "status": status,
                    "latency_ms": latency,
                    "backend_used": data.get("backend_used", "unknown"),
                    "fallback_occurred": data.get("fallback_occurred", False),
                }
            else:
                error_text = await response.text()
                latency = (time.time() - start) * 1000

                return {
                    "request_id": request_id,
                    "success": False,
                    "status": status,
                    "latency_ms": latency,
                    "error": error_text[:200],
                }

    except asyncio.TimeoutError:
        latency = (time.time() - start) * 1000
        return {
            "request_id": request_id,
            "success": False,
            "status": 0,
            "latency_ms": latency,
            "error": "Request timeout (>30s)",
        }

    except Exception as e:
        latency = (time.time() - start) * 1000
        return {
            "request_id": request_id,
            "success": False,
            "status": 0,
            "latency_ms": latency,
            "error": str(e)[:200],
        }


async def load_test_burst(
    url: str,
    concurrent_users: int,
    scenarios: List[Dict[str, Any]],
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Execute a burst of concurrent requests

    Args:
        url: API endpoint URL
        concurrent_users: Number of concurrent requests
        scenarios: List of test scenarios
        verbose: Print progress

    Returns:
        List of request results
    """
    if verbose:
        logger.info(f"Starting burst: {concurrent_users} concurrent requests")

    async with aiohttp.ClientSession() as session:
        tasks = []

        for i in range(concurrent_users):
            # Rotate through scenarios
            scenario = scenarios[i % len(scenarios)]
            task = send_request(session, url, scenario, i)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

    if verbose:
        successes = sum(1 for r in results if r["success"])
        logger.info(f"Burst complete: {successes}/{concurrent_users} successful")

    return results


async def load_test_sustained(
    url: str,
    concurrent_users: int,
    duration_seconds: int,
    scenarios: List[Dict[str, Any]],
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Execute sustained load test over time

    Args:
        url: API endpoint URL
        concurrent_users: Number of concurrent users
        duration_seconds: Test duration in seconds
        scenarios: List of test scenarios
        verbose: Print progress

    Returns:
        List of all request results
    """
    logger.info(
        f"Starting sustained load test: {concurrent_users} users for {duration_seconds}s"
    )

    all_results = []
    start_time = time.time()
    request_id = 0

    async with aiohttp.ClientSession() as session:
        while (time.time() - start_time) < duration_seconds:
            # Send batch of requests
            tasks = []
            batch_size = min(concurrent_users, 50)  # Limit batch size

            for i in range(batch_size):
                scenario = scenarios[request_id % len(scenarios)]
                task = send_request(session, url, scenario, request_id)
                tasks.append(task)
                request_id += 1

            batch_results = await asyncio.gather(*tasks)
            all_results.extend(batch_results)

            if verbose and request_id % 100 == 0:
                elapsed = time.time() - start_time
                rate = request_id / elapsed
                logger.info(f"Progress: {request_id} requests, {rate:.1f} req/s")

            # Small delay between batches
            await asyncio.sleep(0.1)

    logger.info(f"Sustained load test complete: {len(all_results)} total requests")
    return all_results


def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze load test results

    Args:
        results: List of request results

    Returns:
        Dict with analysis metrics
    """
    total_requests = len(results)
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    # Success rate
    success_rate = len(successes) / total_requests if total_requests > 0 else 0

    # Latency statistics
    latencies = [r["latency_ms"] for r in successes]

    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[int(len(latencies) * 0.50)]
        p95 = latencies_sorted[int(len(latencies) * 0.95)]
        p99 = latencies_sorted[int(len(latencies) * 0.99)]

        latency_stats = {
            "min": round(min(latencies), 2),
            "max": round(max(latencies), 2),
            "mean": round(mean(latencies), 2),
            "median": round(median(latencies), 2),
            "stdev": round(stdev(latencies), 2) if len(latencies) > 1 else 0,
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
        }
    else:
        latency_stats = None

    # Backend usage
    backend_usage = {}
    for r in successes:
        backend = r.get("backend_used", "unknown")
        backend_usage[backend] = backend_usage.get(backend, 0) + 1

    # Fallback rate
    fallbacks = sum(1 for r in successes if r.get("fallback_occurred", False))
    fallback_rate = fallbacks / len(successes) if successes else 0

    # Error analysis
    error_types = {}
    for r in failures:
        error = r.get("error", "Unknown error")[:50]
        error_types[error] = error_types.get(error, 0) + 1

    return {
        "total_requests": total_requests,
        "successes": len(successes),
        "failures": len(failures),
        "success_rate": success_rate,
        "latency_stats": latency_stats,
        "backend_usage": backend_usage,
        "fallback_rate": fallback_rate,
        "error_types": error_types,
    }


def print_results(analysis: Dict[str, Any], test_type: str) -> None:
    """Print load test results"""
    print("\n" + "=" * 80)
    print(f"Load Test Results - {test_type}")
    print("=" * 80)

    # Overall metrics
    print(f"\nTotal Requests: {analysis['total_requests']}")
    print(f"Successes: {analysis['successes']} ({analysis['success_rate']*100:.2f}%)")
    print(f"Failures: {analysis['failures']} ({(1-analysis['success_rate'])*100:.2f}%)")

    # Latency statistics
    if analysis["latency_stats"]:
        stats = analysis["latency_stats"]
        print("\nLatency Statistics:")
        print(f"  Min: {stats['min']:.0f}ms")
        print(f"  Max: {stats['max']:.0f}ms")
        print(f"  Mean: {stats['mean']:.0f}ms")
        print(f"  Median (P50): {stats['median']:.0f}ms")
        print(f"  P95: {stats['p95']:.0f}ms")
        print(f"  P99: {stats['p99']:.0f}ms")
        print(f"  StdDev: {stats['stdev']:.0f}ms")

    # Backend usage
    if analysis["backend_usage"]:
        print("\nBackend Usage:")
        for backend, count in analysis["backend_usage"].items():
            percentage = count / analysis["successes"] * 100
            print(f"  {backend}: {count} ({percentage:.1f}%)")

    # Fallback rate
    print(f"\nFallback Rate: {analysis['fallback_rate']*100:.1f}%")

    # Error types
    if analysis["error_types"]:
        print("\nError Types:")
        for error, count in list(analysis["error_types"].items())[:5]:
            print(f"  {error}: {count}")

    # Success criteria
    print("\n" + "=" * 80)
    print("Success Criteria:")
    print("=" * 80)

    uptime_pass = analysis["success_rate"] >= 0.999
    latency_pass = analysis["latency_stats"] and analysis["latency_stats"]["p95"] < 2000

    print(
        f"✅ Uptime ≥99.9%: {'PASS' if uptime_pass else 'FAIL'} ({analysis['success_rate']*100:.2f}%)"
    )

    if analysis["latency_stats"]:
        print(
            f"✅ P95 Latency <2s: {'PASS' if latency_pass else 'FAIL'} ({analysis['latency_stats']['p95']:.0f}ms)"
        )
    else:
        print("❌ P95 Latency <2s: FAIL (no successful requests)")

    overall_pass = uptime_pass and latency_pass
    print("\n" + "=" * 80)
    if overall_pass:
        print("✅ LOAD TEST PASSED - System ready for competition demo")
    else:
        print("❌ LOAD TEST FAILED - Review performance issues")
    print("=" * 80)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Load test demo for competition")
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        default="http://localhost:8000/analyze",
        help="API endpoint URL",
    )
    parser.add_argument(
        "--users", "-n", type=int, default=500, help="Number of concurrent users"
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=300,
        help="Test duration in seconds (for sustained test)",
    )
    parser.add_argument(
        "--test-type",
        "-t",
        type=str,
        default="burst",
        choices=["burst", "sustained", "both"],
        help="Test type: burst, sustained, or both",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    print("=" * 80)
    print("Load Testing Suite")
    print("=" * 80)
    print(f"URL: {args.url}")
    print(f"Concurrent Users: {args.users}")
    print(f"Test Type: {args.test_type}")
    if args.test_type in ["sustained", "both"]:
        print(f"Duration: {args.duration}s")
    print("=" * 80)

    all_results = {}

    # Burst test
    if args.test_type in ["burst", "both"]:
        print("\n" + "=" * 80)
        print("Running Burst Test")
        print("=" * 80)

        burst_results = asyncio.run(
            load_test_burst(args.url, args.users, TEST_SCENARIOS, args.verbose)
        )

        burst_analysis = analyze_results(burst_results)
        print_results(burst_analysis, "Burst Test")
        all_results["burst"] = burst_analysis

    # Sustained test
    if args.test_type in ["sustained", "both"]:
        print("\n" + "=" * 80)
        print("Running Sustained Test")
        print("=" * 80)

        sustained_results = asyncio.run(
            load_test_sustained(
                args.url, args.users, args.duration, TEST_SCENARIOS, args.verbose
            )
        )

        sustained_analysis = analyze_results(sustained_results)
        print_results(sustained_analysis, "Sustained Test")
        all_results["sustained"] = sustained_analysis

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")

    # Exit with appropriate code
    if args.test_type == "burst":
        passed = all_results["burst"]["success_rate"] >= 0.999
    elif args.test_type == "sustained":
        passed = all_results["sustained"]["success_rate"] >= 0.999
    else:  # both
        passed = (
            all_results["burst"]["success_rate"] >= 0.999
            and all_results["sustained"]["success_rate"] >= 0.999
        )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
