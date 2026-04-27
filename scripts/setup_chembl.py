#!/usr/bin/env python3
"""
ChEMBL Database Setup Automation

Automated download, extraction, and validation of ChEMBL SQLite database
for SynthaTrial. Provides comprehensive error handling, progress tracking,
and integrity validation.

Version: 0.2 Beta
"""

import hashlib
import logging
import os
import sqlite3
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, urlretrieve


@dataclass
class ChEMBLSetupResult:
    """Result of ChEMBL database setup."""

    success: bool
    database_path: Optional[str]
    size_mb: float
    setup_time_seconds: float
    errors: list
    warnings: list


@dataclass
class DatabaseValidation:
    """Database validation result."""

    is_valid: bool
    table_count: int
    compound_count: int
    activity_count: int
    size_mb: float
    errors: list
    warnings: list


class ProgressTracker:
    """Progress tracking for downloads and extractions."""

    def __init__(self, operation: str, total_size: int = 0):
        self.operation = operation
        self.total_size = total_size
        self.current_size = 0
        self.start_time = time.time()
        self.last_report_time = 0
        self.report_interval = 2.0  # Report every 2 seconds

    def update(self, current_size: int):
        """Update progress and optionally print status."""
        self.current_size = current_size

        current_time = time.time()
        if current_time - self.last_report_time >= self.report_interval:
            self._print_progress()
            self.last_report_time = current_time

    def _print_progress(self):
        """Print formatted progress information."""
        elapsed = time.time() - self.start_time

        if self.total_size > 0:
            percent = min(100.0, (self.current_size / self.total_size) * 100.0)
            speed_mbps = (
                (self.current_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            )

            # Estimate time remaining
            if percent > 0 and percent < 100:
                eta_seconds = (elapsed / percent) * (100 - percent)
                if eta_seconds > 3600:
                    eta_str = f"{eta_seconds/3600:.1f}h"
                elif eta_seconds > 60:
                    eta_str = f"{eta_seconds/60:.1f}m"
                else:
                    eta_str = f"{eta_seconds:.0f}s"
            else:
                eta_str = "0s"

            # Progress bar
            bar_width = 30
            filled = int(bar_width * percent / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            current_mb = self.current_size / (1024 * 1024)
            total_mb = self.total_size / (1024 * 1024)

            print(
                f"\r  {self.operation}: [{bar}] {percent:5.1f}% | "
                f"{current_mb:6.1f}/{total_mb:6.1f} MB | "
                f"{speed_mbps:5.1f} MB/s | ETA: {eta_str:>6}",
                end="",
                flush=True,
            )
        else:
            # No total size available, just show current progress
            current_mb = self.current_size / (1024 * 1024)
            speed_mbps = (
                (self.current_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            )

            print(
                f"\r  {self.operation}: {current_mb:6.1f} MB | "
                f"{speed_mbps:5.1f} MB/s | {elapsed:.0f}s",
                end="",
                flush=True,
            )

    def finish(self):
        """Print final progress status."""
        print()  # New line after progress bar


class ChEMBLSetup:
    """ChEMBL database setup automation."""

    # ChEMBL database configuration
    CHEMBL_VERSION = "34"
    CHEMBL_URL = f"https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{CHEMBL_VERSION}/chembl_{CHEMBL_VERSION}_sqlite.tar.gz"

    # Expected database characteristics for validation
    MIN_DATABASE_SIZE_MB = 800  # Minimum expected size in MB
    MAX_DATABASE_SIZE_MB = 3000  # Maximum expected size in MB
    MIN_TABLE_COUNT = 50  # Minimum expected number of tables
    MIN_COMPOUND_COUNT = 1000000  # Minimum expected compounds
    MIN_ACTIVITY_COUNT = 10000000  # Minimum expected activities

    # Download configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    CHUNK_SIZE = 8192  # bytes for reading

    def __init__(self, output_dir: str = "data/chembl", verbose: bool = True):
        """
        Initialize ChEMBL setup.

        Args:
            output_dir: Directory to store ChEMBL database
            verbose: Enable verbose logging
        """
        self.output_dir = Path(output_dir)
        self.verbose = verbose

        # Setup logging
        self.logger = self._setup_logging()

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Define expected paths
        self.tar_path = self.output_dir / f"chembl_{self.CHEMBL_VERSION}_sqlite.tar.gz"
        self.extracted_dir = self.output_dir / f"chembl_{self.CHEMBL_VERSION}_sqlite"
        self.database_path = self.extracted_dir / f"chembl_{self.CHEMBL_VERSION}.db"

        if self.verbose:
            self.logger.info(f"ChEMBL setup initialized - Output: {self.output_dir}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger("ChEMBLSetup")
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
        Check if there's enough disk space for download and extraction.

        Args:
            required_gb: Required space in GB

        Returns:
            True if enough space available, False otherwise
        """
        try:
            import shutil

            free_bytes = shutil.disk_usage(self.output_dir).free
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

    def _download_with_progress(self, url: str, output_path: Path) -> bool:
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
                if attempt > 0:
                    print(f"   Retry attempt {attempt + 1}/{self.MAX_RETRIES}")
                    self.logger.info(f"Retry attempt {attempt + 1} for ChEMBL download")

                print(f"   URL: {url}")
                print(f"   Output: {output_path}")

                # Get file size for progress tracking
                try:
                    with urlopen(url) as response:
                        total_size = int(response.headers.get("Content-Length", 0))
                except Exception:
                    total_size = 0

                # Remove partial file from previous attempt
                if output_path.exists() and attempt > 0:
                    output_path.unlink()
                    print(f"   Removed partial file from previous attempt")

                # Setup progress tracker
                tracker = ProgressTracker("Downloading", total_size)

                def progress_callback(block_num: int, block_size: int, total_size: int):
                    tracker.total_size = total_size
                    tracker.update(block_num * block_size)

                print(f"   Starting download...")

                # Download with progress callback
                urlretrieve(url, str(output_path), reporthook=progress_callback)
                tracker.finish()

                # Verify download
                if output_path.exists() and output_path.stat().st_size > 0:
                    size_mb = output_path.stat().st_size / (1024 * 1024)
                    print(f"   ✅ Download completed: {size_mb:.1f} MB")
                    self.logger.info(
                        f"Successfully downloaded ChEMBL database: {size_mb:.1f} MB"
                    )
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

    def _extract_database(self, tar_path: Path) -> bool:
        """
        Extract ChEMBL database from tar.gz file.

        Args:
            tar_path: Path to tar.gz file

        Returns:
            True if extraction successful, False otherwise
        """
        try:
            print(f"   Extracting ChEMBL database...")
            print(f"   Archive: {tar_path}")
            print(f"   Destination: {self.output_dir}")

            with tarfile.open(tar_path, "r:gz") as tar:
                # Get list of members for progress tracking
                members = tar.getmembers()
                total_members = len(members)

                print(f"   Extracting {total_members} files...")

                # Setup progress tracker
                tracker = ProgressTracker("Extracting", total_members)

                for i, member in enumerate(members):
                    tar.extract(member, self.output_dir)
                    tracker.update(i + 1)

                    # Update progress every 10 files or at the end
                    if i % 10 == 0 or i == total_members - 1:
                        tracker._print_progress()

                tracker.finish()

            print(f"   ✅ Extraction completed")
            self.logger.info("Successfully extracted ChEMBL database")
            return True

        except Exception as e:
            print(f"   ❌ Extraction failed: {e}")
            self.logger.error(f"Failed to extract ChEMBL database: {e}")
            return False

    def _validate_database(self, db_path: Path) -> DatabaseValidation:
        """
        Validate ChEMBL database integrity and content.

        Args:
            db_path: Path to SQLite database file

        Returns:
            DatabaseValidation result
        """
        errors = []
        warnings = []
        table_count = 0
        compound_count = 0
        activity_count = 0

        try:
            # Check file exists and size
            if not db_path.exists():
                errors.append("Database file does not exist")
                return DatabaseValidation(
                    is_valid=False,
                    table_count=0,
                    compound_count=0,
                    activity_count=0,
                    size_mb=0,
                    errors=errors,
                    warnings=warnings,
                )

            size_mb = db_path.stat().st_size / (1024 * 1024)

            # Check file size
            if size_mb < self.MIN_DATABASE_SIZE_MB:
                errors.append(
                    f"Database too small: {size_mb:.1f} MB < {self.MIN_DATABASE_SIZE_MB} MB"
                )
            elif size_mb > self.MAX_DATABASE_SIZE_MB:
                warnings.append(
                    f"Database larger than expected: {size_mb:.1f} MB > {self.MAX_DATABASE_SIZE_MB} MB"
                )

            # Connect to database and validate structure
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()

                # Count tables
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]

                if table_count < self.MIN_TABLE_COUNT:
                    errors.append(
                        f"Too few tables: {table_count} < {self.MIN_TABLE_COUNT}"
                    )

                # Check key tables exist and count records
                key_tables = {
                    "molecule_dictionary": "compound_count",
                    "activities": "activity_count",
                    "compound_structures": "structure_count",
                }

                for table_name, count_type in key_tables.items():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]

                        if table_name == "molecule_dictionary":
                            compound_count = count
                            if count < self.MIN_COMPOUND_COUNT:
                                errors.append(
                                    f"Too few compounds: {count:,} < {self.MIN_COMPOUND_COUNT:,}"
                                )

                        elif table_name == "activities":
                            activity_count = count
                            if count < self.MIN_ACTIVITY_COUNT:
                                errors.append(
                                    f"Too few activities: {count:,} < {self.MIN_ACTIVITY_COUNT:,}"
                                )

                    except sqlite3.Error as e:
                        errors.append(f"Cannot access table {table_name}: {e}")

                # Test a simple query to ensure database is functional
                try:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM molecule_dictionary m
                        JOIN compound_structures cs ON m.molregno = cs.molregno
                        WHERE cs.canonical_smiles IS NOT NULL
                        LIMIT 1
                    """
                    )
                    cursor.fetchone()
                except sqlite3.Error as e:
                    errors.append(f"Database query test failed: {e}")

                conn.close()

            except sqlite3.Error as e:
                errors.append(f"Cannot connect to database: {e}")

        except Exception as e:
            errors.append(f"Validation error: {e}")

        is_valid = len(errors) == 0

        return DatabaseValidation(
            is_valid=is_valid,
            table_count=table_count,
            compound_count=compound_count,
            activity_count=activity_count,
            size_mb=size_mb,
            errors=errors,
            warnings=warnings,
        )

    def check_existing_database(self) -> Optional[Path]:
        """
        Check if ChEMBL database already exists and is valid.

        Returns:
            Path to valid database or None if not found/invalid
        """
        # Check multiple possible locations
        possible_paths = [
            self.database_path,  # Standard extracted location
            self.output_dir
            / f"chembl_{self.CHEMBL_VERSION}.db",  # Direct in output dir
            self.output_dir / "chembl.db",  # Generic name
        ]

        for db_path in possible_paths:
            if db_path.exists():
                print(f"   Found existing database: {db_path}")
                validation = self._validate_database(db_path)

                if validation.is_valid:
                    print(f"   ✅ Database is valid ({validation.size_mb:.1f} MB)")
                    print(f"      Tables: {validation.table_count:,}")
                    print(f"      Compounds: {validation.compound_count:,}")
                    print(f"      Activities: {validation.activity_count:,}")
                    return db_path
                else:
                    print(f"   ❌ Database is invalid:")
                    for error in validation.errors:
                        print(f"      - {error}")
                    if validation.warnings:
                        print(f"   Warnings:")
                        for warning in validation.warnings:
                            print(f"      - {warning}")

        return None

    def setup_database(self, force_download: bool = False) -> ChEMBLSetupResult:
        """
        Setup ChEMBL database with download, extraction, and validation.

        Args:
            force_download: Force re-download even if database exists

        Returns:
            ChEMBLSetupResult with setup details
        """
        start_time = time.time()
        errors = []
        warnings = []

        print(f"\n{'='*60}")
        print("ChEMBL Database Setup")
        print(f"{'='*60}")
        print(f"Version: ChEMBL {self.CHEMBL_VERSION}")
        print(f"Output directory: {self.output_dir}")

        try:
            # Check if database already exists (unless forced)
            if not force_download:
                existing_db = self.check_existing_database()
                if existing_db:
                    setup_time = time.time() - start_time
                    return ChEMBLSetupResult(
                        success=True,
                        database_path=str(existing_db),
                        size_mb=existing_db.stat().st_size / (1024 * 1024),
                        setup_time_seconds=setup_time,
                        errors=[],
                        warnings=["Using existing database"],
                    )

            # Check disk space (estimate 3GB needed for download + extraction)
            if not self._check_disk_space(3.0):
                errors.append("Insufficient disk space")
                return ChEMBLSetupResult(
                    success=False,
                    database_path=None,
                    size_mb=0,
                    setup_time_seconds=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                )

            # Download tar.gz file
            print(f"\n[1/3] Downloading ChEMBL database...")
            download_success = self._download_with_progress(
                self.CHEMBL_URL, self.tar_path
            )

            if not download_success:
                errors.append("Failed to download ChEMBL database")
                return ChEMBLSetupResult(
                    success=False,
                    database_path=None,
                    size_mb=0,
                    setup_time_seconds=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                )

            # Extract database
            print(f"\n[2/3] Extracting database...")
            extract_success = self._extract_database(self.tar_path)

            if not extract_success:
                errors.append("Failed to extract ChEMBL database")
                return ChEMBLSetupResult(
                    success=False,
                    database_path=None,
                    size_mb=0,
                    setup_time_seconds=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                )

            # Validate database
            print(f"\n[3/3] Validating database...")
            validation = self._validate_database(self.database_path)

            if not validation.is_valid:
                errors.extend(validation.errors)
                return ChEMBLSetupResult(
                    success=False,
                    database_path=(
                        str(self.database_path) if self.database_path.exists() else None
                    ),
                    size_mb=validation.size_mb,
                    setup_time_seconds=time.time() - start_time,
                    errors=errors,
                    warnings=warnings + validation.warnings,
                )

            # Clean up tar file
            try:
                self.tar_path.unlink()
                print(f"   🗑️  Cleaned up: {self.tar_path.name}")
            except Exception as e:
                warnings.append(f"Could not remove tar file: {e}")

            # Success!
            setup_time = time.time() - start_time

            print(f"\n✅ ChEMBL database setup completed successfully!")
            print(f"   Database: {self.database_path}")
            print(f"   Size: {validation.size_mb:.1f} MB")
            print(f"   Tables: {validation.table_count:,}")
            print(f"   Compounds: {validation.compound_count:,}")
            print(f"   Activities: {validation.activity_count:,}")
            print(f"   Setup time: {setup_time:.1f} seconds")

            return ChEMBLSetupResult(
                success=True,
                database_path=str(self.database_path),
                size_mb=validation.size_mb,
                setup_time_seconds=setup_time,
                errors=[],
                warnings=warnings + validation.warnings,
            )

        except Exception as e:
            errors.append(f"Unexpected error: {e}")
            self.logger.error(f"ChEMBL setup failed: {e}")

            return ChEMBLSetupResult(
                success=False,
                database_path=None,
                size_mb=0,
                setup_time_seconds=time.time() - start_time,
                errors=errors,
                warnings=warnings,
            )

    def verify_setup(self) -> bool:
        """
        Verify that ChEMBL database is properly set up and accessible.

        Returns:
            True if database is ready for use, False otherwise
        """
        print(f"\n{'='*60}")
        print("ChEMBL Database Verification")
        print(f"{'='*60}")

        existing_db = self.check_existing_database()
        if existing_db:
            print(f"✅ ChEMBL database is ready for use!")
            print(f"   Path: {existing_db}")

            # Test basic functionality
            try:
                conn = sqlite3.connect(str(existing_db))
                cursor = conn.cursor()

                # Test query for drug extraction
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM molecule_dictionary m
                    JOIN compound_structures cs ON m.molregno = cs.molregno
                    WHERE m.max_phase >= 2
                    AND cs.canonical_smiles IS NOT NULL
                    AND cs.canonical_smiles != ''
                """
                )

                drug_count = cursor.fetchone()[0]
                print(f"   Available drugs (phase 2+): {drug_count:,}")

                conn.close()
                return True

            except Exception as e:
                print(f"❌ Database functionality test failed: {e}")
                return False
        else:
            print(f"❌ No valid ChEMBL database found")
            print(f"   Run setup to download and install the database")
            return False


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ChEMBL Database Setup Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup ChEMBL database (default location)
  python scripts/setup_chembl.py

  # Setup with custom output directory
  python scripts/setup_chembl.py --output-dir /path/to/data/chembl

  # Force re-download even if database exists
  python scripts/setup_chembl.py --force

  # Just verify existing setup
  python scripts/setup_chembl.py --verify-only

  # Quiet mode (minimal output)
  python scripts/setup_chembl.py --quiet
        """,
    )

    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default="data/chembl",
        help="Output directory for ChEMBL database (default: data/chembl)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-download even if database exists"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing setup, do not download",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Minimal output (errors only)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output (default: True)",
    )

    args = parser.parse_args()

    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet

    # Initialize ChEMBL setup
    chembl_setup = ChEMBLSetup(output_dir=args.output_dir, verbose=verbose)

    try:
        if args.verify_only:
            # Just verify existing setup
            success = chembl_setup.verify_setup()
            return 0 if success else 1
        else:
            # Setup database
            result = chembl_setup.setup_database(force_download=args.force)

            if result.success:
                print(f"\n{'='*60}")
                print("Setup Summary")
                print(f"{'='*60}")
                print(f"✅ ChEMBL database ready: {result.database_path}")
                print(f"   Size: {result.size_mb:.1f} MB")
                print(f"   Setup time: {result.setup_time_seconds:.1f} seconds")

                if result.warnings:
                    print(f"\nWarnings:")
                    for warning in result.warnings:
                        print(f"  - {warning}")

                # Verify functionality
                if chembl_setup.verify_setup():
                    print(f"\n🎉 ChEMBL database is ready for SynthaTrial!")
                    return 0
                else:
                    print(f"\n❌ Database setup completed but verification failed")
                    return 1
            else:
                print(f"\n{'='*60}")
                print("Setup Failed")
                print(f"{'='*60}")
                print(f"❌ ChEMBL database setup failed")

                if result.errors:
                    print(f"\nErrors:")
                    for error in result.errors:
                        print(f"  - {error}")

                if result.warnings:
                    print(f"\nWarnings:")
                    for warning in result.warnings:
                        print(f"  - {warning}")

                return 1

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Setup interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
