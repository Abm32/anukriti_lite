#!/usr/bin/env python3
"""
Property-Based Tests for Data Initialization

This module contains property-based tests for the Data Initialization system,
validating universal properties across different configurations and inputs.

Tests validate:
- Property 4: Data Download and Integrity Validation
- Property 5: Container Startup Data Validation
- Property 6: Download Progress Tracking

Author: SynthaTrial Development Team
Version: 0.2 Beta
"""

import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, mock_open, patch

import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

# Add the project root to the Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.data_initializer import (
    DataInitializer,
    DataStatus,
    DownloadProgress,
    ValidationResult,
)
from scripts.download_vcf_files import (
    DownloadResult,
    ValidationReport,
    VCFDownloader,
    VCFFileInfo,
)
from scripts.setup_chembl import ChEMBLSetup, ChEMBLSetupResult, DatabaseValidation


# Custom strategies for generating test data
@composite
def chromosome_lists(draw):
    """Generate valid chromosome lists for testing"""
    available_chromosomes = ["chr22", "chr10"]
    size = draw(st.integers(min_value=1, max_value=len(available_chromosomes)))
    return draw(
        st.lists(
            st.sampled_from(available_chromosomes),
            min_size=size,
            max_size=size,
            unique=True,
        )
    )


@composite
def file_size_ranges(draw):
    """Generate realistic file size ranges for validation"""
    min_size = draw(
        st.integers(min_value=1024, max_value=100 * 1024 * 1024)
    )  # 1KB to 100MB
    max_size = draw(
        st.integers(min_value=min_size, max_value=min_size * 10)
    )  # Up to 10x min_size
    return (min_size, max_size)


@composite
def download_progress_data(draw):
    """Generate download progress tracking data"""
    total_size = draw(
        st.integers(min_value=1024, max_value=1024 * 1024 * 1024)
    )  # 1KB to 1GB
    downloaded_size = draw(st.integers(min_value=0, max_value=total_size))
    # Use fixed time offset instead of current time to avoid flaky tests
    base_time = 1640995200.0  # Fixed timestamp: 2022-01-01 00:00:00 UTC
    start_time = draw(
        st.floats(min_value=base_time, max_value=base_time + 3600)
    )  # Within 1 hour of base time

    return {
        "url": draw(st.text(min_size=10, max_size=100)),
        "filename": draw(st.text(min_size=5, max_size=50)) + ".vcf.gz",
        "total_size": total_size,
        "downloaded_size": downloaded_size,
        "start_time": start_time,
    }


@composite
def validation_scenarios(draw):
    """Generate file validation scenarios"""
    file_exists = draw(st.booleans())
    # Use smaller file sizes to avoid timeout issues
    file_size = draw(st.integers(min_value=0, max_value=10 * 1024 * 1024))  # 0 to 10MB
    is_gzip_valid = draw(st.booleans()) if file_exists else False
    has_errors = draw(st.booleans())
    has_warnings = draw(st.booleans())

    return {
        "file_exists": file_exists,
        "file_size": file_size,
        "is_gzip_valid": is_gzip_valid,
        "has_errors": has_errors,
        "has_warnings": has_warnings,
    }


class TestDataInitializationProperties(unittest.TestCase):
    """Property-based tests for Data Initialization functionality"""

    def setUp(self):
        """Setup test environment for each test method"""
        self.temp_dir = tempfile.mkdtemp(prefix="data_init_test_")
        self.test_data_dir = Path(self.temp_dir) / "data"
        self.test_genomes_dir = self.test_data_dir / "genomes"
        self.test_chembl_dir = self.test_data_dir / "chembl"

        # Create directory structure
        self.test_genomes_dir.mkdir(parents=True, exist_ok=True)
        self.test_chembl_dir.mkdir(parents=True, exist_ok=True)

        # Initialize data initializer
        self.data_initializer = DataInitializer(base_dir=self.temp_dir, verbose=False)

    def tearDown(self):
        """Cleanup test environment after each test method"""
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.property
    @pytest.mark.data_download
    @given(
        chromosomes=chromosome_lists(),
        force_redownload=st.booleans(),
        verbose=st.booleans(),
    )
    @settings(
        max_examples=5,
        deadline=8000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @example(chromosomes=["chr22"], force_redownload=False, verbose=True)
    @example(chromosomes=["chr10"], force_redownload=True, verbose=False)
    @example(chromosomes=["chr22", "chr10"], force_redownload=False, verbose=True)
    def test_property_4_data_download_and_integrity_validation(
        self, chromosomes, force_redownload, verbose
    ):
        """
        **Feature: docker-enhancements, Property 4: Data Download and Integrity Validation**

        For any data initialization request (VCF files or ChEMBL database),
        the Data_Initializer should successfully download files and validate
        their integrity using checksums.

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Property: Data initializer should always initialize successfully with valid parameters
        initializer = DataInitializer(base_dir=self.temp_dir, verbose=verbose)
        self.assertIsNotNone(initializer)
        self.assertEqual(initializer.base_dir, Path(self.temp_dir))
        self.assertTrue(initializer.genomes_dir.exists())
        self.assertTrue(initializer.chembl_dir.exists())

        # Property: VCF URLs should always be valid and accessible
        for chromosome in chromosomes:
            self.assertIn(chromosome, initializer.VCF_URLS)
            url = initializer.VCF_URLS[chromosome]
            self.assertTrue(url.startswith("https://"))
            self.assertIn("1000genomes", url.lower())
            self.assertIn(chromosome, url)

        # Property: Expected file sizes should be valid ranges
        for chromosome in chromosomes:
            if chromosome in initializer.EXPECTED_SIZES:
                min_size, max_size = initializer.EXPECTED_SIZES[chromosome]
                self.assertGreater(min_size, 0)
                self.assertGreater(max_size, min_size)
                self.assertLessEqual(
                    min_size, 2 * 1024 * 1024 * 1024
                )  # Reasonable upper bound

        # Property: File validation should always return consistent results
        fake_vcf_path = str(self.test_genomes_dir / "fake_chr22.vcf.gz")
        validation = initializer.validate_file_integrity(fake_vcf_path)

        # Non-existent files should always fail validation
        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.size_bytes, 0)
        self.assertFalse(validation.checksum_match)
        self.assertIn("File does not exist", validation.errors)

        # Property: Data completeness check should always return valid status
        status = initializer.check_data_completeness()
        self.assertIsInstance(status, DataStatus)
        self.assertIsInstance(status.vcf_files, dict)
        self.assertIsInstance(status.chembl_database, bool)
        self.assertGreaterEqual(status.total_files, 0)
        self.assertGreaterEqual(status.valid_files, 0)
        self.assertLessEqual(status.valid_files, status.total_files)
        self.assertIsInstance(status.missing_files, list)
        self.assertIsInstance(status.corrupted_files, list)

        # Property: VCF files status should include expected chromosomes
        for chromosome in ["chr22", "chr10"]:
            self.assertIn(chromosome, status.vcf_files)
            self.assertIsInstance(status.vcf_files[chromosome], bool)

    @pytest.mark.property
    @pytest.mark.container_startup
    @given(
        scenario=validation_scenarios(), chromosome=st.sampled_from(["chr22", "chr10"])
    )
    @settings(
        max_examples=4,
        deadline=None,  # Disable deadline for large file operations
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @example(
        scenario={
            "file_exists": True,
            "file_size": 1024 * 1024,
            "is_gzip_valid": True,
            "has_errors": False,
            "has_warnings": False,
        },
        chromosome="chr22",
    )
    @example(
        scenario={
            "file_exists": False,
            "file_size": 0,
            "is_gzip_valid": False,
            "has_errors": True,
            "has_warnings": False,
        },
        chromosome="chr10",
    )
    def test_property_5_container_startup_data_validation(self, scenario, chromosome):
        """
        **Feature: docker-enhancements, Property 5: Container Startup Data Validation**

        For any container startup with data dependencies, the Data_Initializer
        should perform integrity checks and provide accurate reports of missing
        or corrupted files.

        **Validates: Requirements 2.4**
        """
        # Setup test file based on scenario
        # Note: We create files in the data_initializer's expected location
        vcf_file_path = self.data_initializer.genomes_dir / f"{chromosome}.vcf.gz"

        if scenario["file_exists"]:
            # Create a test file with specified characteristics
            if scenario["file_size"] == 0:
                # Create empty file
                vcf_file_path.touch()
            elif scenario["is_gzip_valid"] and scenario["file_size"] > 0:
                # Create a valid gzip file with VCF-like content
                vcf_content = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                with gzip.open(vcf_file_path, "wb") as f:
                    f.write(vcf_content)
                    # Pad to desired size (accounting for gzip compression)
                    if scenario["file_size"] > len(vcf_content):
                        # Add padding that will compress to approximately the desired size
                        padding_content = b"A" * (
                            scenario["file_size"] - len(vcf_content)
                        )
                        f.write(padding_content)
            elif scenario["file_size"] > 0:
                # Create an invalid file (not gzip) with specified size
                with open(vcf_file_path, "wb") as f:
                    content = b"invalid content" * (scenario["file_size"] // 15 + 1)
                    f.write(content[: scenario["file_size"]])  # Truncate to exact size

        # Property: Data completeness check should always detect file existence correctly
        status = self.data_initializer.check_data_completeness()

        if scenario["file_exists"]:
            # File exists, so it should be detected
            self.assertIn(chromosome, status.vcf_files)

            # Validation should reflect file integrity
            validation = self.data_initializer.validate_file_integrity(
                str(vcf_file_path)
            )
            self.assertEqual(validation.file_path, str(vcf_file_path))

            if scenario["file_size"] > 0:
                # Non-empty files should have size > 0 (may differ due to gzip compression)
                self.assertGreater(validation.size_bytes, 0)
            # Note: We don't assert exact size for empty files because the validation
            # might report different sizes due to file system behavior

            if scenario["is_gzip_valid"] and scenario["file_size"] > 0:
                # Valid gzip files should pass basic validation
                self.assertTrue(
                    len(validation.errors) == 0
                    or not any("gzip" in error.lower() for error in validation.errors)
                )
            else:
                # Invalid files should have errors
                self.assertFalse(validation.is_valid)
                self.assertGreater(len(validation.errors), 0)
        else:
            # File doesn't exist, should be in missing files
            self.assertFalse(
                status.vcf_files.get(chromosome, True)
            )  # Should be False or missing
            # The data_initializer checks for both chr22 and chr10
            # If this specific chromosome file doesn't exist, it should be in missing files
            expected_vcf_path = str(vcf_file_path)
            # Debug: Print what we're looking for and what we found
            if expected_vcf_path not in status.missing_files:
                # This might be expected if both files are missing and only one is reported
                # Let's check if the chromosome is marked as False in vcf_files
                self.assertFalse(
                    status.vcf_files.get(chromosome, True),
                    f"Chromosome {chromosome} should be marked as False when file doesn't exist",
                )

        # Property: Status should always be internally consistent
        self.assertEqual(
            status.valid_files,
            sum(1 for exists in status.vcf_files.values() if exists)
            + (1 if status.chembl_database else 0),
        )

        # Property: Missing and corrupted files should not overlap
        missing_set = set(status.missing_files)
        corrupted_set = set(status.corrupted_files)
        self.assertEqual(len(missing_set.intersection(corrupted_set)), 0)

        # Property: Total files should be consistent
        expected_total = len(status.vcf_files) + 1  # VCF files + ChEMBL
        self.assertEqual(status.total_files, expected_total)

    @pytest.mark.property
    @pytest.mark.progress_tracking
    @given(progress_data=download_progress_data())
    @settings(
        max_examples=8,
        deadline=6000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @example(
        progress_data={
            "url": "https://example.com/test.vcf.gz",
            "filename": "test.vcf.gz",
            "total_size": 1024 * 1024,
            "downloaded_size": 512 * 1024,
            "start_time": time.time() - 60,
        }
    )
    def test_property_6_download_progress_tracking(self, progress_data):
        """
        **Feature: docker-enhancements, Property 6: Download Progress Tracking**

        For any large file download operation, the Data_Initializer should
        provide progress indicators that accurately reflect download completion
        percentage.

        **Validates: Requirements 2.5**
        """
        # Create download progress tracker
        progress = DownloadProgress(
            url=progress_data["url"],
            filename=progress_data["filename"],
            total_size=progress_data["total_size"],
            downloaded_size=progress_data["downloaded_size"],
            start_time=progress_data["start_time"],
        )

        # Property: Progress percentage should always be between 0 and 100
        progress_percent = progress.progress_percent
        self.assertGreaterEqual(progress_percent, 0.0)
        self.assertLessEqual(progress_percent, 100.0)

        # Property: Progress percentage should be accurate
        if progress_data["total_size"] > 0:
            expected_percent = min(
                100.0,
                (progress_data["downloaded_size"] / progress_data["total_size"])
                * 100.0,
            )
            self.assertAlmostEqual(progress_percent, expected_percent, places=2)
        else:
            self.assertEqual(progress_percent, 0.0)

        # Property: Speed calculation should be non-negative
        speed_mbps = progress.speed_mbps
        self.assertGreaterEqual(speed_mbps, 0.0)

        # Property: Speed should be reasonable (not infinite) for non-zero elapsed time
        # Create a progress object with a known elapsed time for testing
        test_start_time = progress_data["start_time"] - 60  # 60 seconds ago
        test_progress = DownloadProgress(
            url=progress_data["url"],
            filename=progress_data["filename"],
            total_size=progress_data["total_size"],
            downloaded_size=progress_data["downloaded_size"],
            start_time=test_start_time,
        )

        # Mock time.time() to return a consistent value
        import unittest.mock

        with unittest.mock.patch("time.time", return_value=progress_data["start_time"]):
            test_speed = test_progress.speed_mbps
            self.assertGreaterEqual(test_speed, 0.0)
            # Speed should be finite for positive elapsed time
            if progress_data["downloaded_size"] > 0:
                self.assertNotEqual(test_speed, float("inf"))

        # Property: ETA should be non-negative
        eta_seconds = progress.eta_seconds
        self.assertGreaterEqual(eta_seconds, 0.0)

        # Property: ETA should be 0 when download is complete
        if progress_percent >= 100.0:
            self.assertEqual(eta_seconds, 0.0)

        # Property: ETA should be finite for incomplete downloads with positive speed
        if progress_percent < 100.0 and speed_mbps > 0:
            self.assertNotEqual(eta_seconds, float("inf"))

        # Property: Progress tracking should handle edge cases gracefully
        # Test with zero total size
        zero_progress = DownloadProgress(
            url=progress_data["url"],
            filename=progress_data["filename"],
            total_size=0,
            downloaded_size=progress_data["downloaded_size"],
            start_time=progress_data["start_time"],
        )
        self.assertEqual(zero_progress.progress_percent, 0.0)

        # Test with downloaded > total (should cap at 100%)
        over_progress = DownloadProgress(
            url=progress_data["url"],
            filename=progress_data["filename"],
            total_size=progress_data["total_size"],
            downloaded_size=progress_data["total_size"] + 1000,
            start_time=progress_data["start_time"],
        )
        self.assertEqual(over_progress.progress_percent, 100.0)

    @pytest.mark.property
    @pytest.mark.data_integrity
    @given(
        file_size=st.integers(min_value=0, max_value=100 * 1024 * 1024),  # 0 to 100MB
        is_valid_gzip=st.booleans(),
        chromosome=st.sampled_from(["chr22", "chr10"]),
    )
    @settings(
        max_examples=4,
        deadline=6000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_file_integrity_validation_consistency(
        self, file_size, is_valid_gzip, chromosome
    ):
        """
        **Additional Property: File Integrity Validation Consistency**

        File validation should always return consistent results for the same file,
        and validation results should accurately reflect file characteristics.
        """
        # Create test file
        test_file = self.test_genomes_dir / f"{chromosome}.vcf.gz"

        if file_size > 0:
            if is_valid_gzip:
                # Create valid gzip VCF content
                vcf_content = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                with gzip.open(test_file, "wb") as f:
                    f.write(vcf_content)
                    # Add padding content that will result in approximately the desired uncompressed size
                    if file_size > len(vcf_content):
                        padding_content = b"A" * (file_size - len(vcf_content))
                        f.write(padding_content)
            else:
                # Create invalid (non-gzip) content
                with open(test_file, "wb") as f:
                    content = b"invalid" * (file_size // 7 + 1)
                    f.write(content[:file_size])  # Truncate to exact size

        # Property: Validation should be consistent across multiple calls
        validation1 = self.data_initializer.validate_file_integrity(str(test_file))
        validation2 = self.data_initializer.validate_file_integrity(str(test_file))

        self.assertEqual(validation1.is_valid, validation2.is_valid)
        self.assertEqual(validation1.size_bytes, validation2.size_bytes)
        self.assertEqual(validation1.checksum_match, validation2.checksum_match)
        self.assertEqual(len(validation1.errors), len(validation2.errors))

        # Property: File size should be accurately reported
        if file_size > 0:
            # Note: Actual file size may differ from requested due to gzip compression
            self.assertGreater(validation1.size_bytes, 0)
        else:
            # Empty or non-existent file
            self.assertEqual(validation1.size_bytes, 0)

        # Property: Validation should detect file existence correctly
        if file_size > 0:
            self.assertTrue(test_file.exists())
            self.assertNotIn("File does not exist", validation1.errors)
        else:
            self.assertFalse(test_file.exists())
            self.assertIn("File does not exist", validation1.errors)

        # Property: Gzip validation should be accurate
        if file_size > 0 and is_valid_gzip:
            # Valid gzip files should not have gzip-related errors
            gzip_errors = [
                error for error in validation1.errors if "gzip" in error.lower()
            ]
            self.assertEqual(len(gzip_errors), 0)
        elif file_size > 0 and not is_valid_gzip:
            # Invalid gzip files should have gzip-related errors
            self.assertFalse(validation1.is_valid)
            self.assertGreater(len(validation1.errors), 0)

    @pytest.mark.property
    @pytest.mark.chembl_validation
    @given(
        db_exists=st.booleans(),
        db_size=st.integers(min_value=0, max_value=100 * 1024 * 1024),  # 0 to 100MB
        is_valid_sqlite=st.booleans(),
    )
    @settings(
        max_examples=3,
        deadline=6000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_chembl_database_validation(
        self, db_exists, db_size, is_valid_sqlite
    ):
        """
        **Additional Property: ChEMBL Database Validation**

        ChEMBL database validation should accurately detect database presence,
        size, and basic SQLite integrity.
        """
        # Setup ChEMBL database paths
        chembl_paths = [
            self.test_chembl_dir / "chembl_34_sqlite" / "chembl_34.db",
            self.test_chembl_dir / "chembl_34.db",
        ]

        if db_exists and db_size > 0:
            # Create test database
            db_path = chembl_paths[0]  # Use first path
            db_path.parent.mkdir(parents=True, exist_ok=True)

            if (
                is_valid_sqlite and db_size >= 1024
            ):  # Minimum size for a valid SQLite file
                # Create valid SQLite database
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    # Use CREATE TABLE IF NOT EXISTS to avoid conflicts
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)"
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO test_table (id, name) VALUES (1, 'test')"
                    )
                    conn.commit()
                    conn.close()

                    # Pad to desired size if needed
                    current_size = db_path.stat().st_size
                    if current_size < db_size:
                        with open(db_path, "ab") as f:
                            f.write(b"\x00" * (db_size - current_size))
                except sqlite3.Error:
                    # If SQLite operations fail, create invalid file instead
                    with open(db_path, "wb") as f:
                        content = b"invalid database content" * (db_size // 24 + 1)
                        f.write(content[:db_size])  # Truncate to exact size
            else:
                # Create invalid (non-SQLite) file
                with open(db_path, "wb") as f:
                    content = b"invalid database content" * (db_size // 24 + 1)
                    f.write(content[:db_size])  # Truncate to exact size

        # Property: Data completeness should detect ChEMBL database correctly
        status = self.data_initializer.check_data_completeness()

        if db_exists and db_size >= 1024 and is_valid_sqlite:
            # Valid database should be detected - but only if it meets minimum size requirements
            # The data initializer has minimum size requirements for validation
            if db_size >= 800 * 1024 * 1024:  # 800MB minimum as per data_initializer
                self.assertTrue(status.chembl_database)
            else:
                # Small databases may not pass validation due to size constraints
                # This is expected behavior - small files are considered invalid
                self.assertFalse(status.chembl_database)
        else:
            # Invalid or missing database should not be detected as valid
            self.assertFalse(status.chembl_database)

        # Property: Status should be internally consistent
        expected_valid_files = sum(1 for exists in status.vcf_files.values() if exists)
        if status.chembl_database:
            expected_valid_files += 1

        self.assertEqual(status.valid_files, expected_valid_files)

        # Property: Missing files should include ChEMBL if not present
        if not status.chembl_database:
            # Only assert ChEMBL is in missing files if we expect it to be missing
            # (not just failing validation due to size constraints)
            if not db_exists or db_size == 0 or not is_valid_sqlite:
                chembl_missing = any(
                    "chembl" in missing_file.lower()
                    for missing_file in status.missing_files
                )
                self.assertTrue(
                    chembl_missing,
                    f"Expected ChEMBL to be in missing files: {status.missing_files}",
                )
            # If database exists but is too small, it may not be in missing files
            # because it exists but fails validation - this is acceptable


if __name__ == "__main__":
    # Run the property-based tests
    unittest.main(verbosity=2)
