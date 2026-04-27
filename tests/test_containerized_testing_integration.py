#!/usr/bin/env python3
"""
Integration tests for containerized testing system.
Tests the run_tests_in_container.py script functionality.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the containerized test runner
from scripts.run_tests_in_container import (
    ContainerizedTestRunner,
    TestReport,
    TestResult,
    TestSuite,
)


class TestContainerizedTestRunner(unittest.TestCase):
    """Test the containerized test runner functionality."""

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

    def test_runner_initialization(self):
        """Test that the runner initializes correctly."""
        self.assertIsInstance(self.runner, ContainerizedTestRunner)
        self.assertTrue(self.runner.reports_dir.exists())
        self.assertTrue(self.runner.coverage_dir.exists())
        self.assertTrue(self.runner.artifacts_dir.exists())
        self.assertIn("dev", self.runner.containers)
        self.assertIn("enhanced-dev", self.runner.containers)
        self.assertIn("production", self.runner.containers)

    @patch("subprocess.run")
    def test_check_docker_environment_success(self, mock_run):
        """Test successful Docker environment check."""
        # Mock successful Docker and Docker Compose commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Docker version 20.10.0"),
            MagicMock(returncode=0, stdout="docker-compose version 1.29.0"),
        ]

        result = self.runner.check_docker_environment()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    def test_check_docker_environment_failure(self, mock_run):
        """Test Docker environment check failure."""
        # Mock failed Docker command
        mock_run.return_value = MagicMock(returncode=1, stderr="Docker not found")

        result = self.runner.check_docker_environment()
        self.assertFalse(result)

    def test_parse_test_results_with_json(self):
        """Test parsing test results from JSON report."""
        # Create mock JSON report
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_example.py::test_function",
                    "outcome": "passed",
                    "duration": 0.5,
                    "call": {"longrepr": ""},
                },
                {
                    "nodeid": "tests/test_example.py::test_failure",
                    "outcome": "failed",
                    "duration": 0.3,
                    "call": {"longrepr": "AssertionError: Test failed"},
                },
            ]
        }

        json_report_path = self.runner.reports_dir / "report-test.json"
        with open(json_report_path, "w") as f:
            json.dump(json_data, f)

        # Mock subprocess result
        mock_result = MagicMock()
        mock_result.stdout = ""

        results = self.runner._parse_test_results("test", mock_result)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].test_name, "tests/test_example.py::test_function")
        self.assertEqual(results[0].status, "passed")
        self.assertEqual(results[0].duration, 0.5)
        self.assertEqual(results[1].test_name, "tests/test_example.py::test_failure")
        self.assertEqual(results[1].status, "failed")
        self.assertIsNotNone(results[1].error_message)

    def test_extract_coverage_percentage_from_xml(self):
        """Test extracting coverage percentage from XML report."""
        # Create mock XML coverage report
        xml_content = """<?xml version="1.0" ?>
        <coverage line-rate="0.85" branch-rate="0.75">
            <sources>
                <source>src</source>
            </sources>
        </coverage>"""

        xml_coverage_path = self.runner.coverage_dir / "coverage-test.xml"
        with open(xml_coverage_path, "w") as f:
            f.write(xml_content)

        coverage = self.runner._extract_coverage_percentage("test")
        self.assertEqual(coverage, 85.0)

    def test_collect_artifacts(self):
        """Test artifact collection."""
        # Create mock artifacts
        html_coverage_dir = self.runner.coverage_dir / "html-test"
        html_coverage_dir.mkdir(parents=True, exist_ok=True)

        xml_coverage_path = self.runner.coverage_dir / "coverage-test.xml"
        xml_coverage_path.touch()

        html_report_path = self.runner.reports_dir / "report-test.html"
        html_report_path.touch()

        artifacts = self.runner._collect_artifacts("test")

        self.assertGreater(len(artifacts), 0)
        self.assertTrue(any("html-test" in artifact for artifact in artifacts))
        self.assertTrue(any("coverage-test.xml" in artifact for artifact in artifacts))
        self.assertTrue(any("report-test.html" in artifact for artifact in artifacts))

    def test_generate_ci_integration_data(self):
        """Test CI integration data generation."""
        # Create mock test suites
        suites = [
            TestSuite(
                name="test-suite-1",
                container="enhanced-dev",
                start_time=None,
                end_time=None,
                total_tests=10,
                passed=8,
                failed=2,
                skipped=0,
                errors=0,
                coverage_percentage=85.0,
                duration=30.0,
                results=[],
                artifacts=["coverage-enhanced-dev.xml"],
            )
        ]

        ci_data = self.runner._generate_ci_integration_data(suites)

        self.assertIn("junit_xml_files", ci_data)
        self.assertIn("coverage_xml_files", ci_data)
        self.assertIn("github_actions", ci_data)
        self.assertIn("gitlab_ci", ci_data)
        self.assertIn("Total Tests", ci_data["github_actions"]["summary"])

    def test_environment_info_collection(self):
        """Test environment information collection."""
        env_info = self.runner._collect_environment_info()

        self.assertIn("timestamp", env_info)
        self.assertIn("workspace_root", env_info)
        self.assertIn("python_version", env_info)
        self.assertIn("platform", env_info)
        self.assertEqual(env_info["workspace_root"], str(self.runner.workspace_root))


class TestContainerizedTestingCLI(unittest.TestCase):
    """Test the command-line interface of the containerized testing script."""

    def setUp(self):
        """Set up test environment."""
        self.script_path = (
            Path(__file__).parent.parent / "scripts" / "run_tests_in_container.py"
        )
        self.assertTrue(
            self.script_path.exists(), f"Script not found: {self.script_path}"
        )

    def test_script_help(self):
        """Test that the script shows help correctly."""
        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("Comprehensive Containerized Testing", result.stdout)
            self.assertIn("--containers", result.stdout)
            self.assertIn("--build", result.stdout)

        except subprocess.TimeoutExpired:
            self.fail("Script help command timed out")
        except Exception as e:
            self.fail(f"Script help command failed: {e}")

    def test_script_syntax(self):
        """Test that the script has valid Python syntax."""
        try:
            # Try to compile the script
            with open(self.script_path, "r") as f:
                script_content = f.read()

            compile(script_content, str(self.script_path), "exec")

        except SyntaxError as e:
            self.fail(f"Script has syntax error: {e}")
        except Exception as e:
            self.fail(f"Script compilation failed: {e}")

    @patch("scripts.run_tests_in_container.ContainerizedTestRunner")
    def test_script_main_function(self, mock_runner_class):
        """Test the main function with mocked dependencies."""
        # Mock the runner and its methods
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Mock successful test execution
        mock_report = MagicMock()
        mock_report.summary = {
            "total_tests": 10,
            "passed": 10,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "success_rate": 100.0,
        }
        mock_report.overall_coverage = 85.0
        mock_runner.run_comprehensive_tests.return_value = mock_report

        # Import and test the main function
        from scripts.run_tests_in_container import main

        # Mock sys.argv for testing
        with patch(
            "sys.argv",
            ["run_tests_in_container.py", "--containers", "enhanced-dev", "--ci-mode"],
        ):
            try:
                main()
            except SystemExit as e:
                # Should exit with code 0 for successful tests
                self.assertEqual(e.code, 0)


class TestContainerizedTestingIntegration(unittest.TestCase):
    """Integration tests for the complete containerized testing workflow."""

    def setUp(self):
        """Set up integration test environment."""
        self.workspace_root = Path(__file__).parent.parent
        self.script_path = self.workspace_root / "scripts" / "run_tests_in_container.py"

    def test_docker_compose_files_exist(self):
        """Test that required Docker Compose files exist."""
        compose_files = [
            "docker-compose.dev.yml",
            "docker-compose.dev-enhanced.yml",
            "docker-compose.prod.yml",
        ]

        for compose_file in compose_files:
            file_path = self.workspace_root / compose_file
            self.assertTrue(
                file_path.exists(), f"Docker Compose file not found: {compose_file}"
            )

    def test_dockerfile_exists(self):
        """Test that required Dockerfiles exist."""
        dockerfiles = [
            "docker/Dockerfile.dev",
            "docker/Dockerfile.dev-enhanced",
            "docker/Dockerfile.prod",
        ]

        for dockerfile in dockerfiles:
            file_path = self.workspace_root / dockerfile
            self.assertTrue(file_path.exists(), f"Dockerfile not found: {dockerfile}")

    def test_test_directories_exist(self):
        """Test that test directories and files exist."""
        test_paths = [
            "tests",
            "tests/__init__.py",
            "tests/quick_test.py",
            "tests/validation_tests.py",
        ]

        for test_path in test_paths:
            path = self.workspace_root / test_path
            self.assertTrue(path.exists(), f"Test path not found: {test_path}")

    def test_pytest_configuration(self):
        """Test that pytest configuration is properly set up."""
        pyproject_path = self.workspace_root / "pyproject.toml"
        self.assertTrue(pyproject_path.exists(), "pyproject.toml not found")

        # Check if pytest configuration exists
        with open(pyproject_path, "r") as f:
            content = f.read()
            self.assertIn("[tool.pytest.ini_options]", content)
            self.assertIn("testpaths", content)


def run_integration_tests():
    """Run all integration tests for containerized testing."""
    print("🧪 Running Containerized Testing Integration Tests")
    print("=" * 60)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestContainerizedTestRunner))
    suite.addTests(loader.loadTestsFromTestCase(TestContainerizedTestingCLI))
    suite.addTests(loader.loadTestsFromTestCase(TestContainerizedTestingIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("Integration Test Summary")
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
        print("\n✅ All integration tests passed!")
    else:
        print(f"\n❌ {len(result.failures) + len(result.errors)} test(s) failed")

    return success


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
