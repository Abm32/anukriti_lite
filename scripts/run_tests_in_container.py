#!/usr/bin/env python3
"""
Comprehensive Containerized Testing with Reporting for SynthaTrial
================================================================

This script provides comprehensive test execution within Docker containers with
detailed reporting, coverage metrics, and CI/CD integration capabilities.

Features:
- Multi-container test execution (dev, enhanced-dev, production)
- Comprehensive coverage reporting (HTML, XML, JSON)
- Test result aggregation and analysis
- Performance benchmarking and profiling
- CI/CD integration with multiple output formats
- Property-based test execution and reporting
- Security and quality scanning integration
- Parallel test execution with resource monitoring
- Detailed error reporting and debugging information
- Test artifact management and archival

Version: 0.2 Beta
Author: SynthaTrial Team
"""

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TestResult:
    """Test execution result with comprehensive metrics."""

    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    output: str
    error_message: Optional[str] = None
    coverage_percentage: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


@dataclass
class TestSuite:
    """Test suite execution results."""

    name: str
    container: str
    start_time: datetime
    end_time: datetime
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    coverage_percentage: float
    duration: float
    results: List[TestResult]
    artifacts: List[str]


@dataclass
class TestReport:
    """Comprehensive test execution report."""

    execution_id: str
    start_time: datetime
    end_time: datetime
    total_duration: float
    environment: Dict[str, Any]
    suites: List[TestSuite]
    overall_coverage: float
    summary: Dict[str, Any]
    artifacts: List[str]
    ci_integration: Dict[str, Any]


class ContainerizedTestRunner:
    """Comprehensive containerized test execution and reporting system."""

    def __init__(self, workspace_root: str = "."):
        """Initialize the test runner."""
        self.workspace_root = Path(workspace_root).resolve()
        self.reports_dir = self.workspace_root / "tests" / "reports"
        self.coverage_dir = self.workspace_root / "coverage"
        self.artifacts_dir = self.workspace_root / "test-artifacts"

        # Create directories
        for directory in [self.reports_dir, self.coverage_dir, self.artifacts_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Test configuration
        self.containers = {
            "dev": {
                "compose_file": "docker-compose.dev.yml",
                "service": "synthatrial-dev",
                "test_command": ["conda", "run", "-n", "synthatrial", "pytest"],
            },
            "enhanced-dev": {
                "compose_file": "docker-compose.dev-enhanced.yml",
                "service": "synthatrial-dev-enhanced",
                "test_command": ["conda", "run", "-n", "synthatrial", "pytest"],
            },
            "production": {
                "compose_file": "docker-compose.prod.yml",
                "service": "synthatrial",
                "test_command": ["conda", "run", "-n", "synthatrial", "pytest"],
            },
        }

        # Generate unique execution ID
        self.execution_id = f"test-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def check_docker_environment(self) -> bool:
        """Check if Docker and Docker Compose are available."""
        try:
            # Check Docker
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                print("❌ Docker is not available")
                return False

            # Check Docker Compose
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                print("❌ Docker Compose is not available")
                return False

            print("✅ Docker environment is ready")
            return True

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"❌ Docker environment check failed: {e}")
            return False

    def build_container(self, container_name: str) -> bool:
        """Build the specified container."""
        if container_name not in self.containers:
            print(f"❌ Unknown container: {container_name}")
            return False

        config = self.containers[container_name]
        compose_file = config["compose_file"]

        print(f"🔨 Building container: {container_name}")

        try:
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "build"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
            )

            if result.returncode == 0:
                print(f"✅ Container {container_name} built successfully")
                return True
            else:
                print(f"❌ Failed to build container {container_name}")
                print(f"Error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"❌ Container build timeout for {container_name}")
            return False
        except Exception as e:
            print(f"❌ Container build error for {container_name}: {e}")
            return False

    def start_container(self, container_name: str) -> bool:
        """Start the specified container."""
        if container_name not in self.containers:
            print(f"❌ Unknown container: {container_name}")
            return False

        config = self.containers[container_name]
        compose_file = config["compose_file"]
        service = config["service"]

        print(f"🚀 Starting container: {container_name}")

        try:
            # Start the container
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d", service],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                print(f"❌ Failed to start container {container_name}")
                print(f"Error: {result.stderr}")
                return False

            # Wait for container to be ready
            print(f"⏳ Waiting for container {container_name} to be ready...")
            time.sleep(10)

            # Check if container is running
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "ps", service],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if "Up" in result.stdout:
                print(f"✅ Container {container_name} is running")
                return True
            else:
                print(f"❌ Container {container_name} is not running properly")
                return False

        except subprocess.TimeoutExpired:
            print(f"❌ Container start timeout for {container_name}")
            return False
        except Exception as e:
            print(f"❌ Container start error for {container_name}: {e}")
            return False

    def stop_container(self, container_name: str) -> bool:
        """Stop the specified container."""
        if container_name not in self.containers:
            return True  # Nothing to stop

        config = self.containers[container_name]
        compose_file = config["compose_file"]

        print(f"🛑 Stopping container: {container_name}")

        try:
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "down"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                print(f"✅ Container {container_name} stopped")
                return True
            else:
                print(f"⚠️ Warning: Failed to stop container {container_name}")
                print(f"Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"⚠️ Warning: Container stop error for {container_name}: {e}")
            return False

    def execute_tests_in_container(
        self,
        container_name: str,
        test_patterns: List[str] = None,
        pytest_args: List[str] = None,
    ) -> TestSuite:
        """Execute tests in the specified container with comprehensive reporting."""

        if container_name not in self.containers:
            raise ValueError(f"Unknown container: {container_name}")

        config = self.containers[container_name]
        compose_file = config["compose_file"]
        service = config["service"]
        base_command = config["test_command"]

        # Prepare test command
        test_command = base_command.copy()

        # Add comprehensive pytest arguments
        test_args = [
            # Coverage reporting
            "--cov=src",
            f"--cov-report=html:{self.coverage_dir}/html-{container_name}",
            f"--cov-report=xml:{self.coverage_dir}/coverage-{container_name}.xml",
            "--cov-report=term-missing",
            # Test reporting
            f"--html={self.reports_dir}/report-{container_name}.html",
            "--self-contained-html",
            f"--json-report",
            f"--json-report-file={self.reports_dir}/report-{container_name}.json",
            # Performance and benchmarking (only if pytest-benchmark is available)
            f"--benchmark-json={self.reports_dir}/benchmark-{container_name}.json",
            "--benchmark-skip",  # Skip benchmarks by default, enable with --benchmark-only
            # Verbose output
            "-v",
            "--tb=short",
            # Timeout protection
            "--timeout=300",
            # Parallel execution (if supported)
            "-n",
            "auto",
            # Property-based testing configuration
            "--hypothesis-show-statistics",
            "--hypothesis-verbosity=verbose",
        ]

        # Add custom pytest arguments
        if pytest_args:
            test_args.extend(pytest_args)

        # Add test patterns
        if test_patterns:
            test_args.extend(test_patterns)
        else:
            test_args.append("tests/")

        test_command.extend(test_args)

        print(f"🧪 Executing tests in container: {container_name}")
        print(
            f"Command: {' '.join(test_command[-10:])}"
        )  # Show last 10 args to avoid clutter

        start_time = datetime.now(timezone.utc)

        try:
            # Check container health before running tests
            health_check = self._check_container_health(container_name)
            if not health_check:
                print(f"⚠️ Warning: Container {container_name} health check failed")

            # Execute tests in container
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "exec", "-T", service]
                + test_command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout
            )

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Parse test results
            test_results = self._parse_test_results(container_name, result)

            # Calculate coverage
            coverage_percentage = self._extract_coverage_percentage(container_name)

            # Get resource usage if available
            resource_usage = self._get_container_resource_usage(container_name)

            # Create test suite result
            suite = TestSuite(
                name=f"SynthaTrial-{container_name}",
                container=container_name,
                start_time=start_time,
                end_time=end_time,
                total_tests=len(test_results),
                passed=sum(1 for r in test_results if r.status == "passed"),
                failed=sum(1 for r in test_results if r.status == "failed"),
                skipped=sum(1 for r in test_results if r.status == "skipped"),
                errors=sum(1 for r in test_results if r.status == "error"),
                coverage_percentage=coverage_percentage,
                duration=duration,
                results=test_results,
                artifacts=self._collect_artifacts(container_name),
            )

            print(f"✅ Tests completed in container: {container_name}")
            print(f"   Duration: {duration:.2f}s")
            print(
                f"   Tests: {suite.total_tests} total, {suite.passed} passed, {suite.failed} failed"
            )
            print(f"   Coverage: {coverage_percentage:.1f}%")
            if resource_usage:
                print(
                    f"   Resources: {resource_usage.get('memory', 'N/A')} MB memory, {resource_usage.get('cpu', 'N/A')}% CPU"
                )

            return suite

        except subprocess.TimeoutExpired:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            print(f"❌ Test execution timeout in container: {container_name}")

            return TestSuite(
                name=f"SynthaTrial-{container_name}",
                container=container_name,
                start_time=start_time,
                end_time=end_time,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                coverage_percentage=0.0,
                duration=duration,
                results=[
                    TestResult(
                        test_name="timeout",
                        status="error",
                        duration=duration,
                        output="Test execution timeout",
                        error_message="Test execution exceeded 30 minute timeout",
                    )
                ],
                artifacts=[],
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            print(f"❌ Test execution error in container: {container_name}: {e}")

            return TestSuite(
                name=f"SynthaTrial-{container_name}",
                container=container_name,
                start_time=start_time,
                end_time=end_time,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                coverage_percentage=0.0,
                duration=duration,
                results=[
                    TestResult(
                        test_name="execution_error",
                        status="error",
                        duration=duration,
                        output=str(e),
                        error_message=str(e),
                    )
                ],
                artifacts=[],
            )

    def _check_container_health(self, container_name: str) -> bool:
        """Check if the container is healthy and ready for testing."""
        if container_name not in self.containers:
            return False

        config = self.containers[container_name]
        compose_file = config["compose_file"]
        service = config["service"]

        try:
            # Check if container is running
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "ps", "-q", service],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return False

            container_id = result.stdout.strip()

            # Check container health status
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_id,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                health_status = result.stdout.strip()
                return health_status in [
                    "healthy",
                    "",
                ]  # Empty means no health check defined

            return True  # If no health check, assume healthy

        except Exception as e:
            print(f"⚠️ Health check failed for {container_name}: {e}")
            return False

    def _get_container_resource_usage(
        self, container_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get container resource usage statistics."""
        if container_name not in self.containers:
            return None

        config = self.containers[container_name]
        compose_file = config["compose_file"]
        service = config["service"]

        try:
            # Get container ID
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "ps", "-q", service],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            container_id = result.stdout.strip()

            # Get resource stats
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "table {{.MemUsage}}\t{{.CPUPerc}}",
                    container_id,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:  # Header + data
                    data_line = lines[1]
                    parts = data_line.split("\t")
                    if len(parts) >= 2:
                        memory_usage = parts[0].strip()
                        cpu_usage = parts[1].strip()

                        return {
                            "memory": memory_usage,
                            "cpu": cpu_usage,
                            "container_id": container_id,
                        }

            return None

        except Exception as e:
            print(f"⚠️ Resource monitoring failed for {container_name}: {e}")
            return None

    def _parse_test_results(
        self, container_name: str, result: subprocess.CompletedProcess
    ) -> List[TestResult]:
        """Parse test results from pytest output."""
        test_results = []

        # Try to parse JSON report first
        json_report_path = self.reports_dir / f"report-{container_name}.json"
        if json_report_path.exists():
            try:
                with open(json_report_path, "r") as f:
                    json_data = json.load(f)

                for test in json_data.get("tests", []):
                    test_results.append(
                        TestResult(
                            test_name=test.get("nodeid", "unknown"),
                            status=test.get("outcome", "unknown"),
                            duration=test.get("duration", 0.0),
                            output=test.get("call", {}).get("longrepr", ""),
                            error_message=(
                                test.get("call", {}).get("longrepr", None)
                                if test.get("outcome") in ["failed", "error"]
                                else None
                            ),
                        )
                    )

                return test_results

            except Exception as e:
                print(f"⚠️ Warning: Could not parse JSON report: {e}")

        # Fallback to parsing stdout/stderr
        output_lines = result.stdout.split("\n") if result.stdout else []

        # Simple parsing of pytest output
        for line in output_lines:
            if "::" in line and any(
                status in line for status in ["PASSED", "FAILED", "SKIPPED", "ERROR"]
            ):
                parts = line.split()
                if len(parts) >= 2:
                    test_name = parts[0]
                    status = (
                        "passed"
                        if "PASSED" in line
                        else (
                            "failed"
                            if "FAILED" in line
                            else "skipped"
                            if "SKIPPED" in line
                            else "error"
                        )
                    )

                    test_results.append(
                        TestResult(
                            test_name=test_name,
                            status=status,
                            duration=0.0,
                            output=line,
                            error_message=(
                                line if status in ["failed", "error"] else None
                            ),
                        )
                    )

        return test_results

    def _extract_coverage_percentage(self, container_name: str) -> float:
        """Extract coverage percentage from coverage reports."""
        # Try XML coverage report
        xml_coverage_path = self.coverage_dir / f"coverage-{container_name}.xml"
        if xml_coverage_path.exists():
            try:
                tree = ET.parse(xml_coverage_path)
                root = tree.getroot()

                # Try different XML structures for coverage
                # Structure 1: <coverage line-rate="0.85">
                if root.tag == "coverage":
                    line_rate = root.get("line-rate", "0")
                    return float(line_rate) * 100

                # Structure 2: Find coverage element
                coverage_elem = root.find(".//coverage")
                if coverage_elem is not None:
                    line_rate = coverage_elem.get("line-rate", "0")
                    return float(line_rate) * 100

                # Structure 3: Cobertura format
                if root.tag == "cobertura":
                    line_rate = root.get("line-rate", "0")
                    return float(line_rate) * 100

            except Exception as e:
                print(f"⚠️ Warning: Could not parse XML coverage: {e}")

        # Try JSON report for coverage info
        json_report_path = self.reports_dir / f"report-{container_name}.json"
        if json_report_path.exists():
            try:
                with open(json_report_path, "r") as f:
                    json_data = json.load(f)

                coverage_info = json_data.get("coverage", {})
                if coverage_info:
                    return coverage_info.get("percent_covered", 0.0)

            except Exception as e:
                print(f"⚠️ Warning: Could not extract coverage from JSON: {e}")

        return 0.0

    def _collect_artifacts(self, container_name: str) -> List[str]:
        """Collect test artifacts for the container."""
        artifacts = []

        # Coverage reports
        html_coverage = self.coverage_dir / f"html-{container_name}"
        if html_coverage.exists():
            artifacts.append(str(html_coverage))

        xml_coverage = self.coverage_dir / f"coverage-{container_name}.xml"
        if xml_coverage.exists():
            artifacts.append(str(xml_coverage))

        # Test reports
        html_report = self.reports_dir / f"report-{container_name}.html"
        if html_report.exists():
            artifacts.append(str(html_report))

        json_report = self.reports_dir / f"report-{container_name}.json"
        if json_report.exists():
            artifacts.append(str(json_report))

        benchmark_report = self.reports_dir / f"benchmark-{container_name}.json"
        if benchmark_report.exists():
            artifacts.append(str(benchmark_report))

        return artifacts

    def run_comprehensive_tests(
        self,
        containers: List[str] = None,
        build_containers: bool = True,
        parallel: bool = False,
        test_patterns: List[str] = None,
        pytest_args: List[str] = None,
    ) -> TestReport:
        """Run comprehensive tests across multiple containers."""

        if containers is None:
            containers = ["enhanced-dev"]  # Default to enhanced development

        # Validate containers
        invalid_containers = [c for c in containers if c not in self.containers]
        if invalid_containers:
            raise ValueError(f"Invalid containers: {invalid_containers}")

        print(f"🚀 Starting comprehensive test execution")
        print(f"Execution ID: {self.execution_id}")
        print(f"Containers: {', '.join(containers)}")
        print(f"Parallel execution: {parallel}")

        start_time = datetime.now(timezone.utc)

        # Check Docker environment
        if not self.check_docker_environment():
            raise RuntimeError("Docker environment is not ready")

        suites = []

        try:
            if parallel:
                # Parallel execution using threading
                print("🔄 Running tests in parallel across containers")
                suites = self._run_tests_parallel(
                    containers, build_containers, test_patterns, pytest_args
                )
            else:
                # Sequential execution
                suites = self._run_tests_sequential(
                    containers, build_containers, test_patterns, pytest_args
                )

            end_time = datetime.now(timezone.utc)
            total_duration = (end_time - start_time).total_seconds()

            # Calculate overall metrics
            total_tests = sum(suite.total_tests for suite in suites)
            total_passed = sum(suite.passed for suite in suites)
            total_failed = sum(suite.failed for suite in suites)
            total_skipped = sum(suite.skipped for suite in suites)
            total_errors = sum(suite.errors for suite in suites)

            # Calculate weighted average coverage
            if suites:
                overall_coverage = sum(
                    suite.coverage_percentage * suite.total_tests
                    for suite in suites
                    if suite.total_tests > 0
                ) / max(total_tests, 1)
            else:
                overall_coverage = 0.0

            # Collect all artifacts
            all_artifacts = []
            for suite in suites:
                all_artifacts.extend(suite.artifacts)

            # Create comprehensive report
            report = TestReport(
                execution_id=self.execution_id,
                start_time=start_time,
                end_time=end_time,
                total_duration=total_duration,
                environment=self._collect_environment_info(),
                suites=suites,
                overall_coverage=overall_coverage,
                summary={
                    "total_tests": total_tests,
                    "passed": total_passed,
                    "failed": total_failed,
                    "skipped": total_skipped,
                    "errors": total_errors,
                    "success_rate": (total_passed / max(total_tests, 1)) * 100,
                    "containers_tested": len(suites),
                    "containers_requested": len(containers),
                },
                artifacts=all_artifacts,
                ci_integration=self._generate_ci_integration_data(suites),
            )

            # Save comprehensive report
            self._save_report(report)

            # Add to test history for trend analysis
            aggregator = TestResultAggregator(self.reports_dir)
            aggregator.add_report(report)

            # Print summary
            self._print_summary(report)

            return report

        except Exception as e:
            print(f"❌ Comprehensive test execution failed: {e}")
            raise

    def _run_tests_sequential(
        self,
        containers: List[str],
        build_containers: bool,
        test_patterns: List[str],
        pytest_args: List[str],
    ) -> List[TestSuite]:
        """Run tests sequentially across containers."""
        suites = []

        for container_name in containers:
            print(f"\n{'='*60}")
            print(f"Testing container: {container_name}")
            print(f"{'='*60}")

            # Build container if requested
            if build_containers:
                if not self.build_container(container_name):
                    print(f"❌ Skipping {container_name} due to build failure")
                    continue

            # Start container
            if not self.start_container(container_name):
                print(f"❌ Skipping {container_name} due to start failure")
                continue

            try:
                # Execute tests
                suite = self.execute_tests_in_container(
                    container_name, test_patterns=test_patterns, pytest_args=pytest_args
                )
                suites.append(suite)

            finally:
                # Always try to stop container
                self.stop_container(container_name)

        return suites

    def _run_tests_parallel(
        self,
        containers: List[str],
        build_containers: bool,
        test_patterns: List[str],
        pytest_args: List[str],
    ) -> List[TestSuite]:
        """Run tests in parallel across containers using threading."""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        suites = []
        suites_lock = threading.Lock()

        def run_container_tests(container_name: str) -> Optional[TestSuite]:
            """Run tests for a single container."""
            try:
                print(f"\n🔄 [Parallel] Starting tests for container: {container_name}")

                # Build container if requested
                if build_containers:
                    if not self.build_container(container_name):
                        print(
                            f"❌ [Parallel] Skipping {container_name} due to build failure"
                        )
                        return None

                # Start container
                if not self.start_container(container_name):
                    print(
                        f"❌ [Parallel] Skipping {container_name} due to start failure"
                    )
                    return None

                try:
                    # Execute tests
                    suite = self.execute_tests_in_container(
                        container_name,
                        test_patterns=test_patterns,
                        pytest_args=pytest_args,
                    )
                    print(
                        f"✅ [Parallel] Completed tests for container: {container_name}"
                    )
                    return suite

                finally:
                    # Always try to stop container
                    self.stop_container(container_name)

            except Exception as e:
                print(f"❌ [Parallel] Error in container {container_name}: {e}")
                return None

        # Run tests in parallel with a reasonable thread limit
        max_workers = min(len(containers), 3)  # Limit to 3 parallel containers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all container test jobs
            future_to_container = {
                executor.submit(run_container_tests, container): container
                for container in containers
            }

            # Collect results as they complete
            for future in as_completed(future_to_container):
                container_name = future_to_container[future]
                try:
                    suite = future.result()
                    if suite is not None:
                        with suites_lock:
                            suites.append(suite)
                except Exception as e:
                    print(f"❌ [Parallel] Exception in container {container_name}: {e}")

        return suites

    def _collect_environment_info(self) -> Dict[str, Any]:
        """Collect environment information for the report."""
        env_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(self.workspace_root),
            "python_version": sys.version,
            "platform": sys.platform,
        }

        # Docker version
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                env_info["docker_version"] = result.stdout.strip()
        except:
            env_info["docker_version"] = "unknown"

        # Docker Compose version
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                env_info["docker_compose_version"] = result.stdout.strip()
        except:
            env_info["docker_compose_version"] = "unknown"

        # Git information
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.workspace_root,
            )
            if result.returncode == 0:
                env_info["git_commit"] = result.stdout.strip()
        except:
            env_info["git_commit"] = "unknown"

        return env_info

    def _generate_ci_integration_data(self, suites: List[TestSuite]) -> Dict[str, Any]:
        """Generate CI/CD integration data."""
        ci_data = {
            "junit_xml_files": [],
            "coverage_xml_files": [],
            "github_actions": {"summary": "", "annotations": []},
            "gitlab_ci": {
                "reports": {
                    "junit": [],
                    "coverage_report": {"coverage_format": "cobertura", "path": []},
                }
            },
        }

        # Collect XML files for CI integration
        for suite in suites:
            for artifact in suite.artifacts:
                if artifact.endswith(".xml") and "coverage" in artifact:
                    ci_data["coverage_xml_files"].append(artifact)
                    ci_data["gitlab_ci"]["reports"]["coverage_report"]["path"].append(
                        artifact
                    )

        # Generate GitHub Actions summary
        total_tests = sum(suite.total_tests for suite in suites)
        total_passed = sum(suite.passed for suite in suites)
        total_failed = sum(suite.failed for suite in suites)

        ci_data["github_actions"][
            "summary"
        ] = f"""
## Test Results Summary

- **Total Tests**: {total_tests}
- **Passed**: {total_passed} ✅
- **Failed**: {total_failed} ❌
- **Success Rate**: {(total_passed / max(total_tests, 1)) * 100:.1f}%

### Container Results
""" + "\n".join(
            [
                f"- **{suite.container}**: {suite.passed}/{suite.total_tests} passed ({suite.coverage_percentage:.1f}% coverage)"
                for suite in suites
            ]
        )

        return ci_data

    def _save_report(self, report: TestReport) -> None:
        """Save the comprehensive test report."""
        # Save JSON report
        json_report_path = self.reports_dir / f"{self.execution_id}-comprehensive.json"
        with open(json_report_path, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)

        print(f"📊 Comprehensive report saved: {json_report_path}")

        # Save CI-friendly formats
        self._save_ci_reports(report)

    def _save_ci_reports(self, report: TestReport) -> None:
        """Save CI-friendly report formats."""

        # GitHub Actions summary
        github_summary_path = (
            self.reports_dir / f"{self.execution_id}-github-summary.md"
        )
        with open(github_summary_path, "w") as f:
            f.write(report.ci_integration["github_actions"]["summary"])

        # Simple status file for CI
        status_path = self.reports_dir / f"{self.execution_id}-status.txt"
        with open(status_path, "w") as f:
            total_failed = report.summary["failed"] + report.summary["errors"]
            status = "PASSED" if total_failed == 0 else "FAILED"
            f.write(f"{status}\n")
            f.write(f"Tests: {report.summary['total_tests']}\n")
            f.write(f"Passed: {report.summary['passed']}\n")
            f.write(f"Failed: {total_failed}\n")
            f.write(f"Coverage: {report.overall_coverage:.1f}%\n")

        # JUnit XML format for CI systems
        self._save_junit_xml(report)

        # Cobertura coverage XML for GitLab CI
        self._save_cobertura_xml(report)

        # TeamCity service messages
        self._save_teamcity_messages(report)

        # Azure DevOps format
        self._save_azure_devops_format(report)

    def _save_junit_xml(self, report: TestReport) -> None:
        """Save JUnit XML format for CI integration."""
        junit_path = self.reports_dir / f"{self.execution_id}-junit.xml"

        # Create JUnit XML structure
        xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_content.append("<testsuites>")

        for suite in report.suites:
            xml_content.append(
                f'  <testsuite name="{suite.name}" tests="{suite.total_tests}" '
                f'failures="{suite.failed}" errors="{suite.errors}" '
                f'skipped="{suite.skipped}" time="{suite.duration:.3f}">'
            )

            for result in suite.results:
                xml_content.append(
                    f'    <testcase name="{result.test_name}" '
                    f'time="{result.duration:.3f}">'
                )

                if result.status == "failed":
                    xml_content.append(
                        f'      <failure message="{result.error_message or "Test failed"}">'
                    )
                    xml_content.append(f"        {result.output}")
                    xml_content.append("      </failure>")
                elif result.status == "error":
                    xml_content.append(
                        f'      <error message="{result.error_message or "Test error"}">'
                    )
                    xml_content.append(f"        {result.output}")
                    xml_content.append("      </error>")
                elif result.status == "skipped":
                    xml_content.append("      <skipped/>")

                xml_content.append("    </testcase>")

            xml_content.append("  </testsuite>")

        xml_content.append("</testsuites>")

        with open(junit_path, "w") as f:
            f.write("\n".join(xml_content))

        print(f"📊 JUnit XML report saved: {junit_path}")

    def _save_cobertura_xml(self, report: TestReport) -> None:
        """Save Cobertura XML format for coverage reporting."""
        cobertura_path = self.reports_dir / f"{self.execution_id}-cobertura.xml"

        # Create simplified Cobertura XML
        xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_content.append(
            f'<coverage line-rate="{report.overall_coverage / 100:.3f}" '
            f'branch-rate="0.0" version="1.9" timestamp="{int(report.start_time.timestamp())}">'
        )
        xml_content.append("  <sources>")
        xml_content.append("    <source>src</source>")
        xml_content.append("  </sources>")
        xml_content.append("  <packages>")
        xml_content.append(
            '    <package name="synthatrial" line-rate="{:.3f}" branch-rate="0.0">'.format(
                report.overall_coverage / 100
            )
        )
        xml_content.append("      <classes/>")
        xml_content.append("    </package>")
        xml_content.append("  </packages>")
        xml_content.append("</coverage>")

        with open(cobertura_path, "w") as f:
            f.write("\n".join(xml_content))

        print(f"📊 Cobertura XML report saved: {cobertura_path}")

    def _save_teamcity_messages(self, report: TestReport) -> None:
        """Save TeamCity service messages format."""
        teamcity_path = self.reports_dir / f"{self.execution_id}-teamcity.txt"

        messages = []

        for suite in report.suites:
            messages.append(f"##teamcity[testSuiteStarted name='{suite.name}']")

            for result in suite.results:
                messages.append(f"##teamcity[testStarted name='{result.test_name}']")

                if result.status == "failed":
                    messages.append(
                        f"##teamcity[testFailed name='{result.test_name}' "
                        f"message='{result.error_message or 'Test failed'}']"
                    )
                elif result.status == "error":
                    messages.append(
                        f"##teamcity[testFailed name='{result.test_name}' "
                        f"message='{result.error_message or 'Test error'}']"
                    )
                elif result.status == "skipped":
                    messages.append(
                        f"##teamcity[testIgnored name='{result.test_name}']"
                    )

                messages.append(
                    f"##teamcity[testFinished name='{result.test_name}' "
                    f"duration='{int(result.duration * 1000)}']"
                )

            messages.append(f"##teamcity[testSuiteFinished name='{suite.name}']")

        # Add coverage statistics
        messages.append(
            f"##teamcity[buildStatisticValue key='CodeCoverageAbsLCovered' "
            f"value='{report.overall_coverage:.1f}']"
        )

        with open(teamcity_path, "w") as f:
            f.write("\n".join(messages))

        print(f"📊 TeamCity messages saved: {teamcity_path}")

    def _save_azure_devops_format(self, report: TestReport) -> None:
        """Save Azure DevOps compatible format."""
        azure_path = self.reports_dir / f"{self.execution_id}-azure.json"

        azure_data = {
            "version": "1.0",
            "testResults": [],
            "coverage": {"lineRate": report.overall_coverage / 100, "branchRate": 0.0},
        }

        for suite in report.suites:
            for result in suite.results:
                azure_data["testResults"].append(
                    {
                        "testName": result.test_name,
                        "outcome": "Passed" if result.status == "passed" else "Failed",
                        "duration": f"00:00:{result.duration:06.3f}",
                        "errorMessage": result.error_message,
                        "stackTrace": (
                            result.output
                            if result.status in ["failed", "error"]
                            else None
                        ),
                    }
                )

        with open(azure_path, "w") as f:
            json.dump(azure_data, f, indent=2)

        print(f"📊 Azure DevOps report saved: {azure_path}")

    def _print_summary(self, report: TestReport) -> None:
        """Print comprehensive test execution summary."""
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE TEST EXECUTION SUMMARY")
        print(f"{'='*80}")
        print(f"Execution ID: {report.execution_id}")
        print(f"Duration: {report.total_duration:.2f}s")
        print(f"Overall Coverage: {report.overall_coverage:.1f}%")
        print()

        print("📊 Test Results:")
        print(f"  Total Tests: {report.summary['total_tests']}")
        print(f"  Passed: {report.summary['passed']} ✅")
        print(f"  Failed: {report.summary['failed']} ❌")
        print(f"  Skipped: {report.summary['skipped']} ⏭️")
        print(f"  Errors: {report.summary['errors']} 💥")
        print(f"  Success Rate: {report.summary['success_rate']:.1f}%")
        print()

        print("🐳 Container Results:")
        for suite in report.suites:
            status_icon = "✅" if suite.failed == 0 and suite.errors == 0 else "❌"
            print(
                f"  {status_icon} {suite.container}: {suite.passed}/{suite.total_tests} passed ({suite.coverage_percentage:.1f}% coverage)"
            )
        print()

        print("📁 Artifacts:")
        for artifact in report.artifacts[:10]:  # Show first 10 artifacts
            print(f"  - {artifact}")
        if len(report.artifacts) > 10:
            print(f"  ... and {len(report.artifacts) - 10} more")
        print()

        # Final status
        total_failed = report.summary["failed"] + report.summary["errors"]
        if total_failed == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"❌ {total_failed} TESTS FAILED")

        print(f"{'='*80}")


class TestResultAggregator:
    """Aggregates test results across multiple runs for trend analysis."""

    def __init__(self, reports_dir: Path):
        """Initialize the aggregator."""
        self.reports_dir = reports_dir
        self.history_file = reports_dir / "test_history.json"

    def add_report(self, report: TestReport) -> None:
        """Add a test report to the history."""
        history = self.load_history()

        # Create summary entry
        entry = {
            "execution_id": report.execution_id,
            "timestamp": report.start_time.isoformat(),
            "duration": report.total_duration,
            "total_tests": report.summary["total_tests"],
            "passed": report.summary["passed"],
            "failed": report.summary["failed"],
            "skipped": report.summary["skipped"],
            "errors": report.summary["errors"],
            "coverage": report.overall_coverage,
            "success_rate": report.summary["success_rate"],
            "containers": [suite.container for suite in report.suites],
            "environment": {
                "git_commit": report.environment.get("git_commit", "unknown"),
                "docker_version": report.environment.get("docker_version", "unknown"),
            },
        }

        history.append(entry)

        # Keep only last 100 entries
        if len(history) > 100:
            history = history[-100:]

        self.save_history(history)

    def load_history(self) -> List[Dict[str, Any]]:
        """Load test history from file."""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Warning: Could not load test history: {e}")
            return []

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save test history to file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Could not save test history: {e}")

    def generate_trend_report(self) -> Dict[str, Any]:
        """Generate a trend analysis report."""
        history = self.load_history()

        if len(history) < 2:
            return {"message": "Insufficient data for trend analysis"}

        # Calculate trends
        recent = history[-10:]  # Last 10 runs

        success_rates = [entry["success_rate"] for entry in recent]
        coverages = [entry["coverage"] for entry in recent]
        durations = [entry["duration"] for entry in recent]

        return {
            "total_runs": len(history),
            "recent_runs": len(recent),
            "average_success_rate": sum(success_rates) / len(success_rates),
            "average_coverage": sum(coverages) / len(coverages),
            "average_duration": sum(durations) / len(durations),
            "success_rate_trend": (
                "improving" if success_rates[-1] > success_rates[0] else "declining"
            ),
            "coverage_trend": (
                "improving" if coverages[-1] > coverages[0] else "declining"
            ),
            "duration_trend": "faster" if durations[-1] < durations[0] else "slower",
            "last_run": recent[-1] if recent else None,
        }


def main():
    """Main entry point for containerized testing."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Containerized Testing for SynthaTrial",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run tests in enhanced development container
  python scripts/run_tests_in_container.py --containers enhanced-dev

  # Run tests in multiple containers
  python scripts/run_tests_in_container.py --containers dev enhanced-dev production

  # Run specific test patterns
  python scripts/run_tests_in_container.py --test-patterns "tests/test_*properties*"

  # Skip container building (use existing images)
  python scripts/run_tests_in_container.py --no-build

  # Run with custom pytest arguments
  python scripts/run_tests_in_container.py --pytest-args "--maxfail=1 --tb=long"

  # CI mode (minimal output, exit codes)
  python scripts/run_tests_in_container.py --ci-mode

  # JSON output for CI integration
  python scripts/run_tests_in_container.py --output-format json --ci-mode

  # Fail if coverage below 80%
  python scripts/run_tests_in_container.py --coverage-threshold 80 --fail-on-coverage

  # Show test execution trends
  python scripts/run_tests_in_container.py --show-trends

  # Custom report directory
  python scripts/run_tests_in_container.py --report-dir /tmp/test-reports

  # TeamCity integration
  python scripts/run_tests_in_container.py --output-format teamcity
        """,
    )

    parser.add_argument(
        "--containers",
        nargs="+",
        choices=["dev", "enhanced-dev", "production"],
        default=["enhanced-dev"],
        help="Containers to test (default: enhanced-dev)",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        default=True,
        help="Build containers before testing (default: True)",
    )

    parser.add_argument(
        "--no-build", action="store_true", help="Skip building containers"
    )

    parser.add_argument(
        "--parallel", action="store_true", help="Run tests in parallel (experimental)"
    )

    parser.add_argument(
        "--test-patterns",
        nargs="+",
        help="Test patterns to run (e.g., tests/test_*.py)",
    )

    parser.add_argument("--pytest-args", nargs="+", help="Additional pytest arguments")

    parser.add_argument(
        "--workspace-root",
        default=".",
        help="Workspace root directory (default: current directory)",
    )

    parser.add_argument(
        "--ci-mode",
        action="store_true",
        help="CI mode: minimal output, proper exit codes",
    )

    parser.add_argument(
        "--output-format",
        choices=["console", "json", "junit", "teamcity", "azure"],
        default="console",
        help="Output format for CI integration (default: console)",
    )

    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=0.0,
        help="Minimum coverage threshold (0-100, default: 0)",
    )

    parser.add_argument(
        "--fail-on-coverage",
        action="store_true",
        help="Fail if coverage is below threshold",
    )

    parser.add_argument(
        "--report-dir",
        help="Custom directory for test reports (default: tests/reports)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Test execution timeout in seconds (default: 1800)",
    )

    parser.add_argument(
        "--show-trends",
        action="store_true",
        help="Show test execution trends and history",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Handle build flag
    build_containers = args.build and not args.no_build

    try:
        # Initialize test runner
        if args.report_dir:
            runner = ContainerizedTestRunner(workspace_root=args.workspace_root)
            runner.reports_dir = Path(args.report_dir)
            runner.reports_dir.mkdir(parents=True, exist_ok=True)
        else:
            runner = ContainerizedTestRunner(workspace_root=args.workspace_root)

        # Show trends if requested
        if args.show_trends:
            aggregator = TestResultAggregator(runner.reports_dir)
            trends = aggregator.generate_trend_report()

            print("📈 Test Execution Trends")
            print("=" * 40)
            if "message" in trends:
                print(trends["message"])
            else:
                print(f"Total runs: {trends['total_runs']}")
                print(f"Recent runs analyzed: {trends['recent_runs']}")
                print(f"Average success rate: {trends['average_success_rate']:.1f}%")
                print(f"Average coverage: {trends['average_coverage']:.1f}%")
                print(f"Average duration: {trends['average_duration']:.1f}s")
                print(f"Success rate trend: {trends['success_rate_trend']}")
                print(f"Coverage trend: {trends['coverage_trend']}")
                print(f"Duration trend: {trends['duration_trend']}")
            print()

        # Set timeout if specified
        if hasattr(runner, "_set_timeout"):
            runner._set_timeout(args.timeout)

        # Run comprehensive tests
        report = runner.run_comprehensive_tests(
            containers=args.containers,
            build_containers=build_containers,
            parallel=args.parallel,
            test_patterns=args.test_patterns,
            pytest_args=args.pytest_args,
        )

        # Check coverage threshold
        coverage_failed = False
        if args.fail_on_coverage and report.overall_coverage < args.coverage_threshold:
            coverage_failed = True
            print(
                f"❌ Coverage {report.overall_coverage:.1f}% is below threshold {args.coverage_threshold:.1f}%"
            )

        # Exit with appropriate code
        total_failed = report.summary["failed"] + report.summary["errors"]

        if args.output_format == "json":
            # JSON output for programmatic consumption
            output_data = {
                "status": (
                    "PASSED" if total_failed == 0 and not coverage_failed else "FAILED"
                ),
                "tests": report.summary["total_tests"],
                "passed": report.summary["passed"],
                "failed": total_failed,
                "coverage": report.overall_coverage,
                "duration": report.total_duration,
                "execution_id": report.execution_id,
            }
            print(json.dumps(output_data, indent=2))
        elif args.output_format == "junit":
            # JUnit XML path for CI systems
            junit_path = runner.reports_dir / f"{runner.execution_id}-junit.xml"
            print(f"JUNIT_XML_PATH={junit_path}")
        elif args.output_format == "teamcity":
            # TeamCity service messages
            teamcity_path = runner.reports_dir / f"{runner.execution_id}-teamcity.txt"
            with open(teamcity_path, "r") as f:
                print(f.read())
        elif args.output_format == "azure":
            # Azure DevOps format
            azure_path = runner.reports_dir / f"{runner.execution_id}-azure.json"
            print(f"AZURE_RESULTS_PATH={azure_path}")
        elif args.ci_mode:
            # CI mode: minimal output
            print(
                f"RESULT: {'PASSED' if total_failed == 0 and not coverage_failed else 'FAILED'}"
            )
            print(f"TESTS: {report.summary['total_tests']}")
            print(f"PASSED: {report.summary['passed']}")
            print(f"FAILED: {total_failed}")
            print(f"COVERAGE: {report.overall_coverage:.1f}%")
            if coverage_failed:
                print(f"COVERAGE_THRESHOLD_FAILED: {args.coverage_threshold:.1f}%")

        sys.exit(0 if total_failed == 0 and not coverage_failed else 1)

    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
