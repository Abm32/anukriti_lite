"""
PDF report generation for pharmacogenomics results.

Uses reportlab to build a concise, human-readable report for judges /
clinicians from structured PGx output.
"""

import io
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def generate_pdf_bytes(data: Dict[str, Any]) -> bytes:
    """
    Build a simple PGx clinical report PDF and return raw bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph("Pharmacogenomics Report", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    elements.append(
        Paragraph(f"Drug: {data.get('drug_name', 'N/A')}", styles["Normal"])
    )
    elements.append(Paragraph(f"Gene: {data.get('gene')}", styles["Normal"]))
    elements.append(Paragraph(f"Genotype: {data.get('genotype')}", styles["Normal"]))
    elements.append(Paragraph(f"Phenotype: {data.get('phenotype')}", styles["Normal"]))
    elements.append(
        Paragraph(f"Risk level: {data.get('risk_level')}", styles["Normal"])
    )
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Clinical Recommendation", styles["Heading2"]))
    elements.append(
        Paragraph(data.get("clinical_recommendation", ""), styles["Normal"])
    )
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("AI Explanation", styles["Heading2"]))
    elements.append(Paragraph(data.get("explanation", ""), styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(
        Paragraph(
            "Sources: CPIC and related pharmacogenomics resources (where applicable).",
            styles["Italic"],
        )
    )

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
