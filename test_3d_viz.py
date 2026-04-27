#!/usr/bin/env python3
"""
Test 3D Molecular Visualization

This script tests the 3D visualization functionality for all standard library drugs.
It verifies that SMILES strings can be converted to 3D structures and rendered properly.
"""

import sys

import py3Dmol
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw

# Standard library drugs with SMILES
STANDARD_DRUGS = {
    "Warfarin": "CC(=O)CC(C1=CC=CC=C1)C2=C(O)C3=CC=CC=C3OC2=O",
    "Clopidogrel": "COC(=O)C(C1=CC=CC=C1Cl)N2CCC3=CC=C(C=C32)S",
    "Codeine": "CN1CCC23C4C1CC5=C2C(C(C=C5)O)OC3C(C=C4)O",
    "Ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    "Metoprolol": "CC(C)NCC(O)COC1=CC=C(C=C1)CCOC",
    "Simvastatin": "CCC(C)(C)C(=O)OC1CC(C)C=C2C1C(C)C=C2C",
    "Irinotecan": "CCC1=C2CN3C(=CC4=C(C3=O)COC(=O)C4(CC)O)C2=NC=C1N5CCC(CC5)N6CCCCC6",
}


def test_smiles_parsing(drug_name: str, smiles: str) -> bool:
    """Test if SMILES can be parsed by RDKit."""
    print(f"\n{'='*60}")
    print(f"Testing: {drug_name}")
    print(f"SMILES: {smiles}")
    print(f"{'='*60}")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"❌ FAILED: Could not parse SMILES for {drug_name}")
            return False

        print(f"✅ SMILES parsed successfully")

        # Get molecular properties
        num_atoms = mol.GetNumAtoms()
        num_bonds = mol.GetNumBonds()
        mol_weight = Descriptors.MolWt(mol)

        print(f"   Atoms: {num_atoms}")
        print(f"   Bonds: {num_bonds}")
        print(f"   Molecular Weight: {mol_weight:.2f} g/mol")

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception parsing SMILES: {e}")
        return False


def test_3d_generation(drug_name: str, smiles: str) -> bool:
    """Test if 3D coordinates can be generated."""
    print(f"\n--- Testing 3D Coordinate Generation ---")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"❌ FAILED: Could not parse SMILES")
            return False

        # Add hydrogens
        mol_with_h = Chem.AddHs(mol)
        print(f"✅ Added hydrogens ({mol_with_h.GetNumAtoms()} atoms total)")

        # Try to embed 3D coordinates
        embed_result = -1
        for attempt in range(3):
            try:
                if attempt == 0:
                    embed_result = AllChem.EmbedMolecule(mol_with_h, randomSeed=42)
                elif attempt == 1:
                    embed_result = AllChem.EmbedMolecule(mol_with_h)
                else:
                    embed_result = AllChem.EmbedMolecule(
                        mol_with_h, useRandomCoords=True, maxAttempts=100
                    )

                if embed_result == 0:
                    print(f"✅ 3D coordinates generated (attempt {attempt + 1})")
                    break
            except Exception as e:
                print(f"⚠️  Attempt {attempt + 1} failed: {e}")
                continue

        if embed_result != 0:
            print(f"❌ FAILED: Could not generate 3D coordinates after 3 attempts")
            return False

        # Try to optimize geometry
        try:
            AllChem.MMFFOptimizeMolecule(mol_with_h)
            print(f"✅ Geometry optimized with MMFF")
        except Exception as e:
            print(f"⚠️  Geometry optimization failed (non-critical): {e}")

        # Convert to mol block
        try:
            mol_block = Chem.MolToMolBlock(mol_with_h)
            print(f"✅ Converted to MOL block format ({len(mol_block)} characters)")
        except Exception as e:
            print(f"❌ FAILED: Could not convert to MOL block: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during 3D generation: {e}")
        return False


def test_py3dmol_rendering(drug_name: str, smiles: str) -> bool:
    """Test if py3Dmol can render the molecule."""
    print(f"\n--- Testing py3Dmol Rendering ---")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"❌ FAILED: Could not parse SMILES")
            return False

        mol_with_h = Chem.AddHs(mol)
        embed_result = AllChem.EmbedMolecule(mol_with_h, randomSeed=42)

        if embed_result != 0:
            embed_result = AllChem.EmbedMolecule(mol_with_h)

        if embed_result != 0:
            print(f"❌ FAILED: Could not generate 3D coordinates")
            return False

        try:
            AllChem.MMFFOptimizeMolecule(mol_with_h)
        except Exception:
            pass

        mol_block = Chem.MolToMolBlock(mol_with_h)

        # Create py3Dmol view
        view = py3Dmol.view(width=400, height=300)
        view.addModel(mol_block, "mol")
        view.setStyle(
            {
                "stick": {"colorscheme": "cyanCarbon", "radius": 0.15},
                "sphere": {"scale": 0.25},
            }
        )
        view.setBackgroundColor("#1E293B")
        view.zoomTo()

        print(f"✅ py3Dmol view created successfully")
        print(f"   View object: {type(view)}")

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during py3Dmol rendering: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_2d_fallback(drug_name: str, smiles: str) -> bool:
    """Test if 2D structure can be generated as fallback."""
    print(f"\n--- Testing 2D Fallback ---")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"❌ FAILED: Could not parse SMILES")
            return False

        # Generate 2D image
        img = Draw.MolToImage(mol, size=(400, 300))
        print(f"✅ 2D image generated successfully")
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during 2D generation: {e}")
        return False


def main():
    """Run all tests for all standard library drugs."""
    print("\n" + "=" * 60)
    print("3D MOLECULAR VISUALIZATION TEST SUITE")
    print("=" * 60)

    results = {}

    for drug_name, smiles in STANDARD_DRUGS.items():
        results[drug_name] = {
            "parsing": test_smiles_parsing(drug_name, smiles),
            "3d_generation": test_3d_generation(drug_name, smiles),
            "py3dmol_rendering": test_py3dmol_rendering(drug_name, smiles),
            "2d_fallback": test_2d_fallback(drug_name, smiles),
        }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for drug_name, tests in results.items():
        print(f"\n{drug_name}:")
        for test_name, passed in tests.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {test_name:20s}: {status}")

    # Overall results
    print("\n" + "=" * 60)
    total_tests = len(STANDARD_DRUGS) * 4
    passed_tests = sum(
        sum(1 for passed in tests.values() if passed) for tests in results.values()
    )

    print(f"OVERALL: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {total_tests - passed_tests} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
