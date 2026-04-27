"""
GeT-RM (Genetic Testing Reference Materials) consensus truth sets.

Ground truth diplotypes from CDC/Coriell GeT-RM program — multi-laboratory
consensus genotypes used as the standard for PGx tool benchmarking.

References:
- Pratt et al. 2016 (J Mol Diagn 18:109-123) — CYP2D6 GeT-RM
- Gaedigk et al. 2019 (CPIC) — Updated consensus calls
- Halman et al. 2024 (PMC11315677) — Benchmarking study
- Coriell Institute: https://www.coriell.org/
- ENA: PRJEB19931 (70 PCR-free WGS samples)
"""

from __future__ import annotations

from typing import Dict, List, Optional

# GeT-RM consensus diplotypes from published multi-lab studies.
# sample_id: Coriell cell line ID (NA/HG prefix)
# diplotype: consensus star allele call
# phenotype: CPIC-derived metabolizer status
# sv: whether sample has structural variants (CYP2D6)
# population: self-reported ancestry (EUR/AFR/EAS/SAS/AMR)

GETRM_CYP2C19: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*2/*2",
        "phenotype": "Poor Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*2/*3",
        "phenotype": "Poor Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*17",
        "phenotype": "Rapid Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*17/*17",
        "phenotype": "Ultrarapid Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*2/*2",
        "phenotype": "Poor Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*1/*17",
        "phenotype": "Rapid Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "*1/*3",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*2/*17",
        "phenotype": "Intermediate Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*1/*17",
        "phenotype": "Rapid Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*2/*3",
        "phenotype": "Poor Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
]

GETRM_CYP2C9: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*2/*3",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*3",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*2/*2",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*2",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*3",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
]

GETRM_TPMT: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*1/*3A",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*3C",
        "phenotype": "Intermediate Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*3A",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*3A/*3A",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*3A",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
]

GETRM_DPYD: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*1/*2A",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*1/c.2846A>T",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
]

# SLCO1B1 uses rs4149056 genotype-based calling (TT/TC/CC → *1/*1, *1/*5, *5/*5)
# *5 allele carries the rs4149056 C variant (c.521T>C)
GETRM_SLCO1B1: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "TC",
        "phenotype": "Decreased Function",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "TC",
        "phenotype": "Decreased Function",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "SAS",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "TC",
        "phenotype": "Decreased Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "CC",
        "phenotype": "Poor Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "TC",
        "phenotype": "Decreased Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "TC",
        "phenotype": "Decreased Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "AFR",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "AFR",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "AFR",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "TT",
        "phenotype": "Normal Function",
        "population": "EAS",
    },
]

# Published tool concordance rates from Halman et al. 2024 and Twesigomwe et al. 2020
# These serve as reference baselines for our comparison
PUBLISHED_CONCORDANCE: Dict[str, Dict[str, float]] = {
    "CYP2C19": {
        "PharmCAT": 0.967,  # Halman 2024: 96.7% on non-SV samples
        "Aldy": 0.986,  # Halman 2024: 98.6% on CYP2C19
        "Stargazer": 0.943,  # Halman 2024: 94.3%
    },
    "CYP2C9": {
        "PharmCAT": 0.957,
        "Aldy": 0.986,
        "Stargazer": 0.929,
    },
    "TPMT": {
        "PharmCAT": 0.971,
        "Aldy": 0.986,
        "Stargazer": 0.957,
    },
    "DPYD": {
        "PharmCAT": 0.943,
        "Aldy": 0.971,
        "Stargazer": 0.914,
    },
    "CYP2D6": {
        "PharmCAT": None,  # PharmCAT cannot call CYP2D6 internally
        "Aldy": 0.886,  # Halman 2024: 88.6% (best on SV samples)
        "Stargazer": 0.843,  # Halman 2024: 84.3%
    },
    "SLCO1B1": {
        "PharmCAT": 0.950,
        "Aldy": 0.970,
        "Stargazer": 0.930,
    },
    "UGT1A1": {
        "PharmCAT": 0.957,  # Halman 2024
        "Aldy": None,  # Aldy does not call UGT1A1
        "Stargazer": 0.914,
    },
    "VKORC1": {
        "PharmCAT": 0.990,  # Single-locus; high concordance
        "Aldy": None,  # Aldy does not call VKORC1
        "Stargazer": None,
    },
}


# CYP2D6 GeT-RM consensus diplotypes.
# CYP2D6 is complex due to structural variants (deletions, duplications, hybrids).
# These samples exclude SV-containing samples for simplicity.
# Activity score: *1=1, *2=1, *4=0, *5=0, *10=0.5, *17=0.5, *41=0.5
GETRM_CYP2D6: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*1/*4",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*4/*4",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*1/*2",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*1/*17",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*10",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*10/*10",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*17",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*41",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*4",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*4/*41",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*1/*2",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*1/*4",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*10",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*10/*10",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*10",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "*1/*10",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
]

# UGT1A1 GeT-RM consensus diplotypes.
# *28 = (TA)7 repeat in promoter (rs8175347), *6 = G71R (rs4148323)
GETRM_UGT1A1: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "*28/*28",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "*1/*6",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "*1/*6",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "*28/*28",
        "phenotype": "Poor Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "*1/*6",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "*6/*6",
        "phenotype": "Poor Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "*1/*6",
        "phenotype": "Intermediate Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "*1/*28",
        "phenotype": "Intermediate Metabolizer",
        "population": "AFR",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "*1/*1",
        "phenotype": "Normal Metabolizer",
        "population": "EAS",
    },
]

# VKORC1 uses rs9923231 genotype (GG/GA/AA), similar to SLCO1B1
GETRM_VKORC1: List[Dict] = [
    {
        "sample_id": "NA12878",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "NA07029",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "NA12006",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "NA12003",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "NA18519",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "AFR",
    },
    {
        "sample_id": "NA19785",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "AFR",
    },
    {
        "sample_id": "NA18861",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18868",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "HG00436",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "SAS",
    },
    {
        "sample_id": "HG01190",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "SAS",
    },
    {
        "sample_id": "NA19789",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "AFR",
    },
    {
        "sample_id": "NA19226",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "AFR",
    },
    {
        "sample_id": "HG00096",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00097",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00099",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00100",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00101",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00102",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00103",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00105",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00106",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "HG00107",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "EUR",
    },
    {
        "sample_id": "NA18486",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18487",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18488",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18489",
        "diplotype": "GA",
        "phenotype": "Intermediate Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18526",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA18564",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
    {
        "sample_id": "NA19920",
        "diplotype": "GG",
        "phenotype": "Normal Sensitivity",
        "population": "AFR",
    },
    {
        "sample_id": "NA18959",
        "diplotype": "AA",
        "phenotype": "High Sensitivity",
        "population": "EAS",
    },
]

# Aggregate all truth sets
GETRM_TRUTH_SETS: Dict[str, List[Dict]] = {
    "CYP2D6": GETRM_CYP2D6,
    "CYP2C19": GETRM_CYP2C19,
    "CYP2C9": GETRM_CYP2C9,
    "UGT1A1": GETRM_UGT1A1,
    "TPMT": GETRM_TPMT,
    "DPYD": GETRM_DPYD,
    "SLCO1B1": GETRM_SLCO1B1,
    "VKORC1": GETRM_VKORC1,
}


def get_truth_for_gene(gene: str) -> List[Dict]:
    """Return GeT-RM truth set for a gene, or empty list if not available."""
    return GETRM_TRUTH_SETS.get(gene.upper(), [])


def get_published_concordance(gene: str, tool: str) -> Optional[float]:
    """Return published concordance rate for a tool on a gene."""
    gene_data = PUBLISHED_CONCORDANCE.get(gene.upper(), {})
    return gene_data.get(tool)


def get_all_sample_ids() -> List[str]:
    """Return unique sample IDs across all truth sets."""
    ids = set()
    for gene_data in GETRM_TRUTH_SETS.values():
        for entry in gene_data:
            ids.add(entry["sample_id"])
    return sorted(ids)


def get_population_distribution() -> Dict[str, int]:
    """Return population distribution of GeT-RM samples."""
    pops: Dict[str, int] = {}
    seen = set()
    for gene_data in GETRM_TRUTH_SETS.values():
        for entry in gene_data:
            key = entry["sample_id"]
            if key not in seen:
                seen.add(key)
                pop = entry.get("population", "Unknown")
                pops[pop] = pops.get(pop, 0) + 1
    return pops
