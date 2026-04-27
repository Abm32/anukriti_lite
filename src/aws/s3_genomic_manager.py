"""
S3 Genomic Data Manager

This module provides S3 integration for genomic data storage and retrieval,
optimized for VCF files and large-scale genomic datasets.

Features:
- VCF file upload with metadata
- Presigned URL generation for secure access
- Intelligent Tiering for cost optimization
- Integrity validation and error handling
"""

import hashlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, NoCredentialsError
except Exception:  # pragma: no cover
    boto3 = None
    Config = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment]
    NoCredentialsError = Exception  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class S3GenomicDataManager:
    """S3 integration for genomic data storage and retrieval"""

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region

        try:
            if boto3 is None or Config is None:
                raise NoCredentialsError()
            connect_timeout = int(os.getenv("AWS_CONNECT_TIMEOUT", "2"))
            read_timeout = int(os.getenv("AWS_READ_TIMEOUT", "3"))
            cfg = Config(
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries={"max_attempts": 1, "mode": "standard"},
            )

            self.s3_client = boto3.client("s3", region_name=region, config=cfg)
            self.s3_resource = boto3.resource("s3", region_name=region, config=cfg)
            self.bucket = self.s3_resource.Bucket(bucket_name)

            # Avoid blocking initialization; enable via env var when needed.
            if os.getenv("AWS_S3_TEST_ON_INIT", "false").lower() == "true":
                self._test_connection()

        except NoCredentialsError:
            logger.warning("AWS credentials not found. S3 operations will fail.")
            self.s3_client = None
            self.s3_resource = None
            self.bucket = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
            self.s3_resource = None
            self.bucket = None

    def _test_connection(self):
        """Test S3 connection and bucket access"""
        if not self.s3_client:
            return False

        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                logger.warning(f"Bucket {self.bucket_name} does not exist")
            elif error_code == "403":
                logger.warning(f"Access denied to bucket {self.bucket_name}")
            else:
                logger.warning(f"Error accessing bucket: {e}")
            return False

    def create_bucket_if_not_exists(self) -> bool:
        """Create bucket if it doesn't exist (development mode only)"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False

        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} already exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                try:
                    if self.region == "us-east-1":
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.region
                            },
                        )

                    # Configure Intelligent Tiering
                    self._configure_intelligent_tiering()

                    logger.info(f"Created bucket {self.bucket_name}")
                    return True
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False

    def _configure_intelligent_tiering(self):
        """Configure Intelligent Tiering for cost optimization"""
        if not self.s3_client:
            return

        try:
            self.s3_client.put_bucket_intelligent_tiering_configuration(
                Bucket=self.bucket_name,
                Id="GenomicDataTiering",
                IntelligentTieringConfiguration={
                    "Id": "GenomicDataTiering",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "genomes/"},
                    "Tierings": [
                        {"Days": 1, "AccessTier": "ARCHIVE_ACCESS"},
                        {"Days": 90, "AccessTier": "DEEP_ARCHIVE_ACCESS"},
                    ],
                },
            )
            logger.info("Configured Intelligent Tiering for genomic data")
        except ClientError as e:
            logger.warning(f"Failed to configure Intelligent Tiering: {e}")

    def upload_vcf(
        self, chromosome: str, local_path: str, version: str = "phase3"
    ) -> Optional[str]:
        """Upload VCF file to S3 with appropriate metadata"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None

        if not os.path.exists(local_path):
            logger.error(f"Local file not found: {local_path}")
            return None

        key = f"genomes/chr{chromosome}.vcf.gz"

        try:
            # Calculate file hash for integrity
            file_hash = self._calculate_file_hash(local_path)
            file_size = os.path.getsize(local_path)

            # Upload with metadata
            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                key,
                ExtraArgs={
                    "StorageClass": "INTELLIGENT_TIERING",
                    "Metadata": {
                        "chromosome": chromosome,
                        "version": version,
                        "file_hash": file_hash,
                        "file_size": str(file_size),
                        "upload_date": datetime.now().isoformat(),
                        "content_type": "application/gzip",
                    },
                    "ContentType": "application/gzip",
                },
            )

            logger.info(f"Uploaded VCF file: {key} ({file_size} bytes)")
            return key

        except ClientError as e:
            logger.error(f"Failed to upload VCF file: {e}")
            return None

    def download_vcf(
        self, chromosome: str, local_path: str, version: str = "phase3"
    ) -> bool:
        """Download VCF file from S3"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False

        key = f"genomes/chr{chromosome}.vcf.gz"

        try:
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download file
            self.s3_client.download_file(self.bucket_name, key, local_path)

            # Verify integrity if metadata available
            if self._verify_file_integrity(key, local_path):
                logger.info(f"Downloaded and verified VCF file: {local_path}")
                return True
            else:
                logger.warning(
                    f"Downloaded VCF file but integrity check failed: {local_path}"
                )
                return True  # Still return True as file was downloaded

        except ClientError as e:
            logger.error(f"Failed to download VCF file: {e}")
            return False

    def get_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for secure temporary access"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            logger.info(f"Generated presigned URL for {key} (expires in {expiration}s)")
            return str(url) if url else None
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    def list_vcf_files(self) -> List[Dict[str, Any]]:
        """List all VCF files in the bucket"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return []

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix="genomes/"
            )

            files = []
            for obj in response.get("Contents", []):
                # Get metadata
                metadata_response = self.s3_client.head_object(
                    Bucket=self.bucket_name, Key=obj["Key"]
                )

                file_info = {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "storage_class": obj.get("StorageClass", "STANDARD"),
                    "metadata": metadata_response.get("Metadata", {}),
                }
                files.append(file_info)

            logger.info(f"Found {len(files)} VCF files")
            return files

        except ClientError as e:
            logger.error(f"Failed to list VCF files: {e}")
            return []

    def delete_vcf(self, chromosome: str) -> bool:
        """Delete VCF file from S3"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False

        key = f"genomes/chr{chromosome}.vcf.gz"

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted VCF file: {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete VCF file: {e}")
            return False

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file for integrity checking"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _verify_file_integrity(self, key: str, local_path: str) -> bool:
        """Verify file integrity using stored hash"""
        if not self.s3_client:
            return False

        try:
            # Get stored metadata
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            stored_hash = response.get("Metadata", {}).get("file_hash")

            if not stored_hash:
                logger.warning(f"No hash metadata found for {key}")
                return False

            # Calculate local file hash
            local_hash = self._calculate_file_hash(local_path)

            if stored_hash == local_hash:
                logger.info(f"File integrity verified for {key}")
                return True
            else:
                logger.error(f"File integrity check failed for {key}")
                return False

        except Exception as e:
            logger.error(f"Error verifying file integrity: {e}")
            return False

    def get_bucket_info(self) -> Dict[str, Any]:
        """Get bucket information and statistics"""
        if not self.s3_client:
            return {"error": "S3 client not initialized"}

        try:
            # Get bucket location
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)

            # Get bucket size and object count
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)

            total_size = 0
            object_count = 0

            for obj in response.get("Contents", []):
                total_size += obj["Size"]
                object_count += 1

            return {
                "bucket_name": self.bucket_name,
                "region": location.get("LocationConstraint", "us-east-1"),
                "object_count": object_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "intelligent_tiering": True,
            }

        except ClientError as e:
            logger.error(f"Failed to get bucket info: {e}")
            return {"error": str(e)}


def main():
    """Main function for CLI usage"""

    # Example usage
    bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
    region = os.getenv("AWS_S3_REGION", "us-east-1")

    manager = S3GenomicDataManager(bucket_name, region)

    if manager.s3_client:
        print("S3 Genomic Data Manager initialized successfully")

        # Get bucket info
        info = manager.get_bucket_info()
        print(f"Bucket info: {info}")

        # List VCF files
        files = manager.list_vcf_files()
        print(f"Found {len(files)} VCF files")

        for file_info in files:
            print(f"  - {file_info['key']} ({file_info['size']} bytes)")
    else:
        print("S3 client not initialized. Check AWS credentials and configuration.")


if __name__ == "__main__":
    main()
