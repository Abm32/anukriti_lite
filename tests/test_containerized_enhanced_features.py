#!/usr/bin/env python3
"""
Tests for enhanced containerized testing features.
Tests the new CI integration, reporting, and aggregation features.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_tests_in_container import (
    ContainerizedTestRunner,
    TestReport,
    TestResultAggregator,
    TestSuite,
)


class TestEnhancedContainerizedFeatures(unittest.TestCase):
    """Test the enhanced containerized testing features."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.runner = ContainerizedTestRunner(workspace_root=self.temp_dir)

        # Create required directories
        self.runner.reports_dir.mkdir(parents=True, exist_ok=True)
        self.runner.coverage_dir.mkdir(parents=True, exist_ok=True)
        self.runner.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_junit_xml_generation(self):
        """Test JUnit XML report generation."""
        # Create mock test report
        mock_report = self._create_mock_report()

        # Generate JUnit XML
        self.runner._save_junit_xml(mock_report)

        # Check if file was created
        junit_file = self.runner.reports_dir / f"{self.runner.execution_id}-junit.xml"
        self.assertTrue(junit_file.exists())

        # Check XML content
        with open(junit_file, "r") as f:
            content = f.read()
            self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', content)
            self.assertIn("<testsuites>", content)
            self.assertIn("</testsuites>", content)

    def test_cobertura_xml_generation(self):
        """Test Cobertura XML coverage report generation."""
        # Create mock test report
        mock_report = self._create_mock_report()

        # Generate Cobertura XML
        self.runner._save_cobertura_xml(mock_report)

        # Check if file was created
        cobertura_file = (
            self.runner.reports_dir / f"{self.runner.execution_id}-cobertura.xml"
        )
        self.assertTrue(cobertura_file.exists())

        # Check XML content
        with open(cobertura_file, "r") as f:
            content = f.read()
            self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', content)
            self.assertIn("<coverage", content)
            self.assertIn("line-rate=", content)

    def test_teamcity_messages_generation(self):
        """Test TeamCity service messages generation."""
        # Create mock test report
        mock_report = self._create_mock_report()

        # Generate TeamCity messages
        self.runner._save_teamcity_messages(mock_report)

        # Check if file was created
        teamcity_file = (
            self.runner.reports_dir / f"{self.runner.execution_id}-teamcity.txt"
        )
        self.assertTrue(teamcity_file.exists())

        # Check content
        with open(teamcity_file, "r") as f:
            content = f.read()
            self.assertIn("##teamcity[", content)

    def test_azure_devops_format_generation(self):
        """Test Azure DevOps format generation."""
        # Create mock test report
        mock_report = self._create_mock_report()

        # Generate Azure DevOps format
        self.runner._save_azure_devops_format(mock_report)

        # Check if file was created
        azure_file = self.runner.reports_dir / f"{self.runner.execution_id}-azure.json"
        self.assertTrue(azure_file.exists())

        # Check JSON content
        with open(azure_file, "r") as f:
            data = json.load(f)
            self.assertIn("version", data)
            self.assertIn("testResults", data)
            self.assertIn("coverage", data)

    def test_result_aggregator_initialization(self):
        """Test TestResultAggregator initialization."""
        aggregator = TestResultAggregator(self.runner.reports_dir)

        self.assertEqual(aggregator.reports_dir, self.runner.reports_dir)
        self.assertTrue(aggregator.history_file.name == "test_history.json")

    def test_result_aggregator_add_report(self):
        """Test adding a report to the aggregator."""
        aggregator = TestResultAggregator(self.runner.reports_dir)
        mock_report = self._create_mock_report()

        # Add report
        aggregator.add_report(mock_report)

        # Check history file was created
        self.assertTrue(aggregator.history_file.exists())

        # Check history content
        history = aggregator.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["execution_id"], mock_report.execution_id)

    def test_result_aggregator_trend_analysis(self):
        """Test trend analysis generation."""
        aggregator = TestResultAggregator(self.runner.reports_dir)

        # Add multiple reports
        for i in range(5):
            mock_report = self._create_mock_report(f"test-run-{i}")
            aggregator.add_report(mock_report)

        # Generate trends
        trends = aggregator.generate_trend_report()

        self.assertIn("total_runs", trends)
        self.assertIn("recent_runs", trends)
        self.assertIn("average_success_rate", trends)
        self.assertIn("average_coverage", trends)
        self.assertEqual(trends["total_runs"], 5)

    def test_enhanced_ci_integration_data(self):
        """Test enhanced CI integration data generation."""
        mock_report = self._create_mock_report()

        ci_data = self.runner._generate_ci_integration_data(mock_report.suites)

        # Check all CI formats are included
        self.assertIn("junit_xml_files", ci_data)
        self.assertIn("coverage_xml_files", ci_data)
        self.assertIn("github_actions", ci_data)
        self.assertIn("gitlab_ci", ci_data)

        # Check GitHub Actions summary
        self.assertIn("summary", ci_data["github_actions"])
        self.assertIn("Test Results Summary", ci_data["github_actions"]["summary"])

    def _create_mock_report(self, execution_id=None):
        """Create a mock test report for testing."""
        from datetime import datetime, timezone

        from scripts.run_tests_in_container import TestResult

        if execution_id is None:
            execution_id = self.runner.execution_id

        # Create mock test results
        results = [
            TestResult(
                test_name="test_example_1",
                status="passed",
                duration=0.1,
                output="Test passed",
                coverage_percentage=85.0,
            ),
            TestResult(
                test_name="test_example_2",
                status="failed",
                duration=0.05,
                output="Test failed",
                error_message="Assertion error",
            ),
        ]

        # Create mock test suite
        suite = TestSuite(
            name="SynthaTrial-enhanced-dev",
            container="enhanced-dev",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            total_tests=2,
            passed=1,
            failed=1,
            skipped=0,
            errors=0,
            coverage_percentage=85.0,
            duration=0.15,
            results=results,
            artifacts=[],
        )

        # Create mock test report
        return TestReport(
            execution_id=execution_id,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            total_duration=0.15,
            environment={"git_commit": "abc123", "docker_version": "20.10.0"},
            suites=[suite],
            overall_coverage=85.0,
            summary={
                "total_tests": 2,
                "passed": 1,
                "failed": 1,
                "skipped": 0,
                "errors": 0,
                "success_rate": 50.0,
                "containers_tested": 1,
                "containers_requested": 1,
            },
            artifacts=[],
            ci_integration={},
        )


def run_enhanced_feature_tests():
    """Run all enhanced feature tests."""
    print("🧪 Running Enhanced Containerized Testing Feature Tests")
    print("=" * 60)

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEnhancedContainerizedFeatures)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("Enhanced Feature Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    success = len(result.failures) == 0 and len(result.errors) == 0

    if success:
        print("\n✅ All enhanced feature tests passed!")
    else:
        print(f"\n❌ {len(result.failures) + len(result.errors)} test(s) failed")

    return success


if __name__ == "__main__":
    success = run_enhanced_feature_tests()
    sys.exit(0 if success else 1)
