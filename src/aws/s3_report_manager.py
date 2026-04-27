"""
S3 Report Manager (disabled)

PDF pharmacogenomics reports are generated in-process and downloaded by the user from
Streamlit/API — no S3 upload is required for core flows.

Optional cloud storage of PDFs in S3 (presigned URLs, lifecycle) was removed to avoid
bucket cost and complexity. Re-enable by restoring the previous implementation from git
history if needed.

The S3ReportManager class remains as no-op stubs so any future import does not break.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class S3ReportManager:
    """No-op: S3 report storage is not used (PDFs are local/download-only)."""

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = None
        self.s3_resource = None
        self.bucket = None
        logger.debug(
            "S3ReportManager: S3 PDF storage disabled (bucket=%s not used)",
            bucket_name,
        )

    def _test_connection(self):
        return False

    def create_bucket_if_not_exists(self) -> bool:
        return False

    def configure_lifecycle(self) -> None:
        pass

    def store_report(
        self,
        patient_id: str,
        report_pdf: bytes,
        drug: str = "unknown",
        analysis_type: str = "pharmacogenomics",
    ) -> Optional[str]:
        """S3 upload disabled — returns None (use in-app PDF download)."""
        return None

    def get_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        return None

    def list_patient_reports(self, patient_id: str) -> List[Dict[str, Any]]:
        return []

    def search_reports(
        self,
        drug: Optional[str] = None,
        analysis_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        return []

    def delete_report(self, key: str) -> bool:
        return False

    def delete_patient_reports(self, patient_id: str) -> int:
        return 0

    def get_storage_statistics(self) -> Dict[str, Any]:
        return {
            "disabled": True,
            "note": "S3 report storage not used; PDFs are download-only from the app.",
        }


def main():
    """CLI smoke: reports bucket is not used."""
    bucket_name = os.getenv("AWS_S3_BUCKET_REPORTS", "synthatrial-reports")
    region = os.getenv("AWS_S3_REGION", "us-east-1")
    manager = S3ReportManager(bucket_name, region)
    print("S3 report storage is disabled. PDFs are generated for direct download only.")
    print(f"Would-have bucket (ignored): {manager.bucket_name} region={region}")
    print(manager.get_storage_statistics())


if __name__ == "__main__":
    main()
