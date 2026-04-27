#!/usr/bin/env python3
"""
Data Initialization Orchestrator

Coordinates the download and validation of required data files for SynthaTrial.
Handles VCF files from 1000 Genomes Project and ChEMBL database setup with
comprehensive progress tracking and error handling.

Version: 0.2 Beta
"""

import hashlib
import logging
import os
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve


@dataclass
class ValidationResult:
    """Result of file validation."""

    file_path: str
    is_valid: bool
    checksum_match: bool
    size_bytes: int
    errors: List[str]
    warnings: List[str]


@dataclass
class DataStatus:
    """Overall data completeness status."""

    vcf_files: Dict[str, bool]  # chromosome -> exists
    chembl_database: bool
    total_files: int
    valid_files: int
    missing_files: List[str]
    corrupted_files: List[str]


@dataclass
class DownloadProgress:
    """Download progress tracking."""

    url: str
    filename: str
    total_size: int
    downloaded_size: int
    start_time: float

    @property
    def progress_percent(self) -> float:
        """Calculate download progress percentage."""
        if self.total_size <= 0:
            return 0.0
        return min(100.0, (self.downloaded_size / self.total_size) * 100.0)

    @property
    def speed_mbps(self) -> float:
        """Calculate download speed in MB/s."""
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0.0
        return (self.downloaded_size / (1024 * 1024)) / elapsed

    @property
    def eta_seconds(self) -> float:
        """Estimate time remaining in seconds."""
        if self.progress_percent >= 100.0:
            return 0.0
        speed = self.speed_mbps
        if speed <= 0:
            return float("inf")
        remaining_mb = (self.total_size - self.downloaded_size) / (1024 * 1024)
        return remaining_mb / speed


class ProgressReporter:
    """Progress reporting utility for downloads."""

    def __init__(self, progress: DownloadProgress):
        self.progress = progress
        self.last_report_time = 0
        self.report_interval = 2.0  # Report every 2 seconds

    def __call__(self, block_num: int, block_size: int, total_size: int):
        """Progress callback for urlretrieve."""
        self.progress.total_size = total_size
        self.progress.downloaded_size = block_num * block_size

        current_time = time.time()
        if current_time - self.last_report_time >= self.report_interval:
            self._print_progress()
            self.last_report_time = current_time

    def _print_progress(self):
        """Print formatted progress information."""
        percent = self.progress.progress_percent
        speed = self.progress.speed_mbps
        eta = self.progress.eta_seconds

        # Format sizes
        downloaded_mb = self.progress.downloaded_size / (1024 * 1024)
        total_mb = self.progress.total_size / (1024 * 1024)

        # Format ETA
        if eta == float("inf"):
            eta_str = "∞"
        elif eta > 3600:
            eta_str = f"{eta/3600:.1f}h"
        elif eta > 60:
            eta_str = f"{eta/60:.1f}m"
        else:
            eta_str = f"{eta:.0f}s"

        # Progress bar
        bar_width = 30
        filled = int(bar_width * percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        print(
            f"\r  [{bar}] {percent:5.1f}% | "
            f"{downloaded_mb:6.1f}/{total_mb:6.1f} MB | "
            f"{speed:5.1f} MB/s | ETA: {eta_str:>6}",
            end="",
            flush=True,
        )


class DataInitializer:
    """Main data initialization orchestrator."""

    # VCF file URLs (1000 Genomes EBI release 20130502, v5b — v5a returns 404)
    # See root README for recommended chromosome set.
    EBI_VCF_BASE = "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502"
    VCF_URLS = {
        "chr22": f"{EBI_VCF_BASE}/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr10": f"{EBI_VCF_BASE}/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr2": f"{EBI_VCF_BASE}/ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr6": f"{EBI_VCF_BASE}/ALL.chr6.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr11": f"{EBI_VCF_BASE}/ALL.chr11.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr19": f"{EBI_VCF_BASE}/ALL.chr19.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
        "chr12": f"{EBI_VCF_BASE}/ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    }

    # ChEMBL database URL
    CHEMBL_URL = "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_34/chembl_34_sqlite.tar.gz"

    # Expected file sizes (approximate, for validation)
    EXPECTED_SIZES = {
        "chr22": (180 * 1024 * 1024, 250 * 1024 * 1024),  # ~196 MB
        "chr10": (650 * 1024 * 1024, 800 * 1024 * 1024),  # ~707 MB
        "chr2": (1100 * 1024 * 1024, 1300 * 1024 * 1024),  # ~1.2 GB
        "chr6": (850 * 1024 * 1024, 1000 * 1024 * 1024),  # ~915 MB
        "chr11": (650 * 1024 * 1024, 800 * 1024 * 1024),  # ~701 MB
        "chr19": (300 * 1024 * 1024, 400 * 1024 * 1024),  # ~329 MB
        "chr12": (620 * 1024 * 1024, 750 * 1024 * 1024),  # ~677 MB
        "chembl": (800 * 1024 * 1024, 2000 * 1024 * 1024),  # 800-2000 MB
    }

    # Enhanced retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    def __init__(self, base_dir: str = ".", verbose: bool = True):
        """Initialize the data initializer."""
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"
        self.genomes_dir = self.data_dir / "genomes"
        self.chembl_dir = self.data_dir / "chembl"
        self.verbose = verbose

        # Setup logging
        self.logger = self._setup_logging()

        # Create directories if they don't exist
        self.genomes_dir.mkdir(parents=True, exist_ok=True)
        self.chembl_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            self.logger.info(f"Data initializer ready - Base: {self.base_dir}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger("DataInitializer")
        logger.setLevel(logging.INFO if self.verbose else logging.WARNING)

        # Only add handler if not already present
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _check_disk_space(self, required_gb: float) -> bool:
        """
        Check if there's enough disk space for downloads.

        Args:
            required_gb: Required space in GB

        Returns:
            True if enough space available, False otherwise
        """
        try:
            import shutil

            free_bytes = shutil.disk_usage(self.data_dir).free
            free_gb = free_bytes / (1024**3)

            if free_gb < required_gb:
                print(
                    f"   ⚠️  Insufficient disk space: {free_gb:.1f} GB available, {required_gb:.1f} GB required"
                )
                self.logger.warning(
                    f"Insufficient disk space: {free_gb:.1f} GB available, {required_gb:.1f} GB required"
                )
                return False

            print(f"   ✓ Disk space check: {free_gb:.1f} GB available")
            return True

        except Exception as e:
            self.logger.warning(f"Could not check disk space: {e}")
            return True  # Assume OK if we can't check

    def _estimate_download_size(
        self, chromosomes: List[str], include_chembl: bool = False
    ) -> float:
        """
        Estimate total download size in GB.

        Args:
            chromosomes: List of chromosomes to download
            include_chembl: Whether to include ChEMBL database

        Returns:
            Estimated size in GB
        """
        total_bytes = 0

        # VCF files (use upper bound of expected sizes)
        for chromosome in chromosomes:
            if chromosome in self.EXPECTED_SIZES:
                _, max_size = self.EXPECTED_SIZES[chromosome]
                total_bytes += max_size

        # ChEMBL database
        if include_chembl:
            _, max_size = self.EXPECTED_SIZES["chembl"]
            total_bytes += max_size

        return total_bytes / (1024**3)  # Convert to GB

    def download_vcf_files(
        self, chromosomes: List[str], output_dir: str = None
    ) -> bool:
        """
        Download VCF files for specified chromosomes.

        Args:
            chromosomes: List of chromosome names (e.g., ['chr22', 'chr10'])
            output_dir: Output directory (defaults to data/genomes)

        Returns:
            True if all downloads successful, False otherwise
        """
        if output_dir is None:
            output_dir = str(self.genomes_dir)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print("VCF File Download")
        print(f"{'='*60}")
        print(f"Output directory: {output_path}")
        print(f"Chromosomes: {', '.join(chromosomes)}")

        # Check disk space
        estimated_size = self._estimate_download_size(chromosomes, include_chembl=False)
        if not self._check_disk_space(estimated_size + 1.0):  # Add 1GB buffer
            return False

        success_count = 0
        total_count = len(chromosomes)

        for i, chromosome in enumerate(chromosomes, 1):
            print(f"\n[{i}/{total_count}] Downloading {chromosome}...")

            if chromosome not in self.VCF_URLS:
                print(f"❌ Unknown chromosome: {chromosome}")
                print(f"   Available: {list(self.VCF_URLS.keys())}")
                self.logger.error(f"Unknown chromosome requested: {chromosome}")
                continue

            url = self.VCF_URLS[chromosome]
            filename = f"{chromosome}.vcf.gz"
            output_file = output_path / filename

            # Check if file already exists and is valid
            if output_file.exists():
                print(f"   File exists: {output_file}")
                validation = self.validate_file_integrity(str(output_file))
                if validation.is_valid:
                    print(f"   ✅ File is valid, skipping download")
                    success_count += 1
                    continue
                else:
                    print(f"   ⚠️  File is invalid, re-downloading...")
                    print(f"      Errors: {', '.join(validation.errors)}")
                    self.logger.warning(
                        f"Invalid file detected, re-downloading: {output_file}"
                    )

            # Download the file
            try:
                success = self._download_file_with_progress(url, str(output_file))
                if success:
                    print(f"\n   ✅ Download completed: {filename}")

                    # Validate downloaded file
                    validation = self.validate_file_integrity(str(output_file))
                    if validation.is_valid:
                        print(f"   ✅ File validation passed")
                        success_count += 1
                        self.logger.info(
                            f"Successfully downloaded and validated: {filename}"
                        )
                    else:
                        print(f"   ❌ File validation failed:")
                        for error in validation.errors:
                            print(f"      - {error}")
                        self.logger.error(
                            f"Downloaded file failed validation: {filename}"
                        )
                else:
                    print(f"\n   ❌ Download failed: {filename}")
                    self.logger.error(f"Download failed: {filename}")

            except Exception as e:
                print(f"\n   ❌ Download error: {e}")
                self.logger.error(f"Download error for {filename}: {e}")

        print(f"\n{'='*60}")
        print(f"VCF Download Summary: {success_count}/{total_count} successful")
        print(f"{'='*60}")

        return success_count == total_count

    def setup_chembl_database(self, output_dir: str = None) -> bool:
        """
        Download and extract ChEMBL database.

        Args:
            output_dir: Output directory (defaults to data/chembl)

        Returns:
            True if setup successful, False otherwise
        """
        if output_dir is None:
            output_dir = str(self.chembl_dir)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print("ChEMBL Database Setup")
        print(f"{'='*60}")
        print(f"Output directory: {output_path}")

        # Check if database already exists
        db_paths = [
            output_path / "chembl_34_sqlite" / "chembl_34.db",
            output_path / "chembl_34.db",
        ]

        for db_path in db_paths:
            if db_path.exists():
                print(f"✅ ChEMBL database already exists: {db_path}")
                return True

        # Check disk space
        estimated_size = self._estimate_download_size([], include_chembl=True)
        if not self._check_disk_space(estimated_size + 0.5):  # Add 0.5GB buffer
            return False

        # Download tar.gz file
        tar_filename = "chembl_34_sqlite.tar.gz"
        tar_path = output_path / tar_filename

        print(f"\nDownloading ChEMBL database...")
        print(f"URL: {self.CHEMBL_URL}")

        try:
            success = self._download_file_with_progress(self.CHEMBL_URL, str(tar_path))
            if not success:
                print(f"❌ Failed to download ChEMBL database")
                return False

            print(f"\n✅ Download completed: {tar_filename}")

            # Extract tar.gz file
            print(f"\nExtracting ChEMBL database...")
            with tarfile.open(tar_path, "r:gz") as tar:
                # Get list of members for progress tracking
                members = tar.getmembers()
                total_members = len(members)

                print(f"   Extracting {total_members} files...")

                for i, member in enumerate(members):
                    tar.extract(member, output_path)
                    if i % 10 == 0 or i == total_members - 1:
                        percent = (i + 1) / total_members * 100
                        print(
                            f"\r   Progress: {percent:5.1f}% ({i+1}/{total_members})",
                            end="",
                            flush=True,
                        )

                print()  # New line after progress

            print(f"✅ Extraction completed")

            # Verify database file exists
            for db_path in db_paths:
                if db_path.exists():
                    size_mb = db_path.stat().st_size / (1024 * 1024)
                    print(f"✅ Database verified: {db_path} ({size_mb:.1f} MB)")

                    # Clean up tar file
                    try:
                        tar_path.unlink()
                        print(f"🗑️  Cleaned up: {tar_filename}")
                    except Exception as e:
                        print(f"⚠️  Could not remove tar file: {e}")

                    return True

            print(f"❌ Database file not found after extraction")
            return False

        except Exception as e:
            print(f"❌ ChEMBL setup error: {e}")
            return False

    def validate_data_integrity(self) -> bool:
        """Validate overall data integrity (for integration tests)."""
        status = self.check_data_completeness()
        return status.valid_files == status.total_files and status.total_files > 0

    def validate_file_integrity(self, file_path: str) -> ValidationResult:
        """
        Validate file integrity using size checks and format validation.

        Args:
            file_path: Path to file to validate

        Returns:
            ValidationResult with validation details
        """
        path = Path(file_path)
        errors = []
        warnings = []

        # Check if file exists
        if not path.exists():
            errors.append("File does not exist")
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                checksum_match=False,
                size_bytes=0,
                errors=errors,
                warnings=warnings,
            )

        # Get file size
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        # Determine file type and validate
        if file_path.endswith(".vcf.gz"):
            # VCF file validation; detect chromosome (longest first: chr22 before chr2)
            chromosome = None
            chrom_order = tuple(
                sorted(
                    [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"],
                    key=lambda x: -len(x),
                )
            )
            for c in chrom_order:
                if c not in file_path:
                    continue
                idx = file_path.find(c)
                next_char = file_path[idx + len(c) : idx + len(c) + 1]
                if next_char and next_char.isdigit():
                    continue
                chromosome = c
                break

            if chromosome and chromosome in self.EXPECTED_SIZES:
                min_size, max_size = self.EXPECTED_SIZES[chromosome]
                if size_bytes < min_size:
                    errors.append(
                        f"File too small ({size_mb:.1f} MB < {min_size/(1024*1024):.1f} MB)"
                    )
                elif size_bytes > max_size:
                    warnings.append(
                        f"File larger than expected ({size_mb:.1f} MB > {max_size/(1024*1024):.1f} MB)"
                    )

            # Try to validate gzip format
            try:
                import gzip

                with gzip.open(path, "rb") as f:
                    f.read(1024)  # Try to read first 1KB
            except Exception as e:
                errors.append(f"Invalid gzip format: {e}")

        elif file_path.endswith(".db"):
            # SQLite database validation
            min_size, max_size = self.EXPECTED_SIZES.get("chembl", (0, float("inf")))
            if size_bytes < min_size:
                errors.append(
                    f"Database too small ({size_mb:.1f} MB < {min_size/(1024*1024):.1f} MB)"
                )
            elif size_bytes > max_size:
                warnings.append(
                    f"Database larger than expected ({size_mb:.1f} MB > {max_size/(1024*1024):.1f} MB)"
                )

            # Try to validate SQLite format
            try:
                import sqlite3

                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
                )
                cursor.fetchone()
                conn.close()
            except Exception as e:
                errors.append(f"Invalid SQLite database: {e}")

        is_valid = len(errors) == 0

        return ValidationResult(
            file_path=file_path,
            is_valid=is_valid,
            checksum_match=True,  # We don't have checksums, so assume OK if no errors
            size_bytes=size_bytes,
            errors=errors,
            warnings=warnings,
        )

    def check_data_completeness(self) -> DataStatus:
        """
        Check completeness of all required data files.

        Returns:
            DataStatus with overall completeness information
        """
        vcf_files = {}
        missing_files = []
        corrupted_files = []
        valid_files = 0
        total_files = 0

        # Check VCF files
        for chromosome in list(self.VCF_URLS.keys()):
            vcf_path = self.genomes_dir / f"{chromosome}.vcf.gz"
            total_files += 1

            if vcf_path.exists():
                validation = self.validate_file_integrity(str(vcf_path))
                if validation.is_valid:
                    vcf_files[chromosome] = True
                    valid_files += 1
                else:
                    vcf_files[chromosome] = False
                    corrupted_files.append(str(vcf_path))
            else:
                vcf_files[chromosome] = False
                missing_files.append(str(vcf_path))

        # Check ChEMBL database
        chembl_exists = False
        chembl_paths = [
            self.chembl_dir / "chembl_34_sqlite" / "chembl_34.db",
            self.chembl_dir / "chembl_34.db",
        ]

        total_files += 1
        for db_path in chembl_paths:
            if db_path.exists():
                validation = self.validate_file_integrity(str(db_path))
                if validation.is_valid:
                    chembl_exists = True
                    valid_files += 1
                    break
                else:
                    corrupted_files.append(str(db_path))

        if not chembl_exists:
            missing_files.extend([str(p) for p in chembl_paths if not p.exists()])

        return DataStatus(
            vcf_files=vcf_files,
            chembl_database=chembl_exists,
            total_files=total_files,
            valid_files=valid_files,
            missing_files=missing_files,
            corrupted_files=corrupted_files,
        )

    def _download_file_with_progress(self, url: str, output_path: str) -> bool:
        """
        Download file with progress tracking and retry logic.

        Args:
            url: URL to download from
            output_path: Local path to save file

        Returns:
            True if download successful, False otherwise
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                # Create progress tracker
                filename = Path(output_path).name
                progress = DownloadProgress(
                    url=url,
                    filename=filename,
                    total_size=0,
                    downloaded_size=0,
                    start_time=time.time(),
                )

                reporter = ProgressReporter(progress)

                if attempt > 0:
                    print(f"   Retry attempt {attempt + 1}/{self.MAX_RETRIES}")
                    self.logger.info(f"Retry attempt {attempt + 1} for {filename}")

                print(f"   URL: {url}")
                print(f"   Output: {output_path}")
                print(f"   Starting download...")

                # Check if partial file exists and remove it
                if Path(output_path).exists() and attempt > 0:
                    Path(output_path).unlink()
                    print(f"   Removed partial file from previous attempt")

                # Download with progress callback
                urlretrieve(url, output_path, reporthook=reporter)

                # Final progress report
                print()  # New line after progress bar

                # Verify the download completed successfully
                if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                    self.logger.info(f"Successfully downloaded {filename}")
                    return True
                else:
                    raise Exception("Downloaded file is empty or missing")

            except (URLError, HTTPError) as e:
                error_msg = f"Network error on attempt {attempt + 1}: {e}"
                print(f"\n   {error_msg}")
                self.logger.warning(error_msg)

                if attempt < self.MAX_RETRIES - 1:
                    print(f"   Waiting {self.RETRY_DELAY} seconds before retry...")
                    time.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(
                        f"Failed to download after {self.MAX_RETRIES} attempts"
                    )

            except Exception as e:
                error_msg = f"Download error on attempt {attempt + 1}: {e}"
                print(f"\n   {error_msg}")
                self.logger.warning(error_msg)

                if attempt < self.MAX_RETRIES - 1:
                    print(f"   Waiting {self.RETRY_DELAY} seconds before retry...")
                    time.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(
                        f"Failed to download after {self.MAX_RETRIES} attempts"
                    )

        return False

    def initialize_all_data(self, chromosomes: List[str] = None) -> bool:
        """
        Initialize all required data files.

        Args:
            chromosomes: List of chromosomes to download (defaults to ['chr22', 'chr10']; see root README)

        Returns:
            True if all initialization successful, False otherwise
        """
        if chromosomes is None:
            chromosomes = [
                "chr22",
                "chr10",
            ]  # minimum for SynthaTrial; add chr2,chr6,chr11,chr19 for representative set

        print(f"\n{'='*60}")
        print("SynthaTrial Data Initialization")
        print(f"{'='*60}")
        print("This will download and setup all required data files:")
        print("- VCF files from 1000 Genomes Project")
        print("- ChEMBL database for drug information")
        print()

        # Check current status
        status = self.check_data_completeness()
        print(f"Current status: {status.valid_files}/{status.total_files} files ready")

        if status.missing_files:
            print(f"Missing files: {len(status.missing_files)}")
            for file_path in status.missing_files[:3]:  # Show first 3
                print(f"  - {file_path}")
            if len(status.missing_files) > 3:
                print(f"  ... and {len(status.missing_files) - 3} more")

        if status.corrupted_files:
            print(f"Corrupted files: {len(status.corrupted_files)}")
            for file_path in status.corrupted_files:
                print(f"  - {file_path}")

        # Download VCF files
        vcf_success = self.download_vcf_files(chromosomes)

        # Setup ChEMBL database
        chembl_success = self.setup_chembl_database()

        # Final status check
        final_status = self.check_data_completeness()

        print(f"\n{'='*60}")
        print("Data Initialization Complete")
        print(f"{'='*60}")
        print(
            f"Final status: {final_status.valid_files}/{final_status.total_files} files ready"
        )

        if final_status.valid_files == final_status.total_files:
            print("✅ All data files are ready!")
            print("\nYou can now run SynthaTrial with:")
            print("  python main.py --vcf data/genomes/chr22.vcf.gz \\")
            print("                 --vcf-chr10 data/genomes/chr10.vcf.gz \\")
            print("                 --drug-name Warfarin")
            return True
        else:
            print("❌ Some data files are missing or corrupted")
            if final_status.missing_files:
                print("Missing files:")
                for file_path in final_status.missing_files:
                    print(f"  - {file_path}")
            if final_status.corrupted_files:
                print("Corrupted files:")
                for file_path in final_status.corrupted_files:
                    print(f"  - {file_path}")
            return False


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SynthaTrial Data Initialization Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize all data (VCF + ChEMBL)
  python scripts/data_initializer.py --all

  # Download only VCF files
  python scripts/data_initializer.py --vcf chr22 chr10

  # Setup only ChEMBL database
  python scripts/data_initializer.py --chembl

  # Check current data status
  python scripts/data_initializer.py --status

  # Validate specific file
  python scripts/data_initializer.py --validate data/genomes/chr22.vcf.gz
        """,
    )

    parser.add_argument(
        "--all", action="store_true", help="Initialize all data files (VCF + ChEMBL)"
    )
    parser.add_argument(
        "--vcf",
        nargs="*",
        metavar="CHROMOSOME",
        help="Download VCF files for specified chromosomes",
    )
    parser.add_argument("--chembl", action="store_true", help="Setup ChEMBL database")
    parser.add_argument(
        "--status", action="store_true", help="Check current data status"
    )
    parser.add_argument(
        "--validate", metavar="FILE_PATH", help="Validate specific file integrity"
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose logging (default: True)",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable verbose logging")

    args = parser.parse_args()

    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet

    # Initialize data initializer
    base_dir = args.output_dir or "."
    initializer = DataInitializer(base_dir, verbose=verbose)

    # Handle different commands
    if args.status:
        status = initializer.check_data_completeness()
        print(f"\n{'='*60}")
        print("SynthaTrial Data Status")
        print(f"{'='*60}")
        print(f"Overall: {status.valid_files}/{status.total_files} files ready")
        print()
        print("VCF Files:")
        for chromosome, exists in status.vcf_files.items():
            status_icon = "✅" if exists else "❌"
            print(f"  {status_icon} {chromosome}.vcf.gz")
        print()
        print(f"ChEMBL Database: {'✅' if status.chembl_database else '❌'}")

        if status.missing_files:
            print(f"\nMissing files ({len(status.missing_files)}):")
            for file_path in status.missing_files:
                print(f"  - {file_path}")

        if status.corrupted_files:
            print(f"\nCorrupted files ({len(status.corrupted_files)}):")
            for file_path in status.corrupted_files:
                print(f"  - {file_path}")

        return 0 if status.valid_files == status.total_files else 1

    elif args.validate:
        validation = initializer.validate_file_integrity(args.validate)
        print(f"\n{'='*60}")
        print(f"File Validation: {args.validate}")
        print(f"{'='*60}")
        print(f"Status: {'✅ Valid' if validation.is_valid else '❌ Invalid'}")
        print(f"Size: {validation.size_bytes / (1024*1024):.1f} MB")

        if validation.errors:
            print("\nErrors:")
            for error in validation.errors:
                print(f"  - {error}")

        if validation.warnings:
            print("\nWarnings:")
            for warning in validation.warnings:
                print(f"  - {warning}")

        return 0 if validation.is_valid else 1

    elif args.all:
        success = initializer.initialize_all_data()
        return 0 if success else 1

    elif args.vcf is not None:
        chromosomes = args.vcf if args.vcf else ["chr22", "chr10"]
        success = initializer.download_vcf_files(chromosomes)
        return 0 if success else 1

    elif args.chembl:
        success = initializer.setup_chembl_database()
        return 0 if success else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
