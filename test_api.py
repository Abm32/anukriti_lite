#!/usr/bin/env python3
"""
Test script for Anukriti AI API

Tests both local and deployed API endpoints.
"""

import json
import sys
import time

import requests


def test_health_check(base_url: str):
    """Test the health check endpoint"""
    print(f"\n🔍 Testing Health Check: {base_url}/")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_analyze_endpoint(base_url: str, test_case: dict):
    """Test the analyze endpoint"""
    print(f"\n🧪 Testing Analysis: {test_case['name']}")
    print(f"Drug: {test_case['drug_name']}")

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/analyze",
            json=test_case["payload"],
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        elapsed_time = time.time() - start_time

        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {elapsed_time:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!")
            print(f"Risk Level: {data.get('risk_level', 'N/A')}")
            print(f"\nFull Result:")
            print("-" * 60)
            print(data.get("result", "No result"))
            print("-" * 60)
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all API tests"""
    # Determine which URL to test
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        # Default to local
        base_url = "http://localhost:8000"

    print("=" * 60)
    print("🧬 Anukriti AI API Test Suite")
    print("=" * 60)
    print(f"Testing API at: {base_url}")

    # Test cases
    test_cases = [
        {
            "name": "Warfarin - High Risk (CYP2C9 Poor Metabolizer)",
            "drug_name": "Warfarin",
            "payload": {
                "drug_name": "Warfarin",
                "drug_smiles": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
                "patient_profile": """ID: HG00096
Age: 45
Genetics: CYP2C9 Poor Metabolizer
Conditions: Atrial Fibrillation
Lifestyle: Non-smoker, Moderate alcohol""",
                "similar_drugs": ["Warfarin (CYP2C9 substrate, bleeding risk)"],
            },
        },
        {
            "name": "Codeine - High Risk (CYP2D6 Poor Metabolizer)",
            "drug_name": "Codeine",
            "payload": {
                "drug_name": "Codeine",
                "patient_profile": """ID: SP-02
Age: 52
Genetics: CYP2D6 Poor Metabolizer
Conditions: Chronic Pain (Post-surgical)
Lifestyle: Non-smoker, No alcohol""",
                "similar_drugs": ["Codeine (CYP2D6 substrate, prodrug activation)"],
            },
        },
        {
            "name": "Clopidogrel - Medium Risk (CYP2C19 Poor Metabolizer)",
            "drug_name": "Clopidogrel",
            "payload": {
                "drug_name": "Clopidogrel",
                "patient_profile": """ID: SP-03
Age: 58
Genetics: CYP2C19 Poor Metabolizer
Conditions: Recent Myocardial Infarction
Lifestyle: Former smoker, No alcohol""",
                "similar_drugs": ["Clopidogrel (CYP2C19 substrate, antiplatelet)"],
            },
        },
    ]

    # Run tests
    results = []

    # Test health check
    health_ok = test_health_check(base_url)
    results.append(("Health Check", health_ok))

    if not health_ok:
        print("\n⚠️ Health check failed. API may not be running.")
        print("To start the API locally, run:")
        print("  python api.py")
        return

    # Test analyze endpoint with different cases
    for test_case in test_cases:
        result = test_analyze_endpoint(base_url, test_case)
        results.append((test_case["name"], result))
        time.sleep(1)  # Brief pause between tests

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
