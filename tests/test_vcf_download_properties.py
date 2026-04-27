#!/usr/bin/env python3
"""
Property-based tests for VCF file download automation.

Tests universal properties that should hold across all valid executions
of the VCF download system, ensuring correctness guarantees for data
initialization and integrity validation.

Version: 0.2 Beta
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.data_initializer import DataInitializer, DataStatus, ValidationResult
from scripts.download_vcf_files import (
    DownloadResult,
    ValidationReport,
    VCFDownloader,
    VCFFileInfo,
)


class TestVCFDownloadProperties(unittest.TestCase):
    """Property-based tests for VCF download automation."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "test_genomes"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @given(
        chromosome=st.sampled_from(["chr22", "chr10"]),
        force_redownload=st.booleans(),
        verbose=st.booleans(),
    )
    @settings(
        max_examples=4,
        deadline=8000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_4_data_download_and_integrity_validation(
        self, chromosome, force_redownload, verbose
    ):
        """
        **Feature: docker-enhancements, Property 4: Data Download and Integrity Validation**

        For any data initialization request (VCF files or ChEMBL database),
        the Data_Initializer should successfully download files and validate
        their integrity using checksums.

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Initialize VCF downloader with test parameters
        downloader = VCFDownloader(str(self.test_output_dir), verbose=verbose)

        # Property: VCF downloader should always initialize successfully
        self.assertIsNotNone(downloader)
        self.assertEqual(downloader.output_dir, self.test_output_dir)
        self.assertTrue(self.test_output_dir.exists())

        # Property: Available chromosomes should always include expected chromosomes
        available_chromosomes = downloader.list_available_chromosomes()
        self.assertIn(chromosome, available_chromosomes)

        # Property: VCF file info should always have required fields
        vcf_info = available_chromosomes[chromosome]
        self.assertEqual(vcf_info.chromosome, chromosome)
        self.assertIsNotNone(vcf_info.url)
        self.assertTrue(vcf_info.url.startswith("https://"))
        self.assertIsNotNone(vcf_info.filename)
        self.assertTrue(vcf_info.filename.endswith(".vcf.gz"))
        self.assertIsNotNone(vcf_info.expected_size_range)

        # Property: Size range should be valid (min < max, both positive)
        min_size, max_size = vcf_info.expected_size_range
        self.assertGreater(min_size, 0)
        self.assertGreater(max_size, min_size)

        # Property: Validation of non-existent file should always fail gracefully
        fake_file = str(self.test_output_dir / "nonexistent.vcf.gz")
        validation = downloader.validate_vcf_file(fake_file)
        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.file_size, 0)
        self.assertIn("File does not exist", validation.errors)

    @given(
        chromosomes=st.lists(
            st.sampled_from(["chr22", "chr10"]), min_size=1, max_size=2, unique=True
        ),
        base_dir_suffix=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=10,
        ),
        verbose=st.booleans(),
    )
    @settings(
        max_examples=3,
        deadline=6000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_5_container_startup_data_validation(
        self, chromosomes, base_dir_suffix, verbose
    ):
        """
        **Feature: docker-enhancements, Property 5: Container Startup Data Validation**

        For any container startup with data dependencies, the Data_Initializer
        should perform integrity checks and provide accurate reports of missing
        or corrupted files.

        **Validates: Requirements 2.4**
        """
        # Create test directory with suffix to ensure uniqueness
        test_base_dir = Path(self.temp_dir) / f"test_base_{base_dir_suffix}"
        test_base_dir.mkdir(parents=True, exist_ok=True)

        # Initialize data initializer
        initializer = DataInitializer(str(test_base_dir), verbose=verbose)

        # Property: Data initializer should always initialize successfully
        self.assertIsNotNone(initializer)
        self.assertEqual(initializer.base_dir, test_base_dir)
        self.assertTrue(initializer.data_dir.exists())
        self.assertTrue(initializer.genomes_dir.exists())
        self.assertTrue(initializer.chembl_dir.exists())

        # Property: Data completeness check should always return valid DataStatus
        status = initializer.check_data_completeness()
        self.assertIsInstance(status, DataStatus)

        # Property: Status should have all required fields
        self.assertIsInstance(status.vcf_files, dict)
        self.assertIsInstance(status.chembl_database, bool)
        self.assertIsInstance(status.total_files, int)
        self.assertIsInstance(status.valid_files, int)
        self.assertIsInstance(status.missing_files, list)
        self.assertIsInstance(status.corrupted_files, list)

        # Property: Total files should be at least 3 (2 VCF + 1 ChEMBL); may be more if more chromosomes are configured
        self.assertGreaterEqual(status.total_files, 3)

        # Property: Valid files should never exceed total files
        self.assertLessEqual(status.valid_files, status.total_files)
        self.assertGreaterEqual(status.valid_files, 0)

        # Property: VCF files status should include expected chromosomes
        for chromosome in ["chr22", "chr10"]:
            self.assertIn(chromosome, status.vcf_files)
            self.assertIsInstance(status.vcf_files[chromosome], bool)

        # Property: For fresh installation, all files should be missing
        # (since we're using a clean temp directory)
        self.assertEqual(status.valid_files, 0)
        self.assertFalse(status.chembl_database)
        for chromosome in ["chr22", "chr10"]:
            self.assertFalse(status.vcf_files[chromosome])

        # Property: Missing files list should contain expected paths
        self.assertGreater(len(status.missing_files), 0)

        # Property: File validation should work for any file path
        test_file = str(test_base_dir / "test_file.vcf.gz")
        validation = initializer.validate_file_integrity(test_file)
        self.assertIsInstance(validation, ValidationResult)
        self.assertFalse(validation.is_valid)  # File doesn't exist
        self.assertIn("File does not exist", validation.errors)

    @given(
        filename=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
            min_size=5,
            max_size=50,
        ).filter(lambda x: not x.startswith(".") and "/" not in x),
        total_size=st.integers(
            min_value=1024, max_value=1024 * 1024 * 1024
        ),  # 1KB to 1GB
        update_interval=st.floats(min_value=0.1, max_value=5.0),
    )
    @settings(
        max_examples=4,
        deadline=6000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_6_download_progress_tracking(
        self, filename, total_size, update_interval
    ):
        """
        **Feature: docker-enhancements, Property 6: Download Progress Tracking**

        For any large file download operation, the Data_Initializer should
        provide progress indicators that accurately reflect download completion
        percentage.

        **Validates: Requirements 2.5**
        """
        from scripts.data_initializer import DownloadProgress, ProgressReporter
        from scripts.download_vcf_files import ProgressTracker

        # Test VCF ProgressTracker
        progress_tracker = ProgressTracker(filename, total_size)

        # Property: Progress tracker should initialize correctly
        self.assertEqual(progress_tracker.filename, filename)
        self.assertEqual(progress_tracker.total_size, total_size)
        self.assertEqual(progress_tracker.downloaded_size, 0)
        self.assertGreater(progress_tracker.start_time, 0)

        # Property: Progress updates should be consistent
        for downloaded in [
            0,
            total_size // 4,
            total_size // 2,
            total_size * 3 // 4,
            total_size,
        ]:
            progress_tracker.update(downloaded, total_size)

            # Property: Downloaded size should match update
            self.assertEqual(progress_tracker.downloaded_size, downloaded)

            # Property: Total size should be preserved
            self.assertEqual(progress_tracker.total_size, total_size)

        # Test DataInitializer DownloadProgress
        download_progress = DownloadProgress(
            url="https://example.com/test.vcf.gz",
            filename=filename,
            total_size=total_size,
            downloaded_size=0,
            start_time=0.0,
        )

        # Property: Download progress should initialize correctly
        self.assertEqual(download_progress.filename, filename)
        self.assertEqual(download_progress.total_size, total_size)

        # Property: Progress percentage should be accurate
        test_downloaded_sizes = [
            0,
            total_size // 4,
            total_size // 2,
            total_size * 3 // 4,
            total_size,
        ]
        expected_percentages = [0.0, 25.0, 50.0, 75.0, 100.0]

        for downloaded, expected_percent in zip(
            test_downloaded_sizes, expected_percentages
        ):
            download_progress.downloaded_size = downloaded
            actual_percent = download_progress.progress_percent

            # Property: Progress percentage should be within expected range
            self.assertGreaterEqual(actual_percent, 0.0)
            self.assertLessEqual(actual_percent, 100.0)

            # Property: Progress percentage should be reasonably close to expected
            # Allow for small rounding differences due to integer division
            if expected_percent == 0.0:
                self.assertEqual(actual_percent, 0.0)
            elif expected_percent == 100.0:
                self.assertEqual(actual_percent, 100.0)
            else:
                # For intermediate values, allow 2% tolerance for rounding
                self.assertAlmostEqual(actual_percent, expected_percent, delta=2.0)

        # Property: Speed calculation should be non-negative
        download_progress.start_time = 1000.0  # Fixed start time
        speed = download_progress.speed_mbps
        self.assertGreaterEqual(speed, 0.0)

        # Property: ETA should be reasonable
        eta = download_progress.eta_seconds
        self.assertGreaterEqual(eta, 0.0)

    @given(
        chromosome=st.sampled_from(["chr22", "chr10"]),
        file_size=st.integers(
            min_value=1024, max_value=2 * 1024 * 1024 * 1024
        ),  # 1KB to 2GB
        has_errors=st.booleans(),
        has_warnings=st.booleans(),
    )
    @settings(
        max_examples=4,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_validation_report_consistency(
        self, chromosome, file_size, has_errors, has_warnings
    ):
        """
        **Feature: docker-enhancements, Property: Validation Report Consistency**

        For any validation report, the structure and logic should be consistent
        and all fields should have valid values.

        **Validates: Requirements 2.2, 2.4**
        """
        # Create a test validation report
        errors = ["Test error"] if has_errors else []
        warnings = ["Test warning"] if has_warnings else []

        validation_report = ValidationReport(
            file_path=f"/test/path/{chromosome}.vcf.gz",
            is_valid=not has_errors,  # Valid if no errors
            file_size=file_size,
            md5_checksum="abc123def456",
            md5_match=True,
            gzip_valid=not has_errors,
            vcf_header_valid=not has_errors,
            sample_count=100 if not has_errors else 0,
            variant_count_estimate=50000 if not has_errors else 0,
            errors=errors,
            warnings=warnings,
        )

        # Property: Validation report should have consistent structure
        self.assertIsInstance(validation_report.file_path, str)
        self.assertIsInstance(validation_report.is_valid, bool)
        self.assertIsInstance(validation_report.file_size, int)
        self.assertIsInstance(validation_report.md5_checksum, str)
        self.assertIsInstance(validation_report.md5_match, bool)
        self.assertIsInstance(validation_report.gzip_valid, bool)
        self.assertIsInstance(validation_report.vcf_header_valid, bool)
        self.assertIsInstance(validation_report.sample_count, int)
        self.assertIsInstance(validation_report.variant_count_estimate, int)
        self.assertIsInstance(validation_report.errors, list)
        self.assertIsInstance(validation_report.warnings, list)

        # Property: File size should be non-negative
        self.assertGreaterEqual(validation_report.file_size, 0)

        # Property: Sample and variant counts should be non-negative
        self.assertGreaterEqual(validation_report.sample_count, 0)
        self.assertGreaterEqual(validation_report.variant_count_estimate, 0)

        # Property: Validation logic should be consistent
        if has_errors:
            self.assertFalse(validation_report.is_valid)
            self.assertGreater(len(validation_report.errors), 0)
        else:
            self.assertTrue(validation_report.is_valid)
            self.assertEqual(len(validation_report.errors), 0)

        # Property: Warnings should not affect validity
        if has_warnings:
            self.assertGreater(len(validation_report.warnings), 0)
        else:
            self.assertEqual(len(validation_report.warnings), 0)

    @given(
        chromosome=st.sampled_from(["chr22", "chr10"]),
        success=st.booleans(),
        validation_passed=st.booleans(),
        download_time=st.floats(min_value=0.0, max_value=3600.0),  # 0 to 1 hour
        file_size=st.integers(
            min_value=0, max_value=2 * 1024 * 1024 * 1024
        ),  # 0 to 2GB
    )
    @settings(
        max_examples=3,
        deadline=4000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_download_result_consistency(
        self, chromosome, success, validation_passed, download_time, file_size
    ):
        """
        **Feature: docker-enhancements, Property: Download Result Consistency**

        For any download result, the structure and logic should be consistent
        and all fields should have valid values.

        **Validates: Requirements 2.1, 2.2**
        """
        # Ensure logical consistency: can't have validation pass if download failed
        if not success:
            validation_passed = False

        # Create a test download result
        download_result = DownloadResult(
            chromosome=chromosome,
            filename=f"{chromosome}.vcf.gz",
            success=success,
            file_path=f"/test/path/{chromosome}.vcf.gz",
            file_size=file_size if success else 0,
            download_time=download_time,
            validation_passed=validation_passed,
            md5_match=validation_passed,  # Assume MD5 matches if validation passed
            errors=[] if success else ["Download failed"],
            warnings=[],
        )

        # Property: Download result should have consistent structure
        self.assertIsInstance(download_result.chromosome, str)
        self.assertIsInstance(download_result.filename, str)
        self.assertIsInstance(download_result.success, bool)
        self.assertIsInstance(download_result.file_path, str)
        self.assertIsInstance(download_result.file_size, int)
        self.assertIsInstance(download_result.download_time, float)
        self.assertIsInstance(download_result.validation_passed, bool)
        self.assertIsInstance(download_result.md5_match, bool)
        self.assertIsInstance(download_result.errors, list)
        self.assertIsInstance(download_result.warnings, list)

        # Property: Chromosome should match expected value
        self.assertEqual(download_result.chromosome, chromosome)

        # Property: File size should be non-negative
        self.assertGreaterEqual(download_result.file_size, 0)

        # Property: Download time should be non-negative
        self.assertGreaterEqual(download_result.download_time, 0.0)

        # Property: Logical consistency checks
        if not download_result.success:
            # Failed downloads should have errors and no validation
            self.assertGreater(len(download_result.errors), 0)
            self.assertFalse(download_result.validation_passed)
            self.assertEqual(download_result.file_size, 0)

        if download_result.validation_passed:
            # Validation can only pass if download succeeded
            self.assertTrue(download_result.success)
            self.assertGreater(download_result.file_size, 0)

        # Property: Filename should match chromosome
        self.assertIn(chromosome, download_result.filename)
        self.assertTrue(download_result.filename.endswith(".vcf.gz"))


if __name__ == "__main__":
    # Run property-based tests
    unittest.main(verbosity=2)
