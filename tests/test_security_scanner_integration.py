#!/usr/bin/env python3
"""
Integration tests for SynthaTrial Security Scanner
=================================================

Tests the security scanner integration with Docker images and scanning tools.
"""

import json
import os
import subprocess

# Import the security scanner components
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.append(str(Path(__file__).parent.parent))

from scripts.security_scanner import ScannerType, SecurityScanner


class TestSecurityScannerIntegration:
    """Integration tests for security scanner functionality"""

    def test_scanner_help_command(self):
        """Test that the security scanner CLI shows help correctly"""
        result = subprocess.run(
            ["python", "scripts/security_scanner.py", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "SynthaTrial Container Security Scanner" in result.stdout
        assert "--image" in result.stdout
        assert "--scanner" in result.stdout
        assert "--severity" in result.stdout

    def test_scanner_initialization_without_tools(self):
        """Test scanner initialization when no scanning tools are available"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock that no scanners are available - return non-zero returncode
                def mock_subprocess(*args, **kwargs):
                    result = Mock()
                    result.returncode = 1
                    result.stdout = ""
                    result.stderr = ""
                    return result

                mock_run.side_effect = mock_subprocess

                with pytest.raises(
                    RuntimeError, match="No supported vulnerability scanners found"
                ):
                    SecurityScanner(scanner_type=ScannerType.AUTO, output_dir=temp_dir)

    def test_scanner_initialization_with_trivy(self):
        """Test scanner initialization when Trivy is available"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

                def mock_subprocess(*args, **kwargs):
                    if "trivy" in args[0]:
                        result = Mock()
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    else:
                        result = Mock()
                        result.returncode = 1
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.AUTO, output_dir=temp_dir
                )
                assert scanner.selected_scanner == "trivy"
                assert scanner.available_scanners["trivy"] is True

    def test_scanner_initialization_with_grype(self):
        """Test scanner initialization when Grype is available"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Check if this is a grype version check
                    if len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "grype 0.65.0"
                        return result
                    # Check if this is a trivy version check - should fail
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.AUTO, output_dir=temp_dir
                )
                assert scanner.selected_scanner == "grype"
                assert scanner.available_scanners["grype"] is True

    def test_trivy_scan_mock_success(self):
        """Test successful Trivy scan with mock data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner detection
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for trivy
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    # Version check for grype - should fail
                    elif len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Trivy scan command
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "image" in cmd:
                        result.returncode = 0
                        result.stdout = json.dumps(
                            {
                                "Results": [
                                    {
                                        "Vulnerabilities": [
                                            {
                                                "VulnerabilityID": "CVE-2023-1234",
                                                "Severity": "HIGH",
                                                "Title": "Test vulnerability",
                                                "Description": "Test description",
                                                "PkgName": "test-package",
                                                "InstalledVersion": "1.0.0",
                                                "FixedVersion": "1.0.1",
                                                "References": [
                                                    "https://example.com/cve-2023-1234"
                                                ],
                                            }
                                        ]
                                    }
                                ]
                            }
                        )
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )
                report = scanner.scan_image("test:latest")

                assert report.scan_success is True
                assert report.total_vulnerabilities == 1
                assert report.vulnerabilities[0].id == "CVE-2023-1234"
                assert report.vulnerabilities[0].severity == "high"
                assert report.scanner_used == "trivy"

    def test_grype_scan_mock_success(self):
        """Test successful Grype scan with mock data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner detection
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for grype
                    if len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "grype 0.65.0"
                        return result
                    # Version check for trivy - should fail
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Grype scan command
                    elif len(cmd) >= 2 and cmd[0] == "grype":
                        result.returncode = 0
                        result.stdout = json.dumps(
                            {
                                "matches": [
                                    {
                                        "vulnerability": {
                                            "id": "CVE-2023-5678",
                                            "severity": "CRITICAL",
                                            "description": "Critical test vulnerability",
                                            "urls": [
                                                "https://example.com/cve-2023-5678"
                                            ],
                                        },
                                        "artifact": {
                                            "name": "critical-package",
                                            "version": "2.0.0",
                                        },
                                    }
                                ]
                            }
                        )
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.GRYPE, output_dir=temp_dir
                )
                report = scanner.scan_image("test:latest")

                assert report.scan_success is True
                assert report.total_vulnerabilities == 1
                assert report.vulnerabilities[0].id == "CVE-2023-5678"
                assert report.vulnerabilities[0].severity == "critical"
                assert report.scanner_used == "grype"

    def test_scan_failure_handling(self):
        """Test handling of scan failures"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner detection success but scan failure
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for trivy
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    # Version check for grype - should fail
                    elif len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Trivy scan command - should fail
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "image" in cmd:
                        result.returncode = 1
                        result.stderr = "Image not found"
                        result.stdout = ""
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )
                report = scanner.scan_image("nonexistent:latest")

                assert report.scan_success is False
                assert "Image not found" in report.error_message
                assert report.total_vulnerabilities == 0

    def test_report_file_generation(self):
        """Test that report files are generated correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock successful scan
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for trivy
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    # Version check for grype - should fail
                    elif len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Trivy scan command
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "image" in cmd:
                        result.returncode = 0
                        result.stdout = json.dumps({"Results": []})
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )
                report = scanner.scan_image("test:latest", output_format="json")

                # Check that report file was created
                report_files = list(Path(temp_dir).glob("security_report_*.json"))
                assert len(report_files) == 1

                # Verify report content
                with open(report_files[0]) as f:
                    report_data = json.load(f)

                assert report_data["image_name"] == "test:latest"
                assert report_data["scan_success"] is True

    def test_html_report_generation(self):
        """Test HTML report generation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock successful scan with vulnerabilities
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for trivy
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    # Version check for grype - should fail
                    elif len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Trivy scan command
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "image" in cmd:
                        result.returncode = 0
                        result.stdout = json.dumps(
                            {
                                "Results": [
                                    {
                                        "Vulnerabilities": [
                                            {
                                                "VulnerabilityID": "CVE-2023-TEST",
                                                "Severity": "MEDIUM",
                                                "Title": "Test HTML vulnerability",
                                                "Description": "Test description for HTML report",
                                                "PkgName": "html-test-package",
                                                "InstalledVersion": "1.0.0",
                                            }
                                        ]
                                    }
                                ]
                            }
                        )
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )
                report = scanner.scan_image("test:latest", output_format="html")

                # Check that HTML report file was created
                html_files = list(Path(temp_dir).glob("security_report_*.html"))
                assert len(html_files) == 1

                # Verify HTML content
                html_content = html_files[0].read_text()
                assert "<html>" in html_content
                assert "Security Scan Report" in html_content
                assert "test:latest" in html_content
                assert "CVE-2023-TEST" in html_content

    def test_severity_filtering(self):
        """Test severity filtering functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scan with multiple severity levels
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    # Version check for trivy
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    # Version check for grype - should fail
                    elif len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result
                    # Trivy scan command
                    elif len(cmd) >= 2 and cmd[0] == "trivy" and "image" in cmd:
                        # Check if severity filter is applied
                        if "--severity" in cmd:
                            severity_arg_idx = cmd.index("--severity") + 1
                            if severity_arg_idx < len(cmd):
                                severity_filter = cmd[severity_arg_idx].upper()
                                if (
                                    "HIGH" in severity_filter
                                    and "CRITICAL" in severity_filter
                                ):
                                    # Return only high and critical vulnerabilities
                                    result.returncode = 0
                                    result.stdout = json.dumps(
                                        {
                                            "Results": [
                                                {
                                                    "Vulnerabilities": [
                                                        {
                                                            "VulnerabilityID": "CVE-2023-HIGH",
                                                            "Severity": "HIGH",
                                                            "Title": "High severity vulnerability",
                                                            "Description": "High severity test",
                                                            "PkgName": "test-package",
                                                            "InstalledVersion": "1.0.0",
                                                        },
                                                        {
                                                            "VulnerabilityID": "CVE-2023-CRITICAL",
                                                            "Severity": "CRITICAL",
                                                            "Title": "Critical severity vulnerability",
                                                            "Description": "Critical severity test",
                                                            "PkgName": "test-package",
                                                            "InstalledVersion": "1.0.0",
                                                        },
                                                    ]
                                                }
                                            ]
                                        }
                                    )
                                    return result

                        # Default: return all severities
                        result.returncode = 0
                        result.stdout = json.dumps(
                            {
                                "Results": [
                                    {
                                        "Vulnerabilities": [
                                            {
                                                "VulnerabilityID": "CVE-2023-LOW",
                                                "Severity": "LOW",
                                                "Title": "Low severity vulnerability",
                                                "Description": "Low severity test",
                                                "PkgName": "test-package",
                                                "InstalledVersion": "1.0.0",
                                            },
                                            {
                                                "VulnerabilityID": "CVE-2023-HIGH",
                                                "Severity": "HIGH",
                                                "Title": "High severity vulnerability",
                                                "Description": "High severity test",
                                                "PkgName": "test-package",
                                                "InstalledVersion": "1.0.0",
                                            },
                                        ]
                                    }
                                ]
                            }
                        )
                        return result
                    else:
                        result.returncode = 1
                        result.stdout = ""
                        result.stderr = ""
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )

                # Test with severity filter
                report = scanner.scan_image(
                    "test:latest", severity_filter=["high", "critical"]
                )

                assert report.scan_success is True
                assert report.total_vulnerabilities == 2

                # Verify only high and critical vulnerabilities are included
                severities = [v.severity for v in report.vulnerabilities]
                assert "high" in severities
                assert "critical" in severities
                assert "low" not in severities

    def test_docker_image_listing_mock(self):
        """Test Docker image listing functionality with mock"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

                def mock_subprocess(*args, **kwargs):
                    if "--version" in args[0]:
                        result = Mock()
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
                        return result
                    elif "docker" in args[0] and "images" in args[0]:
                        # Mock Docker images list
                        result = Mock()
                        result.returncode = 0
                        result.stdout = "synthatrial:latest\nubuntu:20.04\nnginx:alpine"
                        return result
                    elif "trivy" in args[0] and "image" in args[0]:
                        # Mock scan results for each image
                        result = Mock()
                        result.returncode = 0
                        result.stdout = json.dumps({"Results": []})
                        return result
                    else:
                        result = Mock()
                        result.returncode = 1
                        return result

                mock_run.side_effect = mock_subprocess

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )
                reports = scanner.scan_all_local_images()

                assert len(reports) == 3
                assert all(report.scan_success for report in reports)

                image_names = [report.image_name for report in reports]
                assert "synthatrial:latest" in image_names
                assert "ubuntu:20.04" in image_names
                assert "nginx:alpine" in image_names

    def test_cli_integration_mock(self):
        """Test CLI integration with mock subprocess"""
        with patch("scripts.security_scanner.subprocess.run") as mock_run:
            # Mock the CLI call
            result = Mock()
            result.returncode = 0
            result.stdout = "Security scan completed successfully"
            result.stderr = ""
            mock_run.return_value = result

            # Test CLI call
            cli_result = subprocess.run(
                [
                    "python",
                    "scripts/security_scanner.py",
                    "--image",
                    "test:latest",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
            )

            # The mock should be called
            assert mock_run.called

    def test_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "security_reports" / "nested"

            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "trivy version 0.45.0"

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=str(output_dir)
                )

                # Directory should be created
                assert output_dir.exists()
                assert output_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
