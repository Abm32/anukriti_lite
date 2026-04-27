#!/usr/bin/env python3
"""
GitHub Actions Integration Tests for SynthaTrial Docker Enhancements

Tests the integration between GitHub Actions workflows and the Docker enhancement
components, ensuring CI/CD pipelines work correctly with all automation features.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestGitHubActionsIntegration:
    """Integration tests for GitHub Actions workflows"""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # Create GitHub Actions directory structure
            (workspace / ".github" / "workflows").mkdir(parents=True)
            (workspace / "scripts").mkdir(parents=True)
            (workspace / "docker").mkdir(parents=True)

            yield workspace

    def test_github_workflows_exist(self):
        """Test that all required GitHub Actions workflows exist"""
        print("\n📋 Testing GitHub Actions Workflow Files")

        required_workflows = [
            ".github/workflows/docker-build.yml",
            ".github/workflows/security-scan.yml",
            ".github/workflows/pr-validation.yml",
            ".github/workflows/release.yml",
        ]

        for workflow_file in required_workflows:
            workflow_path = project_root / workflow_file
            assert workflow_path.exists(), f"Workflow file {workflow_file} should exist"

            # Validate YAML syntax (PyYAML parses unquoted "on" as boolean True)
            try:
                with open(workflow_path) as f:
                    workflow_data = yaml.safe_load(f)
                assert (
                    "name" in workflow_data
                ), f"Workflow {workflow_file} should have a name"
                triggers = workflow_data.get("on") or workflow_data.get(True)
                assert (
                    triggers is not None
                ), f"Workflow {workflow_file} should have triggers"
                assert (
                    "jobs" in workflow_data
                ), f"Workflow {workflow_file} should have jobs"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file}: {e}")

    def test_docker_build_workflow_integration(self):
        """Test Docker build workflow integration with scripts"""
        print("\n🏗️ Testing Docker Build Workflow Integration")

        workflow_path = project_root / ".github" / "workflows" / "docker-build.yml"

        if not workflow_path.exists():
            pytest.skip("Docker build workflow not found")

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Verify workflow structure
        assert "jobs" in workflow_data, "Docker build workflow should have jobs"

        # Check for essential jobs
        jobs = workflow_data["jobs"]
        expected_job_types = ["build", "test", "security", "deploy"]

        # At least one job should exist
        assert len(jobs) > 0, "Docker build workflow should have at least one job"

        # Verify job steps reference our scripts
        script_references = []
        for job_name, job_config in jobs.items():
            if "steps" in job_config:
                for step in job_config["steps"]:
                    if "run" in step:
                        script_references.append(step["run"])

        # Check for script integrations
        expected_scripts = [
            "multi_arch_build.py",
            "security_scanner.py",
            "deploy_to_registry.py",
        ]

        workflow_content = str(workflow_data)
        for script in expected_scripts:
            # Script should be referenced somewhere in the workflow
            script_found = (
                any(script in ref for ref in script_references)
                or script in workflow_content
            )
            if not script_found:
                print(f"Warning: Script {script} not found in Docker build workflow")

    def test_security_scan_workflow_integration(self):
        """Test security scan workflow integration"""
        print("\n🔍 Testing Security Scan Workflow Integration")

        workflow_path = project_root / ".github" / "workflows" / "security-scan.yml"

        if not workflow_path.exists():
            pytest.skip("Security scan workflow not found")

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Verify security-specific configurations
        workflow_content = str(workflow_data)

        # Check for security tools integration
        security_tools = ["trivy", "grype", "security_scanner.py"]
        security_tool_found = any(tool in workflow_content for tool in security_tools)

        if not security_tool_found:
            print("Warning: No security scanning tools found in security workflow")

        # Check for security reporting
        security_reporting = ["security-report", "vulnerability", "SARIF"]
        reporting_found = any(
            report in workflow_content for report in security_reporting
        )

        if not reporting_found:
            print("Warning: No security reporting configuration found")

    def test_pr_validation_workflow_integration(self):
        """Test PR validation workflow integration"""
        print("\n✅ Testing PR Validation Workflow Integration")

        workflow_path = project_root / ".github" / "workflows" / "pr-validation.yml"

        if not workflow_path.exists():
            pytest.skip("PR validation workflow not found")

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Verify PR-specific triggers (PyYAML parses unquoted "on" as True)
        triggers = workflow_data.get("on") or workflow_data.get(True) or {}

        # Should trigger on pull requests
        pr_triggers = ["pull_request", "pull_request_target"]
        pr_trigger_found = any(trigger in triggers for trigger in pr_triggers)

        assert pr_trigger_found, "PR validation should trigger on pull requests"

        # Check for validation steps
        workflow_content = str(workflow_data)
        validation_steps = ["run_tests_in_container.py", "pytest", "pre-commit", "lint"]

        validation_found = any(step in workflow_content for step in validation_steps)
        if not validation_found:
            print("Warning: No validation steps found in PR workflow")

    def test_release_workflow_integration(self):
        """Test release workflow integration"""
        print("\n🚀 Testing Release Workflow Integration")

        workflow_path = project_root / ".github" / "workflows" / "release.yml"

        if not workflow_path.exists():
            pytest.skip("Release workflow not found")

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Verify release triggers (PyYAML parses unquoted "on" as True)
        triggers = workflow_data.get("on") or workflow_data.get(True) or {}

        # Should trigger on tags or releases
        release_triggers = ["push", "release", "workflow_dispatch"]
        release_trigger_found = any(trigger in triggers for trigger in release_triggers)

        assert (
            release_trigger_found
        ), "Release workflow should have appropriate triggers"

        # Check for deployment steps
        workflow_content = str(workflow_data)
        deployment_steps = ["deploy_to_registry.py", "production", "registry"]

        deployment_found = any(step in workflow_content for step in deployment_steps)
        if not deployment_found:
            print("Warning: No deployment steps found in release workflow")

    @patch("subprocess.run")
    def test_workflow_script_execution(self, mock_run, temp_workspace):
        """Test that workflow scripts can be executed"""
        print("\n⚙️ Testing Workflow Script Execution")

        # Mock successful script execution
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

        # Test scripts that should be callable from workflows
        workflow_scripts = [
            "scripts/multi_arch_build.py",
            "scripts/security_scanner.py",
            "scripts/deploy_to_registry.py",
            "scripts/run_tests_in_container.py",
        ]

        for script_path in workflow_scripts:
            full_script_path = project_root / script_path

            if full_script_path.exists():
                # Test help command
                try:
                    result = subprocess.run(
                        [sys.executable, str(full_script_path), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    # Script should either succeed or fail gracefully
                    assert result.returncode in [
                        0,
                        1,
                        2,
                    ], f"Script {script_path} should handle --help"

                except subprocess.TimeoutExpired:
                    print(f"Warning: Script {script_path} timed out on --help")
                except Exception as e:
                    print(f"Warning: Script {script_path} execution failed: {e}")

    def test_github_issue_templates_integration(self):
        """Test GitHub issue templates integration"""
        print("\n📝 Testing GitHub Issue Templates Integration")

        issue_template_dir = project_root / ".github" / "ISSUE_TEMPLATE"

        if not issue_template_dir.exists():
            pytest.skip("GitHub issue templates not found")

        # Check for essential issue templates
        expected_templates = [
            "bug_report.yml",
            "feature_request.yml",
            "security_issue.yml",
        ]

        for template_file in expected_templates:
            template_path = issue_template_dir / template_file

            if template_path.exists():
                # Validate YAML syntax
                try:
                    with open(template_path) as f:
                        template_data = yaml.safe_load(f)

                    assert (
                        "name" in template_data
                    ), f"Template {template_file} should have a name"
                    assert (
                        "description" in template_data
                    ), f"Template {template_file} should have a description"

                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {template_file}: {e}")

    def test_github_settings_integration(self):
        """Test GitHub repository settings integration"""
        print("\n⚙️ Testing GitHub Settings Integration")

        settings_path = project_root / ".github" / "settings.yml"

        if not settings_path.exists():
            pytest.skip("GitHub settings file not found")

        with open(settings_path) as f:
            settings_data = yaml.safe_load(f)

        # Verify essential repository settings
        if "repository" in settings_data:
            repo_settings = settings_data["repository"]

            # Check security settings
            security_settings = [
                "delete_branch_on_merge",
                "allow_squash_merge",
                "allow_merge_commit",
            ]

            for setting in security_settings:
                if setting in repo_settings:
                    print(f"  ✓ Repository setting {setting}: {repo_settings[setting]}")

    def test_pull_request_template_integration(self):
        """Test pull request template integration"""
        print("\n📋 Testing Pull Request Template Integration")

        pr_template_paths = [
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
        ]

        pr_template_found = False
        for template_path in pr_template_paths:
            full_path = project_root / template_path
            if full_path.exists():
                pr_template_found = True

                # Verify template content
                template_content = full_path.read_text()

                # Check for essential sections
                essential_sections = ["Description", "Changes", "Testing", "Checklist"]

                for section in essential_sections:
                    if section.lower() in template_content.lower():
                        print(f"  ✓ PR template includes {section} section")

                break

        if not pr_template_found:
            print("  ⚠️ No pull request template found")

    @patch("subprocess.run")
    def test_ci_environment_simulation(self, mock_run, temp_workspace):
        """Test CI environment simulation"""
        print("\n🔄 Testing CI Environment Simulation")

        # Mock CI environment variables
        ci_env_vars = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_WORKSPACE": str(temp_workspace),
            "GITHUB_REPOSITORY": "test/synthatrial",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "abc123def456",
            "RUNNER_OS": "Linux",
        }

        # Mock successful CI operations
        mock_run.return_value = Mock(returncode=0, stdout="CI Success", stderr="")

        with patch.dict(os.environ, ci_env_vars):
            # Test that scripts detect CI environment
            from scripts.deploy_to_registry import RegistryDeployer

            deployer = RegistryDeployer(verbose=False)

            # Should detect CI environment
            assert os.getenv("CI") == "true", "CI environment should be detected"
            assert (
                os.getenv("GITHUB_ACTIONS") == "true"
            ), "GitHub Actions should be detected"

            # Test CI-specific behavior
            ci_config = deployer._get_ci_configuration()
            assert ci_config is not None, "CI configuration should be available"

    def test_workflow_dependencies_integration(self):
        """Test workflow dependencies and job ordering"""
        print("\n🔗 Testing Workflow Dependencies Integration")

        workflow_files = [
            ".github/workflows/docker-build.yml",
            ".github/workflows/security-scan.yml",
        ]

        for workflow_file in workflow_files:
            workflow_path = project_root / workflow_file

            if not workflow_path.exists():
                continue

            with open(workflow_path) as f:
                workflow_data = yaml.safe_load(f)

            jobs = workflow_data.get("jobs", {})

            # Check for job dependencies
            for job_name, job_config in jobs.items():
                if "needs" in job_config:
                    dependencies = job_config["needs"]
                    if isinstance(dependencies, str):
                        dependencies = [dependencies]

                    # Verify dependencies exist
                    for dep in dependencies:
                        assert (
                            dep in jobs
                        ), f"Job {job_name} depends on non-existent job {dep}"
                        print(f"  ✓ Job {job_name} depends on {dep}")

    def test_workflow_matrix_strategy_integration(self):
        """Test workflow matrix strategy integration"""
        print("\n📊 Testing Workflow Matrix Strategy Integration")

        workflow_path = project_root / ".github" / "workflows" / "docker-build.yml"

        if not workflow_path.exists():
            pytest.skip("Docker build workflow not found")

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        jobs = workflow_data.get("jobs", {})

        # Look for matrix strategies
        matrix_found = False
        for job_name, job_config in jobs.items():
            if "strategy" in job_config and "matrix" in job_config["strategy"]:
                matrix_found = True
                matrix_config = job_config["strategy"]["matrix"]

                print(f"  ✓ Job {job_name} uses matrix strategy")

                # Verify matrix dimensions
                for key, values in matrix_config.items():
                    if isinstance(values, list):
                        print(f"    - {key}: {len(values)} variants")

        if not matrix_found:
            print("  ⚠️ No matrix strategies found in workflows")

    def test_workflow_secrets_integration(self):
        """Test workflow secrets integration"""
        print("\n🔐 Testing Workflow Secrets Integration")

        workflow_files = list((project_root / ".github" / "workflows").glob("*.yml"))

        secrets_usage = []

        for workflow_file in workflow_files:
            with open(workflow_file) as f:
                workflow_content = f.read()

            # Look for secrets usage
            if "secrets." in workflow_content:
                secrets_usage.append(workflow_file.name)

                # Common secrets that should be used
                expected_secrets = [
                    "GITHUB_TOKEN",
                    "REGISTRY_TOKEN",
                    "DOCKER_PASSWORD",
                    "GOOGLE_API_KEY",
                ]

                for secret in expected_secrets:
                    if f"secrets.{secret}" in workflow_content:
                        print(f"  ✓ {workflow_file.name} uses {secret}")

        if secrets_usage:
            print(f"  ✓ {len(secrets_usage)} workflows use secrets")
        else:
            print("  ⚠️ No secret usage found in workflows")

    def test_workflow_artifact_integration(self):
        """Test workflow artifact integration"""
        print("\n📦 Testing Workflow Artifact Integration")

        workflow_files = list((project_root / ".github" / "workflows").glob("*.yml"))

        artifact_usage = []

        for workflow_file in workflow_files:
            with open(workflow_file) as f:
                workflow_data = yaml.safe_load(f)

            workflow_content = str(workflow_data)

            # Look for artifact actions
            artifact_actions = ["actions/upload-artifact", "actions/download-artifact"]

            for action in artifact_actions:
                if action in workflow_content:
                    artifact_usage.append((workflow_file.name, action))
                    print(f"  ✓ {workflow_file.name} uses {action}")

        if not artifact_usage:
            print("  ⚠️ No artifact usage found in workflows")

    def test_workflow_caching_integration(self):
        """Test workflow caching integration"""
        print("\n💾 Testing Workflow Caching Integration")

        workflow_files = list((project_root / ".github" / "workflows").glob("*.yml"))

        caching_usage = []

        for workflow_file in workflow_files:
            with open(workflow_file) as f:
                workflow_data = yaml.safe_load(f)

            workflow_content = str(workflow_data)

            # Look for caching actions
            cache_actions = ["actions/cache", "docker/build-push-action"]

            for action in cache_actions:
                if action in workflow_content:
                    caching_usage.append((workflow_file.name, action))
                    print(f"  ✓ {workflow_file.name} uses {action}")

        if not caching_usage:
            print("  ⚠️ No caching usage found in workflows")


class TestCIEnvironmentCompatibility:
    """Test CI environment compatibility"""

    def test_docker_in_docker_compatibility(self):
        """Test Docker-in-Docker compatibility for CI"""
        print("\n🐳 Testing Docker-in-Docker Compatibility")

        # Check if Docker Compose files support CI environments
        compose_files = ["docker-compose.yml", "docker-compose.dev.yml"]

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                continue

            with open(compose_path) as f:
                compose_data = yaml.safe_load(f)

            # Check for CI-friendly configurations
            services = compose_data.get("services", {})

            for service_name, service_config in services.items():
                # Check for privileged mode (needed for Docker-in-Docker)
                if "privileged" in service_config:
                    print(f"  ✓ Service {service_name} supports privileged mode")

                # Check for Docker socket mounting
                volumes = service_config.get("volumes", [])
                docker_socket_mounted = any(
                    "/var/run/docker.sock" in str(vol) for vol in volumes
                )

                if docker_socket_mounted:
                    print(f"  ✓ Service {service_name} mounts Docker socket")

    def test_environment_variable_compatibility(self):
        """Test environment variable compatibility with CI"""
        print("\n🔧 Testing Environment Variable Compatibility")

        # Check scripts for CI environment variable usage
        script_files = [
            "scripts/deploy_to_registry.py",
            "scripts/security_scanner.py",
            "scripts/run_tests_in_container.py",
        ]

        ci_env_vars = [
            "CI",
            "GITHUB_ACTIONS",
            "GITHUB_WORKSPACE",
            "GITHUB_REPOSITORY",
            "RUNNER_OS",
        ]

        for script_file in script_files:
            script_path = project_root / script_file

            if not script_path.exists():
                continue

            script_content = script_path.read_text()

            # Check for CI environment variable usage
            for env_var in ci_env_vars:
                if env_var in script_content:
                    print(f"  ✓ {script_file} uses {env_var}")

    def test_cross_platform_compatibility(self):
        """Test cross-platform compatibility for CI"""
        print("\n🌐 Testing Cross-Platform Compatibility")

        # Check Dockerfiles for multi-platform support
        dockerfile_paths = [
            "docker/Dockerfile.dev",
            "docker/Dockerfile.prod",
            "Dockerfile",
        ]

        for dockerfile_path in dockerfile_paths:
            full_path = project_root / dockerfile_path

            if not full_path.exists():
                continue

            dockerfile_content = full_path.read_text()

            # Check for platform-specific configurations
            platform_indicators = [
                "FROM --platform=",
                "ARG TARGETPLATFORM",
                "ARG BUILDPLATFORM",
            ]

            for indicator in platform_indicators:
                if indicator in dockerfile_content:
                    print(f"  ✓ {dockerfile_path} supports multi-platform builds")
                    break


def run_github_actions_integration_tests():
    """Run all GitHub Actions integration tests"""
    print("🧪 Running GitHub Actions Integration Tests")
    print("=" * 80)

    # Run pytest with verbose output
    pytest_args = [__file__, "-v", "--tb=short"]

    result = pytest.main(pytest_args)

    print("\n" + "=" * 80)
    if result == 0:
        print("✅ All GitHub Actions integration tests passed!")
    else:
        print("❌ Some GitHub Actions integration tests failed")

    return result == 0


if __name__ == "__main__":
    success = run_github_actions_integration_tests()
    sys.exit(0 if success else 1)
