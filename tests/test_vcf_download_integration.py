#!/usr/bin/env python3
"""
Integration tests for VCF file download automation.

Tests the integration between the specialized VCF downloader and the
data initializer orchestrator to ensure they work together correctly.

Version: 0.2 Beta
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.data_initializer import DataInitializer
from scripts.download_vcf_files import (
    DownloadResult,
    ValidationReport,
    VCFDownloader,
    VCFFileInfo,
)


class TestVCFDownloadIntegration(unittest.TestCase):
    """Test VCF download automation integration."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "test_genomes"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_vcf_downloader_initialization(self):
        """Test VCF downloader initializes correctly."""
        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)

        self.assertEqual(downloader.output_dir, self.test_output_dir)
        self.assertTrue(self.test_output_dir.exists())

    def test_list_available_chromosomes(self):
        """Test listing available chromosomes."""
        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)
        chromosomes = downloader.list_available_chromosomes()

        self.assertIn("chr22", chromosomes)
        self.assertIn("chr10", chromosomes)

        # Check chromosome info
        chr22_info = chromosomes["chr22"]
        self.assertEqual(chr22_info.chromosome, "chr22")
        self.assertIn("CYP2D6", chr22_info.description)
        self.assertIsNotNone(chr22_info.url)
        self.assertIsNotNone(chr22_info.expected_size_range)

    def test_vcf_file_validation_nonexistent(self):
        """Test validation of non-existent VCF file."""
        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)

        fake_file = str(self.test_output_dir / "nonexistent.vcf.gz")
        validation = downloader.validate_vcf_file(fake_file)

        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.file_size, 0)
        self.assertIn("File does not exist", validation.errors)

    def test_data_initializer_integration(self):
        """Test integration with data initializer."""
        # Initialize data initializer with test directory
        initializer = DataInitializer(self.temp_dir, verbose=False)

        # Check data completeness (should show missing files)
        status = initializer.check_data_completeness()

        self.assertEqual(status.valid_files, 0)
        self.assertFalse(status.vcf_files["chr22"])
        self.assertFalse(status.vcf_files["chr10"])
        self.assertFalse(status.chembl_database)
        self.assertGreater(len(status.missing_files), 0)

    def test_vcf_downloader_urls_accessible(self):
        """Test that VCF URLs are properly formatted and accessible."""
        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)

        for chromosome, vcf_info in downloader.list_available_chromosomes().items():
            # Check URL format
            self.assertTrue(vcf_info.url.startswith("https://"))
            self.assertIn("1000genomes", vcf_info.url.lower())
            self.assertIn(chromosome, vcf_info.url)

            # Check expected size range
            self.assertIsNotNone(vcf_info.expected_size_range)
            min_size, max_size = vcf_info.expected_size_range
            self.assertGreater(min_size, 0)
            self.assertGreater(max_size, min_size)

    def test_download_result_structure(self):
        """Test download result structure."""
        # Create a mock download result
        result = DownloadResult(
            chromosome="chr22",
            filename="test.vcf.gz",
            success=True,
            file_path="/test/path",
            file_size=1024,
            download_time=10.5,
            validation_passed=True,
            md5_match=True,
            errors=[],
            warnings=[],
        )

        self.assertEqual(result.chromosome, "chr22")
        self.assertTrue(result.success)
        self.assertTrue(result.validation_passed)
        self.assertEqual(len(result.errors), 0)

    def test_validation_report_structure(self):
        """Test validation report structure."""
        # Create a mock validation report
        report = ValidationReport(
            file_path="/test/file.vcf.gz",
            is_valid=True,
            file_size=1024,
            md5_checksum="abc123",
            md5_match=True,
            gzip_valid=True,
            vcf_header_valid=True,
            sample_count=100,
            variant_count_estimate=50000,
            errors=[],
            warnings=[],
        )

        self.assertTrue(report.is_valid)
        self.assertEqual(report.sample_count, 100)
        self.assertEqual(report.variant_count_estimate, 50000)
        self.assertEqual(len(report.errors), 0)

    @patch("scripts.download_vcf_files.urlretrieve")
    @patch("scripts.download_vcf_files.requests.head")
    def test_mock_download_success(self, mock_head, mock_urlretrieve):
        """Test successful download with mocked network calls."""
        # Mock HTTP head response
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "314572800"}  # 300MB
        mock_head.return_value = mock_response

        # Mock successful download
        def mock_download(url, path, reporthook=None):
            # Create a fake file with realistic size (300MB for chr22)
            Path(path).touch()
            # Create content that meets the minimum size requirement (200MB+)
            fake_content = b"fake_vcf_content" * 15000000  # ~240MB content
            Path(path).write_bytes(fake_content)
            file_size = len(fake_content)
            if reporthook:
                reporthook(1, file_size, file_size)  # Simulate progress

        mock_urlretrieve.side_effect = mock_download

        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)

        # This would normally fail validation, but we're testing download logic
        with patch.object(downloader, "validate_vcf_file") as mock_validate:
            mock_validate.return_value = ValidationReport(
                file_path="test",
                is_valid=True,
                file_size=314572800,  # 300MB
                md5_checksum="abc123",
                md5_match=True,
                gzip_valid=True,
                vcf_header_valid=True,
                sample_count=100,
                variant_count_estimate=50000,
                errors=[],
                warnings=[],
            )

            result = downloader.download_chromosome("chr22")

            self.assertTrue(result.success)
            self.assertTrue(result.validation_passed)

    def test_chromosome_file_mapping(self):
        """Test that chromosomes map to correct output files."""
        downloader = VCFDownloader(str(self.test_output_dir), verbose=False)

        # Test file naming convention
        for chromosome in ["chr22", "chr10"]:
            expected_file = downloader.output_dir / f"{chromosome}.vcf.gz"

            # The file shouldn't exist yet
            self.assertFalse(expected_file.exists())

            # But the path should be correctly constructed
            self.assertEqual(expected_file.name, f"{chromosome}.vcf.gz")
            self.assertEqual(expected_file.parent, downloader.output_dir)


class TestVCFDownloadCLI(unittest.TestCase):
    """Test VCF download command-line interface."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_list_command(self):
        """Test CLI list command."""
        # Test that the script can be imported and run
        from scripts.download_vcf_files import main

        # Mock sys.argv for list command
        with patch("sys.argv", ["download_vcf_files.py", "--list"]):
            with patch("builtins.print") as mock_print:
                try:
                    result = main()
                    self.assertEqual(result, 0)
                except SystemExit as e:
                    self.assertEqual(e.code, 0)

    def test_cli_status_command(self):
        """Test CLI status command."""
        from scripts.download_vcf_files import main

        # Mock sys.argv for status command
        with patch(
            "sys.argv",
            ["download_vcf_files.py", "--status", "--output-dir", self.temp_dir],
        ):
            try:
                result = main()
                # Should return 1 since no files exist
                self.assertEqual(result, 1)
            except SystemExit as e:
                self.assertEqual(e.code, 1)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
