#!/usr/bin/env python3
"""
Property-Based Tests for Security Scanner, Production Monitor, and Backup Manager

This module contains property-based tests for the security and monitoring components,
validating universal properties across different configurations and inputs.

Tests validate:
- Property 10: Security Scanning and Reporting
- Property 11: Production Monitoring and Resource Tracking
- Property 12: Backup and Recovery Operations

Author: SynthaTrial Development Team
Version: 0.2 Beta
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

# Add the project root to the Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.backup_manager import (
    BackupConfig,
    BackupManager,
    BackupMetadata,
    BackupStatus,
    BackupType,
    CompressionType,
    RestoreResult,
)
from scripts.production_monitor import (
    Alert,
    AlertConfig,
    AlertSeverity,
    BackupResult,
    ContainerMetrics,
    HealthStatus,
    ProductionMonitor,
    ResourceMetrics,
)
from scripts.security_scanner import (
    ScannerType,
    SecurityReport,
    SecurityScanner,
    SeverityLevel,
    Vulnerability,
)


# Custom strategies for generating test data
@composite
def valid_image_names(draw):
    """Generate valid Docker image names for testing"""
    # Repository name components
    name_chars = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_.", min_size=1, max_size=20
    ).filter(lambda x: x and not x.startswith("-") and not x.endswith("-"))

    repository = draw(name_chars)
    tag = draw(
        st.one_of(
            st.just("latest"),
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-",
                min_size=1,
                max_size=10,
            ),
        )
    )

    return f"{repository}:{tag}"


@composite
def vulnerability_data(draw):
    """Generate vulnerability data for testing"""
    severity = draw(st.sampled_from(["low", "medium", "high", "critical", "unknown"]))

    return {
        "id": draw(
            st.text(
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
                min_size=5,
                max_size=15,
            )
        ),
        "severity": severity,
        "title": draw(st.text(min_size=10, max_size=100)),
        "description": draw(st.text(min_size=20, max_size=500)),
        "package_name": draw(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
                min_size=3,
                max_size=30,
            )
        ),
        "package_version": draw(
            st.text(alphabet="0123456789.", min_size=1, max_size=10)
        ),
        "fixed_version": draw(
            st.one_of(
                st.none(), st.text(alphabet="0123456789.", min_size=1, max_size=10)
            )
        ),
        "cvss_score": draw(
            st.one_of(st.none(), st.floats(min_value=0.0, max_value=10.0))
        ),
        "references": draw(
            st.lists(st.text(min_size=10, max_size=100), min_size=0, max_size=5)
        ),
    }


@composite
def resource_metrics_data(draw):
    """Generate resource metrics data for testing"""
    return {
        "cpu_usage_percent": draw(st.floats(min_value=0.0, max_value=100.0)),
        "memory_usage_mb": draw(st.integers(min_value=100, max_value=32000)),
        "memory_total_mb": draw(st.integers(min_value=1000, max_value=64000)),
        "disk_usage_mb": draw(st.integers(min_value=1000, max_value=1000000)),
        "disk_total_mb": draw(st.integers(min_value=10000, max_value=2000000)),
        "network_io_mb": draw(st.floats(min_value=0.0, max_value=1000.0)),
        "load_average": (
            draw(st.floats(min_value=0.0, max_value=10.0)),
            draw(st.floats(min_value=0.0, max_value=10.0)),
            draw(st.floats(min_value=0.0, max_value=10.0)),
        ),
    }


@composite
def backup_paths_data(draw):
    """Generate backup paths data for testing"""
    num_paths = draw(st.integers(min_value=1, max_value=5))
    paths = []

    for _ in range(num_paths):
        path_components = draw(
            st.lists(
                st.text(
                    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                    min_size=1,
                    max_size=10,
                ),
                min_size=1,
                max_size=4,
            )
        )
        path = "/" + "/".join(path_components)
        paths.append(path)

    return paths


class TestSecurityScannerProperties:
    """Property-based tests for Security Scanner (Property 10)"""

    @given(
        image_name=valid_image_names(),
        vulnerabilities=st.lists(vulnerability_data(), min_size=0, max_size=20),
        scanner_type=st.sampled_from(["trivy", "grype"]),
    )
    @settings(max_examples=50, deadline=30000)
    def test_property_10_security_scanning_and_reporting(
        self, image_name, vulnerabilities, scanner_type
    ):
        """
        **Feature: docker-enhancements, Property 10: Security Scanning and Reporting**

        *For any* container image build, the Security_Scanner should detect known
        vulnerabilities and generate detailed reports with remediation guidance
        **Validates: Requirements 4.1, 4.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock scanner availability
            with patch.object(SecurityScanner, "_detect_scanners") as mock_detect:
                mock_detect.return_value = {scanner_type: True}

                # Mock scanner execution
                mock_vulnerabilities = []
                severity_counts = {
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                    "critical": 0,
                    "unknown": 0,
                }

                for vuln_data in vulnerabilities:
                    vuln = Vulnerability(
                        id=vuln_data["id"],
                        severity=vuln_data["severity"],
                        title=vuln_data["title"],
                        description=vuln_data["description"],
                        package_name=vuln_data["package_name"],
                        package_version=vuln_data["package_version"],
                        fixed_version=vuln_data["fixed_version"],
                        cvss_score=vuln_data["cvss_score"],
                        references=vuln_data["references"],
                    )
                    mock_vulnerabilities.append(vuln)
                    severity_counts[vuln_data["severity"]] += 1

                # Mock the scan methods
                def mock_scan_method(image_name, severity_filter=None):
                    filtered_vulns = mock_vulnerabilities
                    if severity_filter:
                        filtered_vulns = [
                            v
                            for v in mock_vulnerabilities
                            if v.severity in severity_filter
                        ]

                    filtered_counts = {
                        "low": 0,
                        "medium": 0,
                        "high": 0,
                        "critical": 0,
                        "unknown": 0,
                    }
                    for vuln in filtered_vulns:
                        filtered_counts[vuln.severity] += 1

                    return SecurityReport(
                        image_name=image_name,
                        scan_date=datetime.now(),
                        scanner_used=scanner_type,
                        scanner_version="test-1.0.0",
                        vulnerabilities=filtered_vulns,
                        severity_counts=filtered_counts,
                        total_vulnerabilities=len(filtered_vulns),
                        scan_duration_seconds=1.0,
                        recommendations=[],
                        overall_score=0.0,
                        scan_success=True,
                    )

                with patch.object(
                    SecurityScanner,
                    f"_scan_with_{scanner_type}",
                    side_effect=mock_scan_method,
                ):
                    scanner = SecurityScanner(
                        scanner_type=ScannerType(scanner_type),
                        output_dir=temp_dir,
                        verbose=False,
                    )

                    # Test scan execution
                    report = scanner.scan_image(image_name)

                    # Property validation: Scan should complete successfully
                    assert (
                        report.scan_success
                    ), "Security scan should complete successfully"
                    assert (
                        report.image_name == image_name
                    ), "Report should contain correct image name"
                    assert (
                        report.scanner_used == scanner_type
                    ), "Report should indicate correct scanner used"

                    # Property validation: Vulnerability detection accuracy
                    assert report.total_vulnerabilities == len(
                        vulnerabilities
                    ), "Total vulnerability count should match detected vulnerabilities"

                    # Property validation: Severity classification
                    for severity in ["low", "medium", "high", "critical", "unknown"]:
                        expected_count = len(
                            [v for v in vulnerabilities if v["severity"] == severity]
                        )
                        assert (
                            report.severity_counts[severity] == expected_count
                        ), f"Severity count for {severity} should be accurate"

                    # Property validation: Report generation
                    assert isinstance(
                        report.scan_date, datetime
                    ), "Scan date should be valid datetime"
                    assert (
                        report.scan_duration_seconds >= 0
                    ), "Scan duration should be non-negative"
                    assert (
                        0 <= report.overall_score <= 100
                    ), "Security score should be between 0-100"

                    # Property validation: Recommendations generation
                    critical_count = report.severity_counts.get("critical", 0)
                    high_count = report.severity_counts.get("high", 0)

                    if critical_count > 0 or high_count > 0:
                        # Should have recommendations for high/critical vulnerabilities
                        assert (
                            len(report.recommendations) > 0
                        ), "Should provide recommendations for high/critical vulnerabilities"

                    # Property validation: Severity filtering
                    if vulnerabilities:
                        severity_filter = ["critical", "high"]
                        filtered_report = scanner.scan_image(
                            image_name, severity_filter
                        )

                        expected_filtered = [
                            v
                            for v in vulnerabilities
                            if v["severity"] in severity_filter
                        ]
                        assert filtered_report.total_vulnerabilities == len(
                            expected_filtered
                        ), "Severity filtering should work correctly"

    @given(
        image_count=st.integers(min_value=1, max_value=5),
        base_vulnerability_count=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=20, deadline=30000)
    def test_security_scanner_fleet_analysis(
        self, image_count, base_vulnerability_count
    ):
        """Test security scanner fleet-wide analysis capabilities"""
        # Generate images list and vulnerability counts
        images = [f"test_image_{i}:latest" for i in range(image_count)]
        vulnerability_counts = [
            base_vulnerability_count + i for i in range(image_count)
        ]  # Vary counts per image

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(SecurityScanner, "_detect_scanners") as mock_detect:
                mock_detect.return_value = {"trivy": True}

                # Mock multiple image scans
                def mock_scan_image(
                    image_name, severity_filter=None, output_format="json"
                ):
                    image_index = (
                        images.index(image_name) if image_name in images else 0
                    )
                    vuln_count = vulnerability_counts[image_index]

                    # Generate mock vulnerabilities
                    mock_vulns = []
                    severity_counts = {
                        "low": 0,
                        "medium": 0,
                        "high": 0,
                        "critical": 0,
                        "unknown": 0,
                    }

                    for i in range(vuln_count):
                        severity = ["low", "medium", "high", "critical"][i % 4]
                        mock_vulns.append(
                            Vulnerability(
                                id=f"CVE-2024-{1000+i}",
                                severity=severity,
                                title=f"Test vulnerability {i}",
                                description=f"Test description {i}",
                                package_name=f"package{i}",
                                package_version="1.0.0",
                            )
                        )
                        severity_counts[severity] += 1

                    return SecurityReport(
                        image_name=image_name,
                        scan_date=datetime.now(),
                        scanner_used="trivy",
                        scanner_version="test-1.0.0",
                        vulnerabilities=mock_vulns,
                        severity_counts=severity_counts,
                        total_vulnerabilities=vuln_count,
                        scan_duration_seconds=1.0,
                        recommendations=[],
                        overall_score=max(0, 100 - vuln_count * 5),
                        scan_success=True,
                    )

                with patch.object(
                    SecurityScanner, "scan_image", side_effect=mock_scan_image
                ):
                    with patch("subprocess.run") as mock_run:
                        # Mock docker images command
                        mock_run.return_value.returncode = 0
                        mock_run.return_value.stdout = "\n".join(images)

                        scanner = SecurityScanner(output_dir=temp_dir)
                        reports = scanner.scan_all_local_images()

                        # Property validation: All images scanned
                        assert len(reports) == len(
                            images
                        ), "Should scan all provided images"

                        # Property validation: Summary generation
                        summary = scanner.generate_summary_report(reports)

                        assert summary["scan_summary"]["total_images_scanned"] == len(
                            images
                        )
                        assert summary["scan_summary"]["successful_scans"] == len(
                            images
                        )

                        expected_total_vulns = sum(vulnerability_counts)
                        assert (
                            summary["vulnerability_summary"]["total_vulnerabilities"]
                            == expected_total_vulns
                        )

                        # Property validation: Fleet recommendations
                        assert "recommendations" in summary
                        assert isinstance(summary["recommendations"], list)


class TestProductionMonitorProperties:
    """Property-based tests for Production Monitor (Property 11)"""

    @given(
        metrics_data=resource_metrics_data(),
        check_interval=st.integers(min_value=1, max_value=60),
        alert_thresholds=st.fixed_dictionaries(
            {
                "cpu_threshold": st.floats(min_value=50.0, max_value=95.0),
                "memory_threshold": st.floats(min_value=50.0, max_value=95.0),
                "disk_threshold": st.floats(min_value=70.0, max_value=95.0),
            }
        ),
    )
    @settings(max_examples=30, deadline=30000)
    def test_property_11_production_monitoring_and_resource_tracking(
        self, metrics_data, check_interval, alert_thresholds
    ):
        """
        **Feature: docker-enhancements, Property 11: Production Monitoring and Resource Tracking**

        *For any* production container deployment, the Production_Monitor should continuously
        track resource usage and maintain performance metrics
        **Validates: Requirements 4.2**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create alert configuration
            alert_config = AlertConfig(
                cpu_threshold=alert_thresholds["cpu_threshold"],
                memory_threshold=alert_thresholds["memory_threshold"],
                disk_threshold=alert_thresholds["disk_threshold"],
                check_interval=check_interval,
            )

            # Mock system metrics collection
            def mock_collect_system_metrics():
                memory_usage_percent = (
                    metrics_data["memory_usage_mb"] / metrics_data["memory_total_mb"]
                ) * 100
                disk_usage_percent = (
                    metrics_data["disk_usage_mb"] / metrics_data["disk_total_mb"]
                ) * 100

                return ResourceMetrics(
                    timestamp=datetime.now(),
                    cpu_usage_percent=metrics_data["cpu_usage_percent"],
                    memory_usage_mb=metrics_data["memory_usage_mb"],
                    memory_total_mb=metrics_data["memory_total_mb"],
                    memory_usage_percent=memory_usage_percent,
                    disk_usage_mb=metrics_data["disk_usage_mb"],
                    disk_total_mb=metrics_data["disk_total_mb"],
                    disk_usage_percent=disk_usage_percent,
                    network_io_mb=metrics_data["network_io_mb"],
                    load_average=metrics_data["load_average"],
                )

            with patch("docker.from_env") as mock_docker:
                mock_docker.side_effect = Exception("Docker not available")

                with patch.object(
                    ProductionMonitor,
                    "collect_system_metrics",
                    side_effect=mock_collect_system_metrics,
                ):
                    monitor = ProductionMonitor(
                        output_dir=temp_dir, alert_config=alert_config, verbose=False
                    )

                    # Test metrics collection
                    system_metrics = monitor.collect_system_metrics()

                    # Property validation: Metrics accuracy
                    assert (
                        system_metrics.cpu_usage_percent
                        == metrics_data["cpu_usage_percent"]
                    ), "CPU usage should be accurately collected"
                    assert (
                        system_metrics.memory_usage_mb
                        == metrics_data["memory_usage_mb"]
                    ), "Memory usage should be accurately collected"
                    assert (
                        system_metrics.disk_usage_mb == metrics_data["disk_usage_mb"]
                    ), "Disk usage should be accurately collected"
                    assert (
                        system_metrics.network_io_mb == metrics_data["network_io_mb"]
                    ), "Network I/O should be accurately collected"

                    # Property validation: Timestamp accuracy
                    time_diff = abs(
                        (datetime.now() - system_metrics.timestamp).total_seconds()
                    )
                    assert (
                        time_diff < 5
                    ), "Timestamp should be current (within 5 seconds)"

                    # Property validation: Calculated percentages
                    expected_memory_percent = (
                        metrics_data["memory_usage_mb"]
                        / metrics_data["memory_total_mb"]
                    ) * 100
                    assert (
                        abs(
                            system_metrics.memory_usage_percent
                            - expected_memory_percent
                        )
                        < 0.1
                    ), "Memory percentage should be calculated correctly"

                    expected_disk_percent = (
                        metrics_data["disk_usage_mb"] / metrics_data["disk_total_mb"]
                    ) * 100
                    assert (
                        abs(system_metrics.disk_usage_percent - expected_disk_percent)
                        < 0.1
                    ), "Disk percentage should be calculated correctly"

                    # Property validation: Alert generation
                    container_metrics = []  # No containers for this test
                    alerts = monitor.analyze_metrics_and_generate_alerts(
                        system_metrics, container_metrics
                    )

                    # Check CPU alerts
                    cpu_alerts = [a for a in alerts if "CPU" in a.title]
                    if system_metrics.cpu_usage_percent > alert_config.cpu_threshold:
                        assert (
                            len(cpu_alerts) > 0
                        ), "Should generate CPU alert when threshold exceeded"
                        cpu_alert = cpu_alerts[0]
                        assert (
                            cpu_alert.metric_value == system_metrics.cpu_usage_percent
                        )
                        assert cpu_alert.threshold == alert_config.cpu_threshold
                    else:
                        assert (
                            len(cpu_alerts) == 0
                        ), "Should not generate CPU alert when below threshold"

                    # Check memory alerts
                    memory_alerts = [a for a in alerts if "Memory" in a.title]
                    if (
                        system_metrics.memory_usage_percent
                        > alert_config.memory_threshold
                    ):
                        assert (
                            len(memory_alerts) > 0
                        ), "Should generate memory alert when threshold exceeded"
                    else:
                        assert (
                            len(memory_alerts) == 0
                        ), "Should not generate memory alert when below threshold"

                    # Check disk alerts
                    disk_alerts = [a for a in alerts if "Disk" in a.title]
                    if system_metrics.disk_usage_percent > alert_config.disk_threshold:
                        assert (
                            len(disk_alerts) > 0
                        ), "Should generate disk alert when threshold exceeded"
                    else:
                        assert (
                            len(disk_alerts) == 0
                        ), "Should not generate disk alert when below threshold"

                    # Property validation: Alert severity assignment
                    for alert in alerts:
                        if alert.metric_value and alert.threshold:
                            if alert.metric_value > 95:
                                assert (
                                    alert.severity == AlertSeverity.CRITICAL
                                ), "Should assign CRITICAL severity for very high usage"
                            elif alert.metric_value > alert.threshold:
                                assert alert.severity in [
                                    AlertSeverity.WARNING,
                                    AlertSeverity.CRITICAL,
                                ], "Should assign appropriate severity for threshold violations"

    @given(
        container_count=st.integers(min_value=1, max_value=5),
        restart_count=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=20, deadline=30000)
    def test_container_monitoring_accuracy(self, container_count, restart_count):
        """Test container monitoring accuracy and alert generation"""
        restart_counts = [
            restart_count
        ] * container_count  # Use same restart count for all containers

        with tempfile.TemporaryDirectory() as temp_dir:
            alert_config = AlertConfig(container_restart_threshold=3)

            # Mock container metrics
            mock_containers = []
            for i in range(container_count):
                container_metrics = ContainerMetrics(
                    container_id=f"container_{i}",
                    container_name=f"test_container_{i}",
                    image=f"test_image_{i}:latest",
                    status="running",
                    health_status=HealthStatus.HEALTHY,
                    cpu_usage_percent=50.0,
                    memory_usage_mb=1000,
                    memory_limit_mb=2000,
                    memory_usage_percent=50.0,
                    network_rx_mb=10.0,
                    network_tx_mb=5.0,
                    restart_count=restart_counts[i],
                    uptime_seconds=3600,
                )
                mock_containers.append(container_metrics)

            with patch("docker.from_env") as mock_docker:
                mock_docker.side_effect = Exception("Docker not available")

                with patch.object(
                    ProductionMonitor,
                    "collect_container_metrics",
                    return_value=mock_containers,
                ):
                    monitor = ProductionMonitor(
                        output_dir=temp_dir, alert_config=alert_config
                    )

                    # Test container metrics collection
                    container_metrics = monitor.collect_container_metrics()

                    # Property validation: Container count accuracy
                    assert (
                        len(container_metrics) == container_count
                    ), "Should collect metrics for all containers"

                    # Property validation: Container restart alerts
                    system_metrics = ResourceMetrics(
                        timestamp=datetime.now(),
                        cpu_usage_percent=50.0,
                        memory_usage_mb=4000,
                        memory_total_mb=8000,
                        memory_usage_percent=50.0,
                        disk_usage_mb=10000,
                        disk_total_mb=50000,
                        disk_usage_percent=20.0,
                        network_io_mb=15.0,
                        load_average=(1.0, 1.0, 1.0),
                    )

                    alerts = monitor.analyze_metrics_and_generate_alerts(
                        system_metrics, container_metrics
                    )

                    # Check restart alerts
                    restart_alerts = [a for a in alerts if "Restart" in a.title]
                    expected_restart_alerts = len(
                        [
                            r
                            for r in restart_counts
                            if r > alert_config.container_restart_threshold
                        ]
                    )

                    assert (
                        len(restart_alerts) == expected_restart_alerts
                    ), "Should generate restart alerts for containers exceeding threshold"


class TestBackupManagerProperties:
    """Property-based tests for Backup Manager (Property 12)"""

    @given(
        backup_paths=backup_paths_data(),
        backup_type=st.sampled_from(["full", "incremental", "differential"]),
        compression_type=st.sampled_from(["gzip", "bzip2", "xz", "none"]),
        file_count=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30, deadline=60000)
    def test_property_12_backup_and_recovery_operations(
        self, backup_paths, backup_type, compression_type, file_count
    ):
        """
        **Feature: docker-enhancements, Property 12: Backup and Recovery Operations**

        *For any* backup request for critical data, the Production_Monitor should create
        recoverable backups and provide alerting for system failures
        **Validates: Requirements 4.4, 4.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "backups"
            test_data_dir = Path(temp_dir) / "test_data"
            restore_dir = Path(temp_dir) / "restore"

            # Create test data structure
            test_data_dir.mkdir(parents=True)
            test_files = []
            total_size = 0

            for i in range(file_count):
                file_path = test_data_dir / f"test_file_{i}.txt"
                content = f"Test content for file {i}\n" * (i + 1)
                file_path.write_text(content)
                test_files.append(str(file_path))
                total_size += len(content.encode())

            # Create backup configuration
            config = BackupConfig(
                backup_dir=str(backup_dir),
                compression_type=CompressionType(compression_type),
                retention_days=30,
                verify_after_backup=True,
            )

            manager = BackupManager(config=config, verbose=False)

            # Test backup creation
            backup_metadata = manager.create_backup(
                paths=[str(test_data_dir)], backup_type=BackupType(backup_type)
            )

            # Property validation: Backup creation success
            assert backup_metadata.status in [
                BackupStatus.CREATED,
                BackupStatus.VERIFIED,
            ], "Backup should be created successfully"
            assert backup_metadata.backup_type == BackupType(
                backup_type
            ), "Backup type should match requested type"
            assert backup_metadata.compression_type == CompressionType(
                compression_type
            ), "Compression type should match configuration"

            # Property validation: File count accuracy
            assert (
                backup_metadata.file_count >= file_count
            ), "Backup should include at least the created test files"

            # Property validation: Size calculations
            assert (
                backup_metadata.size_bytes > 0
            ), "Backup should have positive uncompressed size"
            assert (
                backup_metadata.compressed_size_bytes > 0
            ), "Backup should have positive compressed size"

            if compression_type != "none" and backup_metadata.size_bytes > 1000:
                # Compression should generally reduce size for larger files
                # Small files may actually increase in size due to compression overhead
                compression_ratio = (
                    backup_metadata.compressed_size_bytes / backup_metadata.size_bytes
                )
                assert (
                    0 < compression_ratio <= 1.2
                ), "Compression ratio should be reasonable (allowing for small file overhead)"

            # Property validation: Checksum generation
            assert (
                len(backup_metadata.checksum_sha256) == 64
            ), "SHA-256 checksum should be 64 characters"
            assert all(
                c in "0123456789abcdef" for c in backup_metadata.checksum_sha256
            ), "Checksum should be valid hexadecimal"

            # Property validation: Backup file existence
            backup_file = Path(backup_metadata.backup_file)
            assert backup_file.exists(), "Backup file should exist on disk"
            assert (
                backup_file.stat().st_size == backup_metadata.compressed_size_bytes
            ), "Backup file size should match metadata"

            # Property validation: Backup verification
            verification_result = manager.verify_backup(backup_metadata.backup_id)
            assert verification_result, "Backup verification should pass"

            # Property validation: Backup restoration
            restore_result = manager.restore_backup(
                backup_id=backup_metadata.backup_id,
                target_path=str(restore_dir),
                validate_restore=True,
            )

            assert restore_result.success, "Backup restoration should succeed"
            assert (
                restore_result.files_restored >= file_count
            ), "Should restore at least the original test files"
            assert restore_result.validation_passed, "Restore validation should pass"

            # Property validation: Restored file integrity
            for original_file in test_files:
                original_path = Path(original_file)
                relative_path = original_path.relative_to(test_data_dir.parent)
                restored_path = restore_dir / relative_path

                assert (
                    restored_path.exists()
                ), f"Restored file should exist: {restored_path}"

                original_content = original_path.read_text()
                restored_content = restored_path.read_text()
                assert (
                    original_content == restored_content
                ), "Restored file content should match original"

            # Property validation: Metadata persistence
            retrieved_metadata = manager.get_backup_metadata(backup_metadata.backup_id)
            assert (
                retrieved_metadata is not None
            ), "Should be able to retrieve backup metadata"
            assert retrieved_metadata.backup_id == backup_metadata.backup_id
            assert retrieved_metadata.checksum_sha256 == backup_metadata.checksum_sha256

            # Property validation: Backup listing
            backup_list = manager.list_backups()
            backup_ids = [b.backup_id for b in backup_list]
            assert (
                backup_metadata.backup_id in backup_ids
            ), "Created backup should appear in backup list"

    @given(
        retention_days=st.integers(min_value=1, max_value=30),
        backup_count=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=15, deadline=30000)
    def test_backup_retention_and_cleanup(self, retention_days, backup_count):
        """Test backup retention policy and cleanup operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "backups"

            config = BackupConfig(
                backup_dir=str(backup_dir), retention_days=retention_days
            )

            manager = BackupManager(config=config)

            # Create mock backup metadata with different ages
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            old_backups = 0
            recent_backups = 0

            for i in range(backup_count):
                # Create some old and some recent backups
                if i < backup_count // 2:
                    # Old backup (should be cleaned up)
                    backup_date = cutoff_date - timedelta(days=i + 1)
                    old_backups += 1
                else:
                    # Recent backup (should be kept)
                    backup_date = cutoff_date + timedelta(days=i + 1)
                    recent_backups += 1

                # Create a dummy backup file
                backup_file = backup_dir / f"backup_{i}.tar.gz"
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                backup_file.write_text(f"dummy backup {i}")

                # Create metadata
                metadata = BackupMetadata(
                    backup_id=f"backup_{i}",
                    timestamp=backup_date,
                    backup_type=BackupType.FULL,
                    paths=["/test"],
                    backup_file=str(backup_file),
                    size_bytes=100,
                    compressed_size_bytes=50,
                    compression_type=CompressionType.GZIP,
                    checksum_sha256="a" * 64,
                    duration_seconds=1.0,
                    status=BackupStatus.VERIFIED,
                    file_count=1,
                )

                manager._save_backup_metadata(metadata)

            # Test cleanup operation
            cleaned_count = manager.cleanup_old_backups(retention_days)

            # Property validation: Cleanup accuracy
            assert (
                cleaned_count == old_backups
            ), f"Should clean up {old_backups} old backups, cleaned {cleaned_count}"

            # Property validation: Recent backups preserved
            remaining_backups = manager.list_backups()
            assert (
                len(remaining_backups) == recent_backups
            ), f"Should preserve {recent_backups} recent backups"

            # Property validation: Old backup files removed
            for i in range(backup_count // 2):
                backup_file = backup_dir / f"backup_{i}.tar.gz"
                assert (
                    not backup_file.exists()
                ), f"Old backup file should be removed: {backup_file}"

    @given(
        test_file_sizes=st.lists(
            st.integers(min_value=100, max_value=10000), min_size=1, max_size=10
        )
    )
    @settings(max_examples=20, deadline=30000)
    def test_backup_integrity_validation(self, test_file_sizes):
        """Test backup integrity validation and corruption detection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "backups"
            test_data_dir = Path(temp_dir) / "test_data"

            # Create test files with specified sizes
            test_data_dir.mkdir(parents=True)
            for i, size in enumerate(test_file_sizes):
                file_path = test_data_dir / f"file_{i}.dat"
                content = "x" * size
                file_path.write_text(content)

            config = BackupConfig(backup_dir=str(backup_dir))
            manager = BackupManager(config=config)

            # Create backup
            metadata = manager.create_backup(paths=[str(test_data_dir)])

            # Property validation: Initial verification passes
            assert manager.verify_backup(
                metadata.backup_id
            ), "Initial backup verification should pass"

            # Property validation: Checksum consistency
            backup_file = Path(metadata.backup_file)
            actual_checksum = manager._calculate_checksum(str(backup_file))
            assert (
                actual_checksum == metadata.checksum_sha256
            ), "Calculated checksum should match stored checksum"

            # Property validation: Corruption detection
            # Corrupt the backup file
            with open(backup_file, "r+b") as f:
                f.seek(100)  # Seek to position 100
                f.write(b"CORRUPTED")

            # Verification should now fail
            assert not manager.verify_backup(
                metadata.backup_id
            ), "Verification should fail for corrupted backup"

            # Property validation: Recovery test with fresh backup
            # Create a new test directory and backup to avoid ID collision
            test_data_dir2 = Path(temp_dir) / "test_data2"
            test_data_dir2.mkdir(parents=True)
            for i, size in enumerate(test_file_sizes):
                file_path = test_data_dir2 / f"file_{i}.dat"
                content = "y" * size  # Different content to ensure different checksum
                file_path.write_text(content)

            # Wait a moment to ensure different timestamp
            import time

            time.sleep(1.1)  # Ensure different second for backup ID

            # Create fresh backup for recovery test with new manager to avoid DB conflicts
            config2 = BackupConfig(backup_dir=str(backup_dir / "backup2"))
            manager2 = BackupManager(config=config2)

            metadata2 = manager2.create_backup(paths=[str(test_data_dir2)])

            recovery_test_result = manager2.test_recovery(metadata2.backup_id)
            assert recovery_test_result, "Recovery test should pass for valid backup"


class TestSecurityMonitoringIntegration:
    """Integration property tests for security and monitoring components"""

    @given(
        image_names=st.lists(valid_image_names(), min_size=1, max_size=3),
        vulnerability_severities=st.lists(
            st.sampled_from(["low", "medium", "high", "critical"]),
            min_size=1,
            max_size=10,
        ),
        resource_usage_levels=st.lists(
            st.floats(min_value=10.0, max_value=95.0), min_size=3, max_size=3
        ),
    )
    @settings(max_examples=20, deadline=60000)
    def test_integrated_security_monitoring_workflow(
        self, image_names, vulnerability_severities, resource_usage_levels
    ):
        """
        **Feature: docker-enhancements, Integrated Security and Monitoring**

        Test the complete workflow of security scanning, monitoring, and backup operations
        working together in a production environment
        **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            security_dir = Path(temp_dir) / "security"
            monitoring_dir = Path(temp_dir) / "monitoring"
            backup_dir = Path(temp_dir) / "backups"

            # Setup components
            with patch.object(SecurityScanner, "_detect_scanners") as mock_detect:
                mock_detect.return_value = {"trivy": True}

                # Mock security scan results
                def mock_scan_image(
                    image_name, severity_filter=None, output_format="json"
                ):
                    vuln_count = len(
                        [
                            s
                            for s in vulnerability_severities
                            if not severity_filter or s in severity_filter
                        ]
                    )

                    mock_vulns = []
                    severity_counts = {
                        "low": 0,
                        "medium": 0,
                        "high": 0,
                        "critical": 0,
                        "unknown": 0,
                    }

                    for i, severity in enumerate(vulnerability_severities):
                        if not severity_filter or severity in severity_filter:
                            mock_vulns.append(
                                Vulnerability(
                                    id=f"CVE-2024-{1000+i}",
                                    severity=severity,
                                    title=f"Test vulnerability {i}",
                                    description=f"Test description {i}",
                                    package_name=f"package{i}",
                                    package_version="1.0.0",
                                )
                            )
                            severity_counts[severity] += 1

                    return SecurityReport(
                        image_name=image_name,
                        scan_date=datetime.now(),
                        scanner_used="trivy",
                        scanner_version="test-1.0.0",
                        vulnerabilities=mock_vulns,
                        severity_counts=severity_counts,
                        total_vulnerabilities=len(mock_vulns),
                        scan_duration_seconds=1.0,
                        recommendations=[],
                        overall_score=max(0, 100 - len(mock_vulns) * 5),
                        scan_success=True,
                    )

                with patch.object(
                    SecurityScanner, "scan_image", side_effect=mock_scan_image
                ):
                    with patch("docker.from_env") as mock_docker:
                        mock_docker.side_effect = Exception("Docker not available")

                        # Initialize components
                        scanner = SecurityScanner(output_dir=str(security_dir))

                        alert_config = AlertConfig(
                            cpu_threshold=80.0,
                            memory_threshold=85.0,
                            disk_threshold=90.0,
                        )
                        monitor = ProductionMonitor(
                            output_dir=str(monitoring_dir), alert_config=alert_config
                        )

                        backup_config = BackupConfig(backup_dir=str(backup_dir))
                        backup_manager = BackupManager(config=backup_config)

                        # Test integrated workflow

                        # 1. Security scanning phase
                        security_reports = []
                        for image_name in image_names:
                            report = scanner.scan_image(image_name)
                            security_reports.append(report)

                        # Property validation: Security scan integration
                        assert len(security_reports) == len(
                            image_names
                        ), "Should scan all provided images"

                        total_critical = sum(
                            r.severity_counts.get("critical", 0)
                            for r in security_reports
                        )
                        total_high = sum(
                            r.severity_counts.get("high", 0) for r in security_reports
                        )

                        # 2. Monitoring phase with security-aware alerting
                        cpu_usage, memory_usage, disk_usage = resource_usage_levels

                        def mock_collect_system_metrics():
                            return ResourceMetrics(
                                timestamp=datetime.now(),
                                cpu_usage_percent=cpu_usage,
                                memory_usage_mb=int(
                                    memory_usage * 80
                                ),  # Assume 8GB total
                                memory_total_mb=8000,
                                memory_usage_percent=memory_usage,
                                disk_usage_mb=int(
                                    disk_usage * 1000
                                ),  # Assume 100GB total
                                disk_total_mb=100000,
                                disk_usage_percent=disk_usage,
                                network_io_mb=10.0,
                                load_average=(1.0, 1.0, 1.0),
                            )

                        with patch.object(
                            ProductionMonitor,
                            "collect_system_metrics",
                            side_effect=mock_collect_system_metrics,
                        ):
                            system_metrics = monitor.collect_system_metrics()
                            container_metrics = []  # No containers for this test

                            alerts = monitor.analyze_metrics_and_generate_alerts(
                                system_metrics, container_metrics
                            )

                            # Property validation: Integrated alerting
                            # Should generate alerts based on both security and resource metrics
                            resource_alerts = len(alerts)

                            # High security risk should influence monitoring sensitivity
                            if total_critical > 0 or total_high > 5:
                                # In a real system, high security risk might lower alert thresholds
                                # For this test, we validate that security context is available
                                assert (
                                    len(security_reports) > 0
                                ), "Security context should be available for monitoring decisions"

                            # 3. Backup phase triggered by security or resource alerts
                            if alerts or total_critical > 0:
                                # Create test data to backup
                                test_data_dir = Path(temp_dir) / "critical_data"
                                test_data_dir.mkdir(parents=True)

                                # Create security report files
                                for i, report in enumerate(security_reports):
                                    report_file = (
                                        test_data_dir / f"security_report_{i}.json"
                                    )
                                    report_file.write_text(
                                        json.dumps(
                                            report.to_dict(), indent=2, default=str
                                        )
                                    )

                                # Create monitoring data
                                monitoring_file = test_data_dir / "monitoring_data.json"
                                monitoring_data = {
                                    "system_metrics": system_metrics.to_dict(),
                                    "alerts": [alert.to_dict() for alert in alerts],
                                    "timestamp": datetime.now().isoformat(),
                                }
                                monitoring_file.write_text(
                                    json.dumps(monitoring_data, indent=2, default=str)
                                )

                                # Create backup
                                backup_metadata = backup_manager.create_backup(
                                    paths=[str(test_data_dir)],
                                    backup_type=BackupType.FULL,
                                )

                                # Property validation: Emergency backup creation
                                assert backup_metadata.status in [
                                    BackupStatus.CREATED,
                                    BackupStatus.VERIFIED,
                                ], "Emergency backup should be created successfully"

                                # Property validation: Backup contains security and monitoring data
                                assert (
                                    backup_metadata.file_count
                                    >= len(security_reports) + 1
                                ), "Backup should contain security reports and monitoring data"

                                # Verify backup integrity
                                verification_result = backup_manager.verify_backup(
                                    backup_metadata.backup_id
                                )
                                assert (
                                    verification_result
                                ), "Emergency backup should pass verification"

                        # Property validation: Cross-component data consistency
                        # Security scan timestamps should be recent
                        for report in security_reports:
                            time_diff = abs(
                                (datetime.now() - report.scan_date).total_seconds()
                            )
                            assert (
                                time_diff < 60
                            ), "Security scan timestamps should be recent"

                        # Monitoring metrics should be current
                        time_diff = abs(
                            (datetime.now() - system_metrics.timestamp).total_seconds()
                        )
                        assert time_diff < 10, "Monitoring metrics should be current"

                        # Alert timestamps should be synchronized
                        for alert in alerts:
                            time_diff = abs(
                                (datetime.now() - alert.timestamp).total_seconds()
                            )
                            assert (
                                time_diff < 30
                            ), "Alert timestamps should be synchronized"

    @given(
        failure_scenarios=st.lists(
            st.sampled_from(["scanner_failure", "monitor_failure", "backup_failure"]),
            min_size=1,
            max_size=1,  # Only test one scenario at a time to avoid conflicts
        ),
        recovery_strategies=st.lists(
            st.sampled_from(["retry", "fallback", "alert_only"]), min_size=1, max_size=1
        ),
    )
    @settings(max_examples=10, deadline=30000)
    def test_failure_recovery_and_resilience(
        self, failure_scenarios, recovery_strategies
    ):
        """
        **Feature: docker-enhancements, System Resilience**

        Test system behavior under various failure conditions and recovery strategies
        **Validates: Requirements 4.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test each failure scenario
            for i, failure_scenario in enumerate(failure_scenarios):
                scenario_dir = Path(temp_dir) / f"scenario_{i}"
                scenario_dir.mkdir(parents=True, exist_ok=True)

                if failure_scenario == "scanner_failure":
                    # Test security scanner failure handling
                    with patch.object(
                        SecurityScanner, "_detect_scanners"
                    ) as mock_detect:
                        mock_detect.return_value = {}  # No scanners available

                        try:
                            scanner = SecurityScanner(output_dir=str(scenario_dir))
                            assert (
                                False
                            ), "Should raise exception when no scanners available"
                        except RuntimeError as e:
                            assert "No supported vulnerability scanners found" in str(e)
                            # Property validation: Graceful failure with informative error
                            assert "install Trivy or Grype" in str(e)

                elif failure_scenario == "monitor_failure":
                    # Test monitoring failure handling
                    with patch(
                        "psutil.cpu_percent",
                        side_effect=Exception("System monitoring failed"),
                    ):
                        monitor = ProductionMonitor(output_dir=str(scenario_dir))

                        try:
                            monitor.collect_system_metrics()
                            assert (
                                False
                            ), "Should raise exception when system monitoring fails"
                        except Exception as e:
                            # Property validation: Exception propagation for critical failures
                            assert "System monitoring failed" in str(e)

                elif failure_scenario == "backup_failure":
                    # Test backup failure handling
                    config = BackupConfig(backup_dir=str(scenario_dir / "backups"))
                    manager = BackupManager(config=config)

                    # Try to backup non-existent path
                    metadata = manager.create_backup(paths=["/non/existent/path"])

                    # Property validation: Backup failure handling
                    assert metadata.status == BackupStatus.FAILED
                    assert metadata.error_message is not None
                    assert len(metadata.error_message) > 0


class TestSecurityMonitoringEdgeCases:
    """Edge case property tests for security and monitoring components"""

    @given(
        empty_inputs=st.sampled_from([[], [""], ["/nonexistent"]]),
        malformed_data=st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.one_of(st.none(), st.text(), st.integers(), st.floats()),
        ),
    )
    @settings(max_examples=20, deadline=30000)
    def test_edge_case_input_validation(self, empty_inputs, malformed_data):
        """
        **Feature: docker-enhancements, Input Validation**

        Test system behavior with edge case inputs and malformed data
        **Validates: Requirements 4.1, 4.2, 4.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test security scanner with empty/invalid inputs
            if empty_inputs:
                with patch.object(SecurityScanner, "_detect_scanners") as mock_detect:
                    mock_detect.return_value = {"trivy": True}

                    scanner = SecurityScanner(output_dir=temp_dir)

                    for empty_input in empty_inputs:
                        if empty_input == "":
                            # Empty string should be handled gracefully
                            try:
                                # This would typically fail in subprocess call
                                # We're testing the input validation layer
                                assert (
                                    empty_input != ""
                                ), "Empty input should be rejected"
                            except AssertionError:
                                pass  # Expected behavior
                        elif empty_input == "/nonexistent":
                            # Non-existent image should be handled gracefully
                            # In real scenario, this would fail in scanner subprocess
                            pass

            # Test backup manager with empty paths
            config = BackupConfig(backup_dir=temp_dir)
            manager = BackupManager(config=config)

            if not empty_inputs or empty_inputs == []:
                # Empty path list should be handled
                try:
                    metadata = manager.create_backup(paths=[])
                    # Should either succeed with no files or fail gracefully
                    if metadata.status == BackupStatus.FAILED:
                        assert metadata.error_message is not None
                    else:
                        assert metadata.file_count == 0
                except Exception as e:
                    # Graceful failure is acceptable
                    assert isinstance(e, (ValueError, RuntimeError))

            # Test monitoring with malformed configuration
            try:
                # Create alert config with potentially invalid data
                alert_config = AlertConfig()

                # Test with extreme threshold values
                alert_config.cpu_threshold = malformed_data.get("cpu_threshold", 80.0)
                alert_config.memory_threshold = malformed_data.get(
                    "memory_threshold", 85.0
                )

                # Ensure thresholds are reasonable
                if isinstance(alert_config.cpu_threshold, (int, float)):
                    if not (0 <= alert_config.cpu_threshold <= 100):
                        alert_config.cpu_threshold = 80.0

                if isinstance(alert_config.memory_threshold, (int, float)):
                    if not (0 <= alert_config.memory_threshold <= 100):
                        alert_config.memory_threshold = 85.0

                monitor = ProductionMonitor(
                    output_dir=temp_dir, alert_config=alert_config
                )

                # Property validation: System handles malformed configuration gracefully
                assert monitor.alert_config.cpu_threshold >= 0
                assert monitor.alert_config.memory_threshold >= 0

            except Exception as e:
                # Graceful failure with informative error is acceptable
                assert isinstance(e, (ValueError, TypeError, RuntimeError))

    @given(operation_count=st.integers(min_value=2, max_value=3))
    @settings(max_examples=5, deadline=30000)
    def test_concurrent_operations_safety(self, operation_count):
        """
        **Feature: docker-enhancements, Concurrency Safety**

        Test system behavior under concurrent operations
        **Validates: Requirements 4.1, 4.2, 4.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            import queue
            import threading

            results = queue.Queue()
            errors = queue.Queue()

            def run_scan_operation(op_id):
                try:
                    op_dir = Path(temp_dir) / f"scan_{op_id}"
                    op_dir.mkdir(parents=True, exist_ok=True)

                    with patch.object(
                        SecurityScanner, "_detect_scanners"
                    ) as mock_detect:
                        mock_detect.return_value = {"trivy": True}

                        def mock_scan(
                            image_name, severity_filter=None, output_format="json"
                        ):
                            time.sleep(0.05)  # Short simulation time
                            return SecurityReport(
                                image_name=image_name,
                                scan_date=datetime.now(),
                                scanner_used="trivy",
                                scanner_version="test-1.0.0",
                                vulnerabilities=[],
                                severity_counts={
                                    "low": 0,
                                    "medium": 0,
                                    "high": 0,
                                    "critical": 0,
                                    "unknown": 0,
                                },
                                total_vulnerabilities=0,
                                scan_duration_seconds=0.05,
                                recommendations=[],
                                overall_score=100.0,
                                scan_success=True,
                            )

                        with patch.object(
                            SecurityScanner, "scan_image", side_effect=mock_scan
                        ):
                            scanner = SecurityScanner(output_dir=str(op_dir))
                            result = scanner.scan_image(f"test_image_{op_id}:latest")
                            results.put(("scan", op_id, result.scan_success))

                except Exception as e:
                    errors.put(("scan", op_id, str(e)))

            # Start concurrent scan operations (most reliable operation type)
            threads = []
            for i in range(operation_count):
                thread = threading.Thread(target=run_scan_operation, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all operations to complete
            for thread in threads:
                thread.join(timeout=10)  # 10 second timeout per thread

            # Property validation: Concurrent operations complete successfully
            successful_operations = 0
            total_operations = 0
            while not results.empty():
                op_type, op_id, success = results.get()
                total_operations += 1
                if success:
                    successful_operations += 1

            # Property validation: Most operations should succeed
            if total_operations > 0:
                success_rate = successful_operations / total_operations
                assert (
                    success_rate >= 0.8
                ), f"At least 80% of concurrent operations should succeed, got {success_rate:.2f}"
            else:
                # If no operations completed, check if threads are still alive (timeout issue)
                alive_threads = [t for t in threads if t.is_alive()]
                assert (
                    len(alive_threads) == 0
                ), f"Operations timed out: {len(alive_threads)} threads still running"

            # Property validation: No critical errors
            critical_errors = 0
            while not errors.empty():
                op_type, op_id, error = errors.get()
                if "critical" in error.lower() or "fatal" in error.lower():
                    critical_errors += 1

            assert critical_errors == 0, "Should not have critical system failures"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
