#!/usr/bin/env python3
"""
Validation Results Generator

Runs validation tests and generates quantitative metrics for the paper.
Compares predictions against known clinical guidelines (CPIC).
"""

import os
import re
import sys
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent_engine import run_simulation
from src.input_processor import get_drug_fingerprint
from src.vector_search import find_similar_drugs

# Known CYP2D6 substrates and expected outcomes (from CPIC guidelines)
VALIDATION_CASES = [
    {
        "name": "Codeine",
        "smiles": "CN1CC[C@]23C4=C5C=CC(=C4O)Oc4c5c(C[C@@H]1[C@@H]2C=C[C@@H]3O)cc(c4)O",
        "cyp2d6_substrate": True,
        "poor_metabolizer_expected_risk": "High",
        "poor_metabolizer_reason": "Reduced conversion to morphine (active metabolite)",
        "cpic_guideline": "Alternative analgesic recommended for CYP2D6 poor metabolizers",
    },
    {
        "name": "Tramadol",
        "smiles": "CN1C[C@H](CC2=CC=CC=C2)OC[C@H]1C3=CC=CC=C3",
        "cyp2d6_substrate": True,
        "poor_metabolizer_expected_risk": "Medium",
        "poor_metabolizer_reason": "Reduced activation to active metabolite",
        "cpic_guideline": "Consider dose adjustment or alternative",
    },
    {
        "name": "Metoprolol",
        "smiles": "CC(C)OC(=O)C(COc1ccc(C(C)CCN)cc1)O",
        "cyp2d6_substrate": True,
        "poor_metabolizer_expected_risk": "High",
        "poor_metabolizer_reason": "Increased plasma levels, risk of bradycardia",
        "cpic_guideline": "Reduce dose by 50% for poor metabolizers",
    },
    {
        "name": "Paracetamol (Acetaminophen)",
        "smiles": "CC(=O)Nc1ccc(O)cc1",
        "cyp2d6_substrate": False,  # Metabolized by CYP1A2, CYP2E1
        "poor_metabolizer_expected_risk": "Low",
        "poor_metabolizer_reason": "Not CYP2D6 dependent",
        "cpic_guideline": "No CYP2D6-related dose adjustment needed",
    },
]


def create_patient_profile(cyp2d6_status: str) -> str:
    """Create patient profile with specified CYP2D6 status."""
    return f"""ID: VAL-TEST
Age: 45
Genetics: CYP2D6 {cyp2d6_status.replace('_', ' ').title()}
Conditions: None
Lifestyle: Standard"""


def extract_risk_level(prediction: str) -> str:
    """Extract risk level from LLM prediction."""
    prediction_lower = prediction.lower()

    # Try multiple patterns to extract risk level
    patterns = [
        r"risk\s+level[:\s]+(high|medium|low)",  # "RISK LEVEL: High"
        r"\*\s*risk\s+level[:\s]+(high|medium|low)",  # "* RISK LEVEL: High"
        r"risk[:\s]+(high|medium|low)",  # "Risk: High"
        r"(high|medium|low)\s+risk",  # "High Risk" or "Medium Risk"
        r"risk\s+assessment[:\s]+(high|medium|low)",  # "Risk Assessment: High"
    ]

    for pattern in patterns:
        match = re.search(pattern, prediction_lower)
        if match:
            risk = match.group(1).title()
            # Normalize
            if risk.lower() == "high":
                return "High"
            elif risk.lower() == "medium":
                return "Medium"
            elif risk.lower() == "low":
                return "Low"

    # Fallback: look for keywords in context
    if "high" in prediction_lower and (
        "risk" in prediction_lower or "severe" in prediction_lower
    ):
        return "High"
    elif "medium" in prediction_lower and (
        "risk" in prediction_lower or "moderate" in prediction_lower
    ):
        return "Medium"
    elif "low" in prediction_lower and "risk" in prediction_lower:
        return "Low"

    return "Unknown"


def validate_prediction(
    drug_name: str, drug_smiles: str, cyp2d6_status: str, expected_risk: str
) -> Tuple[bool, str, str]:
    """
    Validate prediction against expected outcome.

    Returns: (is_correct, actual_prediction, risk_level)
    """
    try:
        # Generate fingerprint
        fingerprint = get_drug_fingerprint(drug_smiles)

        # Find similar drugs
        similar_drugs = find_similar_drugs(fingerprint, top_k=3)

        # Create patient profile
        patient_profile = create_patient_profile(cyp2d6_status)

        # Check if API key is available
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return (False, "API key not found", "Unknown")

        # Run simulation
        prediction = run_simulation(drug_name, similar_drugs, patient_profile)

        # Extract risk level
        risk_level = extract_risk_level(prediction)

        # Check if prediction matches expected
        is_correct = risk_level.lower() == expected_risk.lower()

        return (is_correct, prediction, risk_level)

    except Exception as e:
        return (False, f"Error: {e}", "Error")


def run_validation_suite() -> Dict:
    """Run complete validation suite."""
    print("=" * 60)
    print("Anukriti Validation Results")
    print("=" * 60)
    print()

    results = []
    correct_predictions = 0
    total_predictions = 0

    # Test poor metabolizer scenarios
    print("Testing CYP2D6 Poor Metabolizer Scenarios:")
    print("-" * 60)

    for case in VALIDATION_CASES:
        if not case.get("cyp2d6_substrate", False):
            continue  # Skip non-CYP2D6 substrates for poor metabolizer test

        expected_risk = case["poor_metabolizer_expected_risk"]
        print(f"\nTesting: {case['name']}")
        print(f"  Expected Risk: {expected_risk}")
        print(f"  CPIC Guideline: {case['cpic_guideline']}")

        is_correct, prediction, risk_level = validate_prediction(
            case["name"], case["smiles"], "poor_metabolizer", expected_risk
        )

        total_predictions += 1
        if is_correct:
            correct_predictions += 1

        status = "✓ CORRECT" if is_correct else "✗ INCORRECT"
        print(f"  Actual Risk: {risk_level}")
        print(f"  Status: {status}")

        if not is_correct:
            print(f"  Expected: {expected_risk}, Got: {risk_level}")
            # Show first 200 chars of prediction for debugging
            print(f"  Prediction preview: {prediction[:200]}...")

        results.append(
            {
                "drug": case["name"],
                "expected_risk": expected_risk,
                "actual_risk": risk_level,
                "is_correct": is_correct,
                "prediction": (
                    prediction[:200] + "..." if len(prediction) > 200 else prediction
                ),
            }
        )

    # Calculate accuracy
    accuracy = (
        (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
    )

    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    print(f"Total Test Cases: {total_predictions}")
    print(f"Correct Predictions: {correct_predictions}")
    print(f"Accuracy: {accuracy:.1f}%")

    # Detailed results
    print("\nDetailed Results:")
    for result in results:
        status = "✓" if result["is_correct"] else "✗"
        print(
            f"  {status} {result['drug']}: Expected {result['expected_risk']}, Got {result['actual_risk']}"
        )

    return {
        "total_cases": total_predictions,
        "correct_predictions": correct_predictions,
        "accuracy": accuracy,
        "results": results,
    }


def generate_paper_summary(validation_stats: Dict):
    """Generate summary for paper."""
    print("\n" + "=" * 60)
    print("Summary for Paper")
    print("=" * 60)
    print(f"Validation Accuracy: {validation_stats['accuracy']:.1f}%")
    print(f"Test Cases: {validation_stats['total_cases']}")
    print(
        f"Correct Predictions: {validation_stats['correct_predictions']}/{validation_stats['total_cases']}"
    )

    print("\nExample Test Case Results:")
    for result in validation_stats["results"][:3]:  # Show first 3
        print(f"\n{result['drug']}:")
        print(f"  Expected Risk: {result['expected_risk']}")
        print(f"  Predicted Risk: {result['actual_risk']}")
        print(f"  Match: {'Yes' if result['is_correct'] else 'No'}")


def main():
    """Main validation function."""
    validation_stats = run_validation_suite()
    generate_paper_summary(validation_stats)

    print("\n✓ Validation complete!")
    print("\nNote: These results can be included in the paper's Results section.")


if __name__ == "__main__":
    main()
