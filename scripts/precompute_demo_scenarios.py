#!/usr/bin/env python3
"""
Pre-compute Demo Scenarios for Offline Mode
Generates and caches demo scenarios for reliable competition demos

This script pre-computes responses for common demo scenarios to ensure:
- Instant response times during demos
- No dependency on LLM availability
- Consistent, high-quality responses
- Offline demo capability

Usage:
    python scripts/precompute_demo_scenarios.py
    python scripts/precompute_demo_scenarios.py --output data/demo_scenarios_cache.json
    python scripts/precompute_demo_scenarios.py --scenarios 20
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

# Add src to path
sys.path.insert(0, ".")

from src.multi_backend_llm import MultiBackendLLM

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Demo scenarios for competition
DEMO_SCENARIOS = [
    # Warfarin scenarios (CYP2C9 + VKORC1)
    {
        "id": "warfarin_poor_metabolizer",
        "drug": "Warfarin",
        "patient": "African ancestry, CYP2C9 *2/*3 (Poor Metabolizer), VKORC1 -1639G>A",
        "context": "CYP2C9 metabolizes warfarin. Poor metabolizers have reduced enzyme activity and increased bleeding risk.",
        "pgx_data": {
            "gene": "CYP2C9",
            "genotype": "*2/*3",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Reduce warfarin dose by 50% and monitor INR closely. Consider alternative anticoagulant.",
        },
    },
    {
        "id": "warfarin_normal_metabolizer",
        "drug": "Warfarin",
        "patient": "European ancestry, CYP2C9 *1/*1 (Normal Metabolizer), VKORC1 -1639G>G",
        "context": "CYP2C9 metabolizes warfarin. Normal metabolizers have standard enzyme activity.",
        "pgx_data": {
            "gene": "CYP2C9",
            "genotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "risk": "Low",
            "recommendation": "Standard warfarin dosing. Monitor INR regularly.",
        },
    },
    # Clopidogrel scenarios (CYP2C19)
    {
        "id": "clopidogrel_poor_metabolizer",
        "drug": "Clopidogrel",
        "patient": "Asian ancestry, CYP2C19 *2/*2 (Poor Metabolizer)",
        "context": "CYP2C19 activates clopidogrel. Poor metabolizers have reduced drug efficacy and increased cardiovascular risk.",
        "pgx_data": {
            "gene": "CYP2C19",
            "genotype": "*2/*2",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Consider alternative antiplatelet therapy (prasugrel or ticagrelor). Avoid clopidogrel.",
        },
    },
    {
        "id": "clopidogrel_rapid_metabolizer",
        "drug": "Clopidogrel",
        "patient": "European ancestry, CYP2C19 *1/*17 (Rapid Metabolizer)",
        "context": "CYP2C19 activates clopidogrel. Rapid metabolizers have increased drug efficacy.",
        "pgx_data": {
            "gene": "CYP2C19",
            "genotype": "*1/*17",
            "phenotype": "Rapid Metabolizer",
            "risk": "Low",
            "recommendation": "Standard clopidogrel dosing. Enhanced antiplatelet effect expected.",
        },
    },
    # Codeine scenarios (CYP2D6)
    {
        "id": "codeine_ultrarapid_metabolizer",
        "drug": "Codeine",
        "patient": "East African ancestry, CYP2D6 *1/*2xN (Ultra-Rapid Metabolizer)",
        "context": "CYP2D6 converts codeine to morphine. Ultra-rapid metabolizers have increased toxicity risk.",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*1/*2xN",
            "phenotype": "Ultra-Rapid Metabolizer",
            "risk": "High",
            "recommendation": "Avoid codeine. Use alternative analgesic (acetaminophen, ibuprofen, or non-opioid).",
        },
    },
    {
        "id": "codeine_poor_metabolizer",
        "drug": "Codeine",
        "patient": "European ancestry, CYP2D6 *4/*4 (Poor Metabolizer)",
        "context": "CYP2D6 converts codeine to morphine. Poor metabolizers have reduced analgesic effect.",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*4/*4",
            "phenotype": "Poor Metabolizer",
            "risk": "Medium",
            "recommendation": "Codeine will be ineffective. Use alternative analgesic (morphine, oxycodone).",
        },
    },
    # Simvastatin scenarios (SLCO1B1)
    {
        "id": "simvastatin_high_risk",
        "drug": "Simvastatin",
        "patient": "Asian ancestry, SLCO1B1 rs4149056 T/T (Poor Function)",
        "context": "SLCO1B1 transports statins into liver. Poor function increases myopathy risk.",
        "pgx_data": {
            "gene": "SLCO1B1",
            "genotype": "rs4149056 T/T",
            "phenotype": "Poor Function",
            "risk": "High",
            "recommendation": "Reduce simvastatin dose to ≤20mg daily or use alternative statin (pravastatin, rosuvastatin).",
        },
    },
    {
        "id": "simvastatin_normal_function",
        "drug": "Simvastatin",
        "patient": "European ancestry, SLCO1B1 rs4149056 C/C (Normal Function)",
        "context": "SLCO1B1 transports statins into liver. Normal function has standard myopathy risk.",
        "pgx_data": {
            "gene": "SLCO1B1",
            "genotype": "rs4149056 C/C",
            "phenotype": "Normal Function",
            "risk": "Low",
            "recommendation": "Standard simvastatin dosing. Monitor for muscle symptoms.",
        },
    },
    # Irinotecan scenarios (UGT1A1)
    {
        "id": "irinotecan_poor_metabolizer",
        "drug": "Irinotecan",
        "patient": "African ancestry, UGT1A1 *28/*28 (Poor Metabolizer)",
        "context": "UGT1A1 metabolizes irinotecan. Poor metabolizers have increased toxicity risk.",
        "pgx_data": {
            "gene": "UGT1A1",
            "genotype": "*28/*28",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Reduce irinotecan dose by 30-50%. Monitor for severe neutropenia and diarrhea.",
        },
    },
    {
        "id": "irinotecan_normal_metabolizer",
        "drug": "Irinotecan",
        "patient": "European ancestry, UGT1A1 *1/*1 (Normal Metabolizer)",
        "context": "UGT1A1 metabolizes irinotecan. Normal metabolizers have standard toxicity risk.",
        "pgx_data": {
            "gene": "UGT1A1",
            "genotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "risk": "Low",
            "recommendation": "Standard irinotecan dosing. Monitor for toxicity.",
        },
    },
    # Metoprolol scenarios (CYP2D6)
    {
        "id": "metoprolol_poor_metabolizer",
        "drug": "Metoprolol",
        "patient": "European ancestry, CYP2D6 *4/*4 (Poor Metabolizer)",
        "context": "CYP2D6 metabolizes metoprolol. Poor metabolizers have increased drug levels and bradycardia risk.",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*4/*4",
            "phenotype": "Poor Metabolizer",
            "risk": "Medium",
            "recommendation": "Reduce metoprolol dose by 50%. Monitor heart rate and blood pressure closely.",
        },
    },
    {
        "id": "metoprolol_ultrarapid_metabolizer",
        "drug": "Metoprolol",
        "patient": "East African ancestry, CYP2D6 *1/*2xN (Ultra-Rapid Metabolizer)",
        "context": "CYP2D6 metabolizes metoprolol. Ultra-rapid metabolizers have reduced drug efficacy.",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*1/*2xN",
            "phenotype": "Ultra-Rapid Metabolizer",
            "risk": "Medium",
            "recommendation": "Consider alternative beta-blocker not metabolized by CYP2D6 (atenolol, bisoprolol).",
        },
    },
    # Azathioprine scenarios (TPMT)
    {
        "id": "azathioprine_poor_metabolizer",
        "drug": "Azathioprine",
        "patient": "European ancestry, TPMT *3A/*3A (Poor Metabolizer)",
        "context": "TPMT metabolizes azathioprine. Poor metabolizers have severe myelosuppression risk.",
        "pgx_data": {
            "gene": "TPMT",
            "genotype": "*3A/*3A",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Reduce azathioprine dose by 90% or avoid. Consider alternative immunosuppressant.",
        },
    },
    {
        "id": "azathioprine_intermediate_metabolizer",
        "drug": "Azathioprine",
        "patient": "Asian ancestry, TPMT *1/*3A (Intermediate Metabolizer)",
        "context": "TPMT metabolizes azathioprine. Intermediate metabolizers have moderate myelosuppression risk.",
        "pgx_data": {
            "gene": "TPMT",
            "genotype": "*1/*3A",
            "phenotype": "Intermediate Metabolizer",
            "risk": "Medium",
            "recommendation": "Reduce azathioprine dose by 50%. Monitor CBC closely.",
        },
    },
    # Fluorouracil scenarios (DPYD)
    {
        "id": "fluorouracil_poor_metabolizer",
        "drug": "Fluorouracil",
        "patient": "European ancestry, DPYD *2A/*2A (Poor Metabolizer)",
        "context": "DPYD metabolizes fluorouracil. Poor metabolizers have severe toxicity risk.",
        "pgx_data": {
            "gene": "DPYD",
            "genotype": "*2A/*2A",
            "phenotype": "Poor Metabolizer",
            "risk": "High",
            "recommendation": "Avoid fluorouracil. Consider alternative chemotherapy regimen.",
        },
    },
    {
        "id": "fluorouracil_intermediate_metabolizer",
        "drug": "Fluorouracil",
        "patient": "European ancestry, DPYD *1/*2A (Intermediate Metabolizer)",
        "context": "DPYD metabolizes fluorouracil. Intermediate metabolizers have moderate toxicity risk.",
        "pgx_data": {
            "gene": "DPYD",
            "genotype": "*1/*2A",
            "phenotype": "Intermediate Metabolizer",
            "risk": "Medium",
            "recommendation": "Reduce fluorouracil dose by 50%. Monitor for severe toxicity.",
        },
    },
    # Abacavir scenarios (HLA-B*57:01)
    {
        "id": "abacavir_positive",
        "drug": "Abacavir",
        "patient": "European ancestry, HLA-B*57:01 positive",
        "context": "HLA-B*57:01 increases abacavir hypersensitivity risk.",
        "pgx_data": {
            "gene": "HLA-B",
            "genotype": "*57:01 positive",
            "phenotype": "High Risk",
            "risk": "High",
            "recommendation": "Avoid abacavir. Use alternative antiretroviral (tenofovir, emtricitabine).",
        },
    },
    {
        "id": "abacavir_negative",
        "drug": "Abacavir",
        "patient": "Asian ancestry, HLA-B*57:01 negative",
        "context": "HLA-B*57:01 negative has low abacavir hypersensitivity risk.",
        "pgx_data": {
            "gene": "HLA-B",
            "genotype": "*57:01 negative",
            "phenotype": "Low Risk",
            "risk": "Low",
            "recommendation": "Abacavir can be used. Monitor for hypersensitivity symptoms.",
        },
    },
    # Omeprazole scenarios (CYP2C19)
    {
        "id": "omeprazole_poor_metabolizer",
        "drug": "Omeprazole",
        "patient": "Asian ancestry, CYP2C19 *2/*2 (Poor Metabolizer)",
        "context": "CYP2C19 metabolizes omeprazole. Poor metabolizers have increased drug efficacy.",
        "pgx_data": {
            "gene": "CYP2C19",
            "genotype": "*2/*2",
            "phenotype": "Poor Metabolizer",
            "risk": "Low",
            "recommendation": "Standard omeprazole dosing. Enhanced acid suppression expected.",
        },
    },
    {
        "id": "omeprazole_rapid_metabolizer",
        "drug": "Omeprazole",
        "patient": "European ancestry, CYP2C19 *17/*17 (Rapid Metabolizer)",
        "context": "CYP2C19 metabolizes omeprazole. Rapid metabolizers have reduced drug efficacy.",
        "pgx_data": {
            "gene": "CYP2C19",
            "genotype": "*17/*17",
            "phenotype": "Rapid Metabolizer",
            "risk": "Medium",
            "recommendation": "Consider higher omeprazole dose or alternative PPI (pantoprazole).",
        },
    },
    # Tramadol scenarios (CYP2D6)
    {
        "id": "tramadol_poor_metabolizer",
        "drug": "Tramadol",
        "patient": "European ancestry, CYP2D6 *4/*4 (Poor Metabolizer)",
        "context": "CYP2D6 activates tramadol. Poor metabolizers have reduced analgesic effect.",
        "pgx_data": {
            "gene": "CYP2D6",
            "genotype": "*4/*4",
            "phenotype": "Poor Metabolizer",
            "risk": "Medium",
            "recommendation": "Tramadol will be ineffective. Use alternative analgesic (morphine, oxycodone).",
        },
    },
]


def precompute_scenario(
    llm: MultiBackendLLM, scenario: Dict[str, Any], verbose: bool = False
) -> Dict[str, Any]:
    """
    Pre-compute a single demo scenario

    Args:
        llm: MultiBackendLLM instance
        scenario: Scenario definition
        verbose: Print progress

    Returns:
        Dict with pre-computed response
    """
    if verbose:
        print(f"  Computing: {scenario['id']}")

    try:
        start = time.time()

        result = llm.generate_with_fallback(
            context=scenario["context"],
            query=f"What is the effect of {scenario['pgx_data']['genotype']} on {scenario['drug']}?",
            pgx_data=scenario["pgx_data"],
        )

        latency = (time.time() - start) * 1000

        if verbose:
            print(
                f"    ✅ Success: {latency:.0f}ms, backend: {result.get('backend_used')}"
            )

        return {
            "id": scenario["id"],
            "drug": scenario["drug"],
            "patient": scenario["patient"],
            "response": result.get("response", ""),
            "backend_used": result.get("backend_used"),
            "fallback_occurred": result.get("fallback_occurred", False),
            "attempts": result.get("attempts", 1),
            "latency_ms": round(latency, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pgx_data": scenario["pgx_data"],
        }

    except Exception as e:
        logger.error(f"Failed to compute scenario {scenario['id']}: {e}")
        return {
            "id": scenario["id"],
            "drug": scenario["drug"],
            "patient": scenario["patient"],
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Pre-compute demo scenarios")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/demo_scenarios_cache.json",
        help="Output file path",
    )
    parser.add_argument(
        "--scenarios",
        "-s",
        type=int,
        default=len(DEMO_SCENARIOS),
        help="Number of scenarios to compute",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=" * 80)
    print("Demo Scenario Pre-computation")
    print("=" * 80)
    print(f"Total Scenarios: {min(args.scenarios, len(DEMO_SCENARIOS))}")
    print(f"Output File: {args.output}")
    print("=" * 80)

    # Initialize multi-backend LLM
    llm = MultiBackendLLM()

    # Pre-compute scenarios
    results = []
    scenarios_to_compute = DEMO_SCENARIOS[: args.scenarios]

    for i, scenario in enumerate(scenarios_to_compute, 1):
        print(
            f"\n[{i}/{len(scenarios_to_compute)}] {scenario['drug']} - {scenario['id']}"
        )
        result = precompute_scenario(llm, scenario, args.verbose)
        results.append(result)

    # Save results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    cache_data = {
        "version": "1.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenarios": len(results),
        "scenarios": results,
    }

    with open(args.output, "w") as f:
        json.dump(cache_data, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("Pre-computation Summary")
    print("=" * 80)

    successes = sum(1 for r in results if "response" in r)
    failures = sum(1 for r in results if "error" in r)

    print(f"Total Scenarios: {len(results)}")
    print(f"Successes: {successes} ({successes/len(results)*100:.1f}%)")
    print(f"Failures: {failures}")

    if successes > 0:
        latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
        print(f"Avg Latency: {sum(latencies)/len(latencies):.0f}ms")

        backends = {}
        for r in results:
            if "backend_used" in r:
                backends[r["backend_used"]] = backends.get(r["backend_used"], 0) + 1

        print("\nBackend Usage:")
        for backend, count in backends.items():
            print(f"  {backend}: {count} ({count/len(results)*100:.1f}%)")

    print(f"\n✅ Results saved to: {args.output}")
    print("=" * 80)

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
