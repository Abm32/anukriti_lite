# src/pgx_triggers.py

"""
Drug → Gene trigger map (CPIC-style).

We only surface PGx interpretations when the drug being analyzed
has a guideline-relevant gene.

Example:
- Warfarin → CYP2C9 + VKORC1
- Simvastatin → SLCO1B1
- Clopidogrel → CYP2C19
"""

DRUG_GENE_TRIGGERS = {
    # Statins (SLCO1B1 + CYP3A4)
    "simvastatin": ["SLCO1B1", "CYP3A4"],
    "atorvastatin": ["SLCO1B1", "CYP3A4"],
    "rosuvastatin": ["SLCO1B1"],
    "pravastatin": ["SLCO1B1"],
    "lovastatin": ["SLCO1B1", "CYP3A4"],
    "fluvastatin": ["SLCO1B1"],
    "pitavastatin": ["SLCO1B1"],
    # Warfarin
    "warfarin": ["CYP2C9", "VKORC1"],
    # Clopidogrel
    "clopidogrel": ["CYP2C19"],
    # CYP2D6 substrates
    "codeine": ["CYP2D6"],
    "tramadol": ["CYP2D6"],
    "metoprolol": ["CYP2D6"],
    "dextromethorphan": ["CYP2D6"],
    # Thiopurines (TPMT)
    "azathioprine": ["TPMT"],
    "mercaptopurine": ["TPMT"],
    "thioguanine": ["TPMT"],
    # Fluoropyrimidines (DPYD)
    "fluorouracil": ["DPYD"],
    "capecitabine": ["DPYD"],
    "tegafur": ["DPYD"],
    # Abacavir hypersensitivity (HLA-B*57:01 proxy)
    "abacavir": ["HLA_B5701"],
    # Anticonvulsant SCARs — HLA-B*15:02 (rs3909184 proxy); CPIC Level A
    "carbamazepine": ["HLA_B1502"],
    "oxcarbazepine": ["HLA_B1502"],
    "phenytoin": ["HLA_B1502"],
    # UGT1A1
    "irinotecan": ["UGT1A1"],
    # CYP3A4/3A5 — transplant immunosuppressants
    "tacrolimus": ["CYP3A5", "CYP3A4"],
    "cyclosporine": ["CYP3A4", "CYP3A5"],
    "midazolam": ["CYP3A4", "CYP3A5"],
    "alprazolam": ["CYP3A4"],
    "fentanyl": ["CYP3A4"],
    # CYP1A2 — psychiatry and asthma
    "clozapine": ["CYP1A2"],
    "olanzapine": ["CYP1A2"],
    "theophylline": ["CYP1A2"],
    "caffeine": ["CYP1A2"],
    "fluvoxamine": ["CYP1A2"],
    "tizanidine": ["CYP1A2"],
    "duloxetine": ["CYP1A2"],
    # CYP2B6 — HIV antiretrovirals and antidepressants
    "efavirenz": ["CYP2B6"],
    "bupropion": ["CYP2B6"],
    "methadone": ["CYP2B6", "CYP2D6"],
    "cyclophosphamide": ["CYP2B6", "GSTM1", "GSTT1"],
    "nevirapine": ["CYP2B6"],
    # NAT2 — TB drugs and sulfonamides
    "isoniazid": ["NAT2"],
    "sulfamethoxazole": ["NAT2"],
    "hydralazine": ["NAT2"],
    "procainamide": ["NAT2"],
    "dapsone": ["NAT2"],
    # GSTM1/GSTT1 — cancer chemotherapy
    "busulfan": ["GSTM1", "GSTT1"],
    "oxaliplatin": ["GSTM1", "GSTT1"],
    "cisplatin": ["GSTM1", "GSTT1"],
    "carboplatin": ["GSTM1", "GSTT1"],
}
