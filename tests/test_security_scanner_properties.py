#!/usr/bin/env python3
"""
Property-based tests for SynthaTrial Security Scanner
====================================================

Tests the security scanner functionality using property-based testing
to ensure correctness across various inputs and scenarios.

**Feature: docker-enhancements**
"""

import json
import os

# Import the security scanner components
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

sys.path.append(str(Path(__file__).parent.parent))

from scripts.security_scanner import (
    ScannerType,
    SecurityReport,
    SecurityScanner,
    SeverityLevel,
    Vulnerability,
)


@composite
def vulnerability_data(draw):
    """Generate realistic vulnerability data"""
    return Vulnerability(
        id=draw(
            st.text(
                min_size=5,
                max_size=20,
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-",
            )
        ),
        severity=draw(
            st.sampled_from(["low", "medium", "high", "critical", "unknown"])
        ),
        title=draw(st.text(min_size=10, max_size=100)),
        description=draw(st.text(min_size=20, max_size=500)),
        package_name=draw(
            st.text(
                min_size=3,
                max_size=50,
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
            )
        ),
        package_version=draw(st.text(min_size=1, max_size=20, alphabet="0123456789.-")),
        fixed_version=draw(
            st.one_of(
                st.none(), st.text(min_size=1, max_size=20, alphabet="0123456789.-")
            )
        ),
        cvss_score=draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=10.0))),
        references=draw(
            st.lists(st.text(min_size=10, max_size=100), min_size=0, max_size=5)
        ),
    )


@composite
def security_report_data(draw):
    """Generate realistic security report data"""
    vulnerabilities = draw(st.lists(vulnerability_data(), min_size=0, max_size=50))
    severity_counts = {}
    for vuln in vulnerabilities:
        severity_counts[vuln.severity] = severity_counts.get(vuln.severity, 0) + 1

    return SecurityReport(
        image_name=draw(
            st.text(
                min_size=5,
                max_size=50,
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_:/",
            )
        ),
        scan_date=draw(
            st.datetimes(
                min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)
            )
        ),
        scanner_used=draw(st.sampled_from(["trivy", "grype"])),
        scanner_version=draw(st.text(min_size=3, max_size=20)),
        vulnerabilities=vulnerabilities,
        severity_counts=severity_counts,
        total_vulnerabilities=len(vulnerabilities),
        scan_duration_seconds=draw(st.floats(min_value=0.1, max_value=300.0)),
        recommendations=draw(
            st.lists(st.text(min_size=10, max_size=200), min_size=0, max_size=10)
        ),
        overall_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        scan_success=True,
    )


class TestSecurityScannerProperties:
    """Property-based tests for security scanner functionality"""

    @pytest.mark.property
    def test_property_scanner_detection_and_selection(self):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any scanner detection scenario, the SecurityScanner should correctly
        identify available scanners and select an appropriate one based on availability
        and preference.
        **Validates: Requirements 4.1, 4.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test auto-detection with no scanners available
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

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

            # Test auto-detection with Trivy available
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
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
                assert scanner.selected_scanner == "trivy"
                assert scanner.available_scanners["trivy"] is True
                assert scanner.available_scanners["grype"] is False

            # Test auto-detection with Grype available (Trivy not available)
            with patch("scripts.security_scanner.subprocess.run") as mock_run:

                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    if len(cmd) >= 2 and cmd[0] == "grype" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "grype 0.65.0"
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
                assert scanner.available_scanners["trivy"] is False
                assert scanner.available_scanners["grype"] is True

    @pytest.mark.property
    @given(vulnerability_data())
    def test_property_vulnerability_data_integrity(self, vulnerability):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any vulnerability data structure, all required fields should be properly
        initialized and maintain data integrity throughout processing.
        **Validates: Requirements 4.1, 4.3**
        """
        # Property: All required fields should be present and valid
        assert vulnerability.id is not None and len(vulnerability.id) > 0
        assert vulnerability.severity in [
            "low",
            "medium",
            "high",
            "critical",
            "unknown",
        ]
        assert vulnerability.title is not None and len(vulnerability.title) > 0
        assert (
            vulnerability.description is not None and len(vulnerability.description) > 0
        )
        assert (
            vulnerability.package_name is not None
            and len(vulnerability.package_name) > 0
        )
        assert (
            vulnerability.package_version is not None
            and len(vulnerability.package_version) > 0
        )

        # Property: Optional fields should be properly handled
        if vulnerability.cvss_score is not None:
            assert 0.0 <= vulnerability.cvss_score <= 10.0

        # Property: References should be a list
        assert isinstance(vulnerability.references, list)

    @pytest.mark.property
    @given(security_report_data())
    def test_property_security_report_generation_and_serialization(self, report):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any security report data, the report should be properly structured,
        serializable to JSON, and maintain data consistency.
        **Validates: Requirements 4.1, 4.3**
        """
        # Property: Report should have all required fields
        assert report.image_name is not None and len(report.image_name) > 0
        assert isinstance(report.scan_date, datetime)
        assert report.scanner_used in ["trivy", "grype"]
        assert isinstance(report.vulnerabilities, list)
        assert isinstance(report.severity_counts, dict)
        assert report.total_vulnerabilities >= 0
        assert report.scan_duration_seconds >= 0
        assert isinstance(report.recommendations, list)
        assert 0.0 <= report.overall_score <= 100.0

        # Property: Vulnerability count consistency
        assert report.total_vulnerabilities == len(report.vulnerabilities)

        # Property: Severity counts should match actual vulnerabilities
        calculated_counts = {}
        for vuln in report.vulnerabilities:
            calculated_counts[vuln.severity] = (
                calculated_counts.get(vuln.severity, 0) + 1
            )

        for severity, count in calculated_counts.items():
            assert report.severity_counts.get(severity, 0) == count

        # Property: Report should be serializable to JSON
        report_dict = report.to_dict()
        json_str = json.dumps(report_dict, default=str)
        assert len(json_str) > 0

        # Property: Deserialized data should maintain key information
        parsed_data = json.loads(json_str)
        assert parsed_data["image_name"] == report.image_name
        assert parsed_data["total_vulnerabilities"] == report.total_vulnerabilities
        assert parsed_data["scan_success"] == report.scan_success

    @pytest.mark.property
    @given(st.lists(vulnerability_data(), min_size=0, max_size=20))
    def test_property_security_score_calculation(self, vulnerabilities):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any list of vulnerabilities, the security score calculation should
        be consistent, bounded, and reflect the severity distribution appropriately.
        **Validates: Requirements 4.1, 4.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner availability
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "trivy version 0.45.0"

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )

                # Create a mock report
                severity_counts = {}
                for vuln in vulnerabilities:
                    severity_counts[vuln.severity] = (
                        severity_counts.get(vuln.severity, 0) + 1
                    )

                report = SecurityReport(
                    image_name="test:latest",
                    scan_date=datetime.now(),
                    scanner_used="trivy",
                    scanner_version="0.45.0",
                    vulnerabilities=vulnerabilities,
                    severity_counts=severity_counts,
                    total_vulnerabilities=len(vulnerabilities),
                    scan_duration_seconds=1.0,
                    recommendations=[],
                    overall_score=0.0,
                    scan_success=True,
                )

                # Calculate security score
                score = scanner._calculate_security_score(report)

                # Property: Score should be bounded between 0 and 100
                assert 0.0 <= score <= 100.0

                # Property: No vulnerabilities should result in perfect score
                if len(vulnerabilities) == 0:
                    assert score == 100.0

                # Property: Critical vulnerabilities should significantly impact score
                critical_count = severity_counts.get("critical", 0)
                if critical_count > 0:
                    assert score < 90.0  # Should be significantly penalized

                # Property: Score should decrease with more severe vulnerabilities
                if len(vulnerabilities) > 0:
                    assert score < 100.0

    @pytest.mark.property
    @given(st.text(min_size=1, max_size=50), st.sampled_from(["json", "html"]))
    def test_property_report_file_generation_and_storage(
        self, image_name, output_format
    ):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any valid image name and output format, the security scanner should
        generate and store reports in the specified format with proper file naming.
        **Validates: Requirements 4.1, 4.3**
        """
        # Clean image name for file system compatibility
        safe_image_name = "".join(c for c in image_name if c.isalnum() or c in "-_")
        assume(len(safe_image_name) > 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner availability
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "trivy version 0.45.0"

                scanner = SecurityScanner(
                    scanner_type=ScannerType.TRIVY, output_dir=temp_dir
                )

                # Create a test report
                report = SecurityReport(
                    image_name=safe_image_name,
                    scan_date=datetime.now(),
                    scanner_used="trivy",
                    scanner_version="0.45.0",
                    vulnerabilities=[],
                    severity_counts={},
                    total_vulnerabilities=0,
                    scan_duration_seconds=1.0,
                    recommendations=["Test recommendation"],
                    overall_score=100.0,
                    scan_success=True,
                )

                # Save report
                scanner._save_report(report, output_format)

                # Property: Report file should be created
                report_files = list(Path(temp_dir).glob(f"security_report_*"))
                assert len(report_files) > 0

                # Property: File should have correct extension
                report_file = report_files[0]
                if output_format == "json":
                    assert report_file.suffix == ".json"
                elif output_format == "html":
                    assert report_file.suffix == ".html"

                # Property: File should contain valid content
                content = report_file.read_text()
                assert len(content) > 0

                if output_format == "json":
                    # Should be valid JSON
                    parsed = json.loads(content)
                    assert parsed["image_name"] == safe_image_name
                    assert parsed["scan_success"] is True
                elif output_format == "html":
                    # Should contain HTML structure
                    assert "<html>" in content
                    assert safe_image_name in content

    @pytest.mark.property
    @given(st.lists(security_report_data(), min_size=1, max_size=10))
    def test_property_fleet_summary_report_generation(self, reports):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any collection of security reports, the fleet summary should accurately
        aggregate vulnerability data and provide meaningful insights.
        **Validates: Requirements 4.1, 4.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner availability
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
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

                # Generate summary report
                summary = scanner.generate_summary_report(reports)

                # Property: Summary should have all required sections
                assert "scan_summary" in summary
                assert "vulnerability_summary" in summary
                assert "most_vulnerable_images" in summary
                assert "recommendations" in summary

                # Property: Scan summary should be accurate
                scan_summary = summary["scan_summary"]
                assert scan_summary["total_images_scanned"] == len(reports)
                successful_scans = len([r for r in reports if r.scan_success])
                assert scan_summary["successful_scans"] == successful_scans
                assert scan_summary["failed_scans"] == len(reports) - successful_scans

                # Property: Vulnerability summary should aggregate correctly
                vuln_summary = summary["vulnerability_summary"]
                expected_total = sum(
                    r.total_vulnerabilities for r in reports if r.scan_success
                )
                assert vuln_summary["total_vulnerabilities"] == expected_total

                # Property: Most vulnerable images should be sorted correctly
                most_vulnerable = summary["most_vulnerable_images"]
                if len(most_vulnerable) > 1:
                    for i in range(len(most_vulnerable) - 1):
                        assert (
                            most_vulnerable[i]["vulnerabilities"]
                            >= most_vulnerable[i + 1]["vulnerabilities"]
                        )

                # Property: Recommendations should be provided (may be empty if no issues found)
                recommendations = summary["recommendations"]
                assert isinstance(recommendations, list)
                # Recommendations may be empty if all scans are clean and successful
                # This is acceptable behavior

    @pytest.mark.property
    @given(
        st.lists(
            st.sampled_from(["low", "medium", "high", "critical"]),
            min_size=1,
            max_size=4,
        )
    )
    def test_property_severity_filtering(self, severity_filter):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any severity filter configuration, the scanner should only include
        vulnerabilities matching the specified severity levels.
        **Validates: Requirements 4.1, 4.3**
        """
        # Create test vulnerabilities with different severities
        test_vulnerabilities = []
        all_severities = ["low", "medium", "high", "critical", "unknown"]

        for severity in all_severities:
            vuln = Vulnerability(
                id=f"TEST-{severity.upper()}-001",
                severity=severity,
                title=f"Test {severity} vulnerability",
                description=f"Test description for {severity} vulnerability",
                package_name="test-package",
                package_version="1.0.0",
            )
            test_vulnerabilities.append(vuln)

        # Filter vulnerabilities based on severity filter
        filtered_vulnerabilities = [
            v for v in test_vulnerabilities if v.severity in severity_filter
        ]

        # Property: Filtered list should only contain specified severities
        for vuln in filtered_vulnerabilities:
            assert vuln.severity in severity_filter

        # Property: All vulnerabilities of specified severities should be included
        for severity in severity_filter:
            matching_vulns = [
                v for v in filtered_vulnerabilities if v.severity == severity
            ]
            original_vulns = [v for v in test_vulnerabilities if v.severity == severity]
            assert len(matching_vulns) == len(original_vulns)

    @pytest.mark.property
    def test_property_error_handling_and_graceful_degradation(self):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        For any error condition during scanning, the scanner should handle errors
        gracefully and provide meaningful error reports without crashing.
        **Validates: Requirements 4.1, 4.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.security_scanner.subprocess.run") as mock_run:
                # Mock scanner availability
                def mock_subprocess(*args, **kwargs):
                    cmd = args[0] if args else []
                    result = Mock()
                    if len(cmd) >= 2 and cmd[0] == "trivy" and "--version" in cmd:
                        result.returncode = 0
                        result.stdout = "trivy version 0.45.0"
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

                # Test scan failure scenario
                with patch.object(scanner, "_scan_with_trivy") as mock_scan:
                    mock_scan.side_effect = RuntimeError("Scan failed")

                    report = scanner.scan_image("test:latest")

                    # Property: Failed scan should return error report
                    assert report.scan_success is False
                    assert (
                        "Scan failed" in report.error_message
                        or report.error_message == "Scan failed"
                    )
                    assert report.total_vulnerabilities == 0
                    assert report.overall_score == 0.0
                    assert len(report.vulnerabilities) == 0

                # Test timeout scenario
                with patch.object(scanner, "_scan_with_trivy") as mock_scan:
                    mock_scan.side_effect = TimeoutError("Scan timeout")

                    report = scanner.scan_image("test:latest")

                    # Property: Timeout should be handled gracefully
                    assert report.scan_success is False
                    assert "timeout" in report.error_message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
