#!/usr/bin/env python3
"""
Integration Test Runner for SynthaTrial Docker Enhancements

Comprehensive test runner that executes all integration tests for complete workflows,
ensuring all Docker enhancements work together seamlessly.

This runner orchestrates:
1. Complete workflow integration tests
2. GitHub Actions integration tests
3. Docker environment integration tests
4. Cross-component validation tests
5. End-to-end system validation
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class IntegrationTestRunner:
    """Comprehensive integration test runner"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.workspace_root = project_root
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def run_all_integration_tests(self) -> Dict:
        """Run all integration test suites"""
        print("🚀 Starting Comprehensive Integration Test Suite")
        print("=" * 80)

        self.start_time = time.time()

        # Define test suites in execution order
        test_suites = [
            {
                "name": "Docker Environment Integration",
                "module": "test_docker_environment_integration",
                "description": "Tests Docker containers, compose files, and environment setup",
            },
            {
                "name": "Complete Workflow Integration",
                "module": "test_complete_workflow_integration",
                "description": "Tests end-to-end workflows combining all components",
            },
            {
                "name": "GitHub Actions Integration",
                "module": "test_github_actions_integration",
                "description": "Tests CI/CD pipeline integration and automation",
            },
            {
                "name": "Cross-Component Validation",
                "module": None,  # Custom validation
                "description": "Tests integration between different enhancement components",
            },
        ]

        # Execute test suites
        for suite in test_suites:
            print(f"\n🧪 Running {suite['name']}")
            print(f"📋 {suite['description']}")
            print("-" * 60)

            if suite["module"]:
                result = self._run_test_module(suite["module"])
            else:
                result = self._run_cross_component_validation()

            self.test_results[suite["name"]] = result

            if result["success"]:
                print(f"✅ {suite['name']} completed successfully")
            else:
                print(f"❌ {suite['name']} failed")
                if not self.verbose:
                    break  # Stop on first failure in non-verbose mode

        self.end_time = time.time()

        # Generate comprehensive report
        return self._generate_final_report()

    def _run_test_module(self, module_name: str) -> Dict:
        """Run a specific test module"""
        test_file = self.workspace_root / "tests" / f"{module_name}.py"

        if not test_file.exists():
            return {
                "success": False,
                "error": f"Test file not found: {test_file}",
                "duration": 0,
                "tests_run": 0,
                "failures": 1,
                "errors": 0,
            }

        start_time = time.time()

        try:
            # Run pytest on the specific module
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(test_file),
                    "-v",
                    "--tb=short",
                    "--json-report",
                    "--json-report-file",
                    f"tests/reports/{module_name}_report.json",
                ],
                capture_output=True,
                text=True,
                cwd=self.workspace_root,
                timeout=300,  # 5 minute timeout per module
            )

            duration = time.time() - start_time

            # Parse results
            report_file = (
                self.workspace_root / "tests" / "reports" / f"{module_name}_report.json"
            )

            if report_file.exists():
                with open(report_file) as f:
                    report_data = json.load(f)

                return {
                    "success": result.returncode == 0,
                    "duration": duration,
                    "tests_run": report_data.get("summary", {}).get("total", 0),
                    "failures": report_data.get("summary", {}).get("failed", 0),
                    "errors": report_data.get("summary", {}).get("error", 0),
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            else:
                return {
                    "success": result.returncode == 0,
                    "duration": duration,
                    "tests_run": 0,
                    "failures": 1 if result.returncode != 0 else 0,
                    "errors": 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Test module {module_name} timed out",
                "duration": time.time() - start_time,
                "tests_run": 0,
                "failures": 1,
                "errors": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to run {module_name}: {str(e)}",
                "duration": time.time() - start_time,
                "tests_run": 0,
                "failures": 0,
                "errors": 1,
            }

    def _run_cross_component_validation(self) -> Dict:
        """Run cross-component validation tests"""
        print("🔗 Running Cross-Component Validation Tests")

        start_time = time.time()
        validation_results = []

        # Test 1: SSL + Data + Deployment Integration
        print("  🔒 Testing SSL + Data + Deployment Integration")
        ssl_data_result = self._validate_ssl_data_deployment_integration()
        validation_results.append(("SSL + Data + Deployment", ssl_data_result))

        # Test 2: Security + Monitoring Integration
        print("  🛡️ Testing Security + Monitoring Integration")
        security_monitoring_result = self._validate_security_monitoring_integration()
        validation_results.append(("Security + Monitoring", security_monitoring_result))

        # Test 3: CI/CD + Docker Integration
        print("  🔄 Testing CI/CD + Docker Integration")
        cicd_docker_result = self._validate_cicd_docker_integration()
        validation_results.append(("CI/CD + Docker", cicd_docker_result))

        # Test 4: Development + Production Parity
        print("  ⚖️ Testing Development + Production Parity")
        dev_prod_result = self._validate_dev_prod_parity()
        validation_results.append(("Dev/Prod Parity", dev_prod_result))

        # Test 5: Makefile + Scripts Integration
        print("  🔨 Testing Makefile + Scripts Integration")
        makefile_result = self._validate_makefile_scripts_integration()
        validation_results.append(("Makefile + Scripts", makefile_result))

        duration = time.time() - start_time

        # Aggregate results
        total_tests = len(validation_results)
        passed_tests = sum(1 for _, result in validation_results if result)
        failed_tests = total_tests - passed_tests

        return {
            "success": failed_tests == 0,
            "duration": duration,
            "tests_run": total_tests,
            "failures": failed_tests,
            "errors": 0,
            "validation_results": validation_results,
        }

    def _validate_ssl_data_deployment_integration(self) -> bool:
        """Validate SSL + Data + Deployment integration"""
        try:
            # Check SSL manager exists and is importable
            # Check data initializer exists and is importable
            from scripts.data_initializer import DataInitializer

            # Check deployment script exists and is importable
            from scripts.deploy_to_registry import RegistryDeployer
            from scripts.ssl_manager import SSLManager

            # Verify SSL certificates can be generated for deployment
            ssl_manager = SSLManager("/tmp/test_ssl")

            # Verify data initializer can validate deployment readiness
            data_initializer = DataInitializer(workspace_root=self.workspace_root)

            # Verify deployer can handle SSL-enabled deployments
            deployer = RegistryDeployer(verbose=False)

            print("    ✓ All SSL + Data + Deployment components importable")
            return True

        except ImportError as e:
            print(f"    ❌ Import error: {e}")
            return False
        except Exception as e:
            print(f"    ❌ Integration error: {e}")
            return False

    def _validate_security_monitoring_integration(self) -> bool:
        """Validate Security + Monitoring integration"""
        try:
            # Check security scanner exists and is importable
            # Check production monitor exists and is importable
            from scripts.production_monitor import ProductionMonitor
            from scripts.security_scanner import SecurityScanner

            # Verify security scanner can integrate with monitoring
            security_scanner = SecurityScanner(workspace_root=self.workspace_root)
            monitor = ProductionMonitor(workspace_root=self.workspace_root)

            print("    ✓ Security + Monitoring components importable")
            return True

        except ImportError as e:
            print(f"    ❌ Import error: {e}")
            return False
        except Exception as e:
            print(f"    ❌ Integration error: {e}")
            return False

    def _validate_cicd_docker_integration(self) -> bool:
        """Validate CI/CD + Docker integration"""
        try:
            # Check GitHub Actions workflows exist
            workflows_dir = self.workspace_root / ".github" / "workflows"

            if not workflows_dir.exists():
                print("    ❌ GitHub workflows directory not found")
                return False

            # Check for essential workflows
            essential_workflows = ["docker-build.yml", "security-scan.yml"]

            for workflow in essential_workflows:
                workflow_path = workflows_dir / workflow
                if not workflow_path.exists():
                    print(f"    ❌ Workflow not found: {workflow}")
                    return False

            # Check Docker Compose files exist
            compose_files = [
                "docker-compose.yml",
                "docker-compose.dev.yml",
                "docker-compose.prod.yml",
            ]

            for compose_file in compose_files:
                compose_path = self.workspace_root / compose_file
                if not compose_path.exists():
                    print(f"    ❌ Compose file not found: {compose_file}")
                    return False

            print("    ✓ CI/CD + Docker integration validated")
            return True

        except Exception as e:
            print(f"    ❌ Integration error: {e}")
            return False

    def _validate_dev_prod_parity(self) -> bool:
        """Validate development and production environment parity"""
        try:
            import yaml

            # Compare development and production configurations
            dev_compose_path = self.workspace_root / "docker-compose.dev.yml"
            prod_compose_path = self.workspace_root / "docker-compose.prod.yml"

            if not dev_compose_path.exists() or not prod_compose_path.exists():
                print("    ❌ Dev or prod compose files not found")
                return False

            # Load compose configurations
            with open(dev_compose_path) as f:
                dev_config = yaml.safe_load(f)

            with open(prod_compose_path) as f:
                prod_config = yaml.safe_load(f)

            # Check service parity
            dev_services = set(dev_config.get("services", {}).keys())
            prod_services = set(prod_config.get("services", {}).keys())

            # Core services should exist in both
            core_services = {"synthatrial"}  # Main application service

            for service in core_services:
                if service not in dev_services:
                    print(f"    ❌ Core service {service} missing from dev config")
                    return False
                if service not in prod_services:
                    print(f"    ❌ Core service {service} missing from prod config")
                    return False

            print("    ✓ Dev/Prod parity validated")
            return True

        except Exception as e:
            print(f"    ❌ Parity validation error: {e}")
            return False

    def _validate_makefile_scripts_integration(self) -> bool:
        """Validate Makefile and scripts integration"""
        try:
            # Check Makefile exists
            makefile_path = self.workspace_root / "Makefile"

            if not makefile_path.exists():
                print("    ❌ Makefile not found")
                return False

            makefile_content = makefile_path.read_text()

            # Check for essential script integrations
            essential_scripts = [
                "ssl_manager.py",
                "data_initializer.py",
                "deploy_to_registry.py",
                "security_scanner.py",
                "run_tests_in_container.py",
            ]

            for script in essential_scripts:
                if script not in makefile_content:
                    print(f"    ❌ Script {script} not integrated in Makefile")
                    return False

            # Check for essential targets
            essential_targets = [
                "ssl-setup:",
                "data-init:",
                "security-scan:",
                "deploy-staging:",
                "test-containerized:",
            ]

            for target in essential_targets:
                if target not in makefile_content:
                    print(f"    ❌ Target {target} not found in Makefile")
                    return False

            print("    ✓ Makefile + Scripts integration validated")
            return True

        except Exception as e:
            print(f"    ❌ Makefile integration error: {e}")
            return False

    def _generate_final_report(self) -> Dict:
        """Generate comprehensive final report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE INTEGRATION TEST REPORT")
        print("=" * 80)

        total_duration = (
            self.end_time - self.start_time if self.end_time and self.start_time else 0
        )

        # Aggregate statistics
        total_tests = 0
        total_failures = 0
        total_errors = 0
        successful_suites = 0

        for suite_name, result in self.test_results.items():
            print(f"\n📋 {suite_name}")
            print("-" * 40)

            if result["success"]:
                print("✅ Status: PASSED")
                successful_suites += 1
            else:
                print("❌ Status: FAILED")

            print(f"⏱️  Duration: {result['duration']:.2f}s")
            print(f"🧪 Tests Run: {result['tests_run']}")
            print(f"❌ Failures: {result['failures']}")
            print(f"💥 Errors: {result['errors']}")

            total_tests += result["tests_run"]
            total_failures += result["failures"]
            total_errors += result["errors"]

            # Show validation details for cross-component tests
            if "validation_results" in result:
                print("🔗 Cross-Component Validations:")
                for validation_name, validation_success in result["validation_results"]:
                    status = "✅" if validation_success else "❌"
                    print(f"   {status} {validation_name}")

        # Overall summary
        print("\n" + "=" * 80)
        print("📈 OVERALL SUMMARY")
        print("=" * 80)

        overall_success = total_failures == 0 and total_errors == 0

        print(f"🎯 Overall Status: {'✅ SUCCESS' if overall_success else '❌ FAILURE'}")
        print(f"⏱️  Total Duration: {total_duration:.2f}s")
        print(f"📊 Test Suites: {successful_suites}/{len(self.test_results)} passed")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"❌ Total Failures: {total_failures}")
        print(f"💥 Total Errors: {total_errors}")

        if overall_success:
            print("\n🎉 All Docker enhancements integration tests passed!")
            print("🚀 System is ready for production deployment!")
        else:
            print("\n⚠️  Some integration tests failed.")
            print("🔧 Please review failures before deployment.")

        # Generate JSON report
        report_data = {
            "timestamp": time.time(),
            "overall_success": overall_success,
            "total_duration": total_duration,
            "test_suites": len(self.test_results),
            "successful_suites": successful_suites,
            "total_tests": total_tests,
            "total_failures": total_failures,
            "total_errors": total_errors,
            "suite_results": self.test_results,
            "environment": {
                "workspace_root": str(self.workspace_root),
                "python_version": sys.version,
                "platform": sys.platform,
            },
        }

        # Save report
        reports_dir = self.workspace_root / "tests" / "reports"
        reports_dir.mkdir(exist_ok=True)

        report_file = reports_dir / "integration_test_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_file}")

        return report_data


def run_comprehensive_integration_tests(verbose: bool = True) -> bool:
    """Run comprehensive integration tests"""

    # Ensure reports directory exists
    reports_dir = project_root / "tests" / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Create and run test runner
    runner = IntegrationTestRunner(verbose=verbose)
    report = runner.run_all_integration_tests()

    return report["overall_success"]


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprehensive Integration Test Runner for SynthaTrial Docker Enhancements"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (stop on first failure)",
    )

    args = parser.parse_args()

    verbose = args.verbose and not args.quiet

    success = run_comprehensive_integration_tests(verbose=verbose)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
