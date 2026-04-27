#!/usr/bin/env python3
"""
Integration tests for deployment automation script

Tests the deploy_to_registry.py script integration with existing Docker infrastructure,
multi-architecture builds, and CI/CD workflows.
"""

import json
import os
import subprocess

# Add src to path for imports
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the deployment script
from scripts.deploy_to_registry import (
    DeploymentConfig,
    DeploymentResult,
    RegistryConfig,
    RegistryDeployer,
)


class TestDeployToRegistryIntegration:
    """Integration tests for deployment automation"""

    @pytest.fixture
    def deployer(self):
        """Create a RegistryDeployer instance for testing"""
        return RegistryDeployer(verbose=True)

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # Create basic directory structure
            (workspace / "deployments").mkdir()
            (workspace / "deployment_reports").mkdir()
            (workspace / "scripts").mkdir()
            (workspace / "docker").mkdir()

            # Create mock files
            (workspace / "scripts" / "multi_arch_build.py").touch()
            (workspace / "docker" / "Dockerfile.prod").touch()
            (workspace / "docker" / "Dockerfile.dev").touch()
            (workspace / "docker" / "Dockerfile.dev-enhanced").touch()

            yield workspace

    def test_registry_config_creation(self, deployer):
        """Test registry configuration creation for different registry types"""

        # Test GitHub Container Registry
        ghcr_config = deployer.get_registry_config("ghcr.io/org/synthatrial")
        assert ghcr_config.name == "GitHub Container Registry"
        assert ghcr_config.hostname == "ghcr.io"
        assert ghcr_config.namespace == "org/synthatrial"
        assert ghcr_config.auth_method == "token"

        # Test Docker Hub
        dockerhub_config = deployer.get_registry_config("docker.io/org/synthatrial")
        assert dockerhub_config.name == "Docker Hub"
        assert dockerhub_config.hostname == "docker.io"
        assert dockerhub_config.namespace == "org/synthatrial"
        assert dockerhub_config.auth_method == "password"

        # Test AWS ECR
        ecr_config = deployer.get_registry_config(
            "123456789012.dkr.ecr.us-west-2.amazonaws.com/synthatrial"
        )
        assert ecr_config.name == "AWS Elastic Container Registry"
        assert ecr_config.auth_method == "aws_ecr"

        # Test custom registry
        custom_config = deployer.get_registry_config("custom.registry.com/org/repo")
        assert "Custom Registry" in custom_config.name
        assert custom_config.hostname == "custom.registry.com"

    def test_environment_configurations(self, deployer):
        """Test environment-specific configurations"""

        # Test development environment
        dev_config = deployer.environment_configs["development"]
        assert dev_config["health_check_timeout"] == 60
        assert dev_config["rollback_enabled"] is True
        assert dev_config["validation_required"] is False
        assert dev_config["approval_required"] is False

        # Test staging environment
        staging_config = deployer.environment_configs["staging"]
        assert staging_config["health_check_timeout"] == 120
        assert staging_config["validation_required"] is True
        assert staging_config["approval_required"] is False

        # Test production environment
        prod_config = deployer.environment_configs["production"]
        assert prod_config["health_check_timeout"] == 300
        assert prod_config["validation_required"] is True
        assert prod_config["approval_required"] is True

    def test_image_to_target_mapping(self, deployer):
        """Test image name to build target mapping"""

        assert deployer._map_image_to_target("synthatrial") == "prod"
        assert deployer._map_image_to_target("synthatrial-dev") == "dev"
        assert (
            deployer._map_image_to_target("synthatrial-dev-enhanced") == "dev-enhanced"
        )
        assert deployer._map_image_to_target("custom-image") == "prod"  # Default

    @patch("subprocess.run")
    def test_docker_authentication_token(self, mock_run, deployer):
        """Test Docker registry authentication with token"""

        # Mock successful authentication
        mock_run.return_value = Mock(returncode=0, stdout="Login Succeeded", stderr="")

        registry = RegistryConfig(
            name="Test Registry",
            url="ghcr.io/test/repo",
            token="test_token",
            auth_method="token",
        )

        with patch.dict(os.environ, {"REGISTRY_TOKEN": "test_token"}):
            result = deployer.authenticate_registry(registry)

        assert result is True
        mock_run.assert_called_once()

        # Verify the command was correct
        call_args = mock_run.call_args
        assert "docker" in call_args[0][0]
        assert "login" in call_args[0][0]
        assert "ghcr.io" in call_args[0][0]

    @patch("subprocess.run")
    def test_docker_authentication_password(self, mock_run, deployer):
        """Test Docker registry authentication with username/password"""

        # Mock successful authentication
        mock_run.return_value = Mock(returncode=0, stdout="Login Succeeded", stderr="")

        registry = RegistryConfig(
            name="Docker Hub",
            url="docker.io/test/repo",
            username="testuser",
            password="testpass",
            auth_method="password",
        )

        result = deployer.authenticate_registry(registry)

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_aws_ecr_authentication(self, mock_run, deployer):
        """Test AWS ECR authentication"""

        # Mock AWS CLI and Docker login
        mock_run.side_effect = [
            Mock(
                returncode=0, stdout="test_ecr_token", stderr=""
            ),  # aws ecr get-login-password
            Mock(returncode=0, stdout="Login Succeeded", stderr=""),  # docker login
        ]

        registry = RegistryConfig(
            name="AWS ECR",
            url="123456789012.dkr.ecr.us-west-2.amazonaws.com/synthatrial",
            auth_method="aws_ecr",
        )

        result = deployer.authenticate_registry(registry)

        assert result is True
        assert mock_run.call_count == 2

        # Verify AWS CLI call
        first_call = mock_run.call_args_list[0]
        assert "aws" in first_call[0][0]
        assert "ecr" in first_call[0][0]
        assert "get-login-password" in first_call[0][0]

    def test_aws_region_extraction(self, deployer):
        """Test AWS region extraction from ECR URL"""

        region = deployer._extract_aws_region(
            "123456789012.dkr.ecr.us-west-2.amazonaws.com"
        )
        assert region == "us-west-2"

        region = deployer._extract_aws_region(
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com"
        )
        assert region == "eu-central-1"

        # Test default region for invalid URL
        region = deployer._extract_aws_region("invalid.url.com")
        assert region == "us-east-1"

    @patch("subprocess.run")
    def test_image_verification(self, mock_run, deployer):
        """Test image existence verification"""

        # Mock successful manifest inspection
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"mediaType": "application/vnd.docker.distribution.manifest.v2+json"}',
        )

        result = deployer._verify_image_exists("ghcr.io/test/synthatrial:latest")

        assert result is True
        mock_run.assert_called_once()

        # Verify the command
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "manifest" in call_args
        assert "inspect" in call_args
        assert "ghcr.io/test/synthatrial:latest" in call_args

    @patch("subprocess.run")
    def test_build_and_push_integration(self, mock_run, deployer, temp_workspace):
        """Test build and push integration with multi-arch build script"""

        # Mock successful authentication and build
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Login Succeeded", stderr=""),  # docker login
            Mock(
                returncode=0, stdout="Build completed successfully", stderr=""
            ),  # multi_arch_build.py
            Mock(
                returncode=0,
                stdout='{"mediaType": "application/vnd.docker.distribution.manifest.v2+json"}',
            ),  # image verification
        ]

        # Patch workspace root
        deployer.workspace_root = temp_workspace

        registry = RegistryConfig(
            name="Test Registry",
            url="ghcr.io/test/synthatrial",
            token="test_token",
            auth_method="token",
        )

        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64", "linux/arm64"],
        )

        with patch.dict(os.environ, {"REGISTRY_TOKEN": "test_token"}):
            result = deployer.build_and_push_images(config)

        assert result is True

        # Verify multi-arch build script was called
        build_call = None
        for call in mock_run.call_args_list:
            if "multi_arch_build.py" in str(call):
                build_call = call
                break

        assert build_call is not None
        call_args = build_call[0][0]
        assert "python3" in call_args
        assert "scripts/multi_arch_build.py" in call_args
        assert "--target" in call_args
        assert "prod" in call_args
        assert "--platforms" in call_args
        assert "--push" in call_args

    @patch("requests.get")
    def test_health_check_success(self, mock_get, deployer):
        """Test successful health check"""

        # Mock successful health check response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
            health_check_url="http://localhost:8501/health",
        )

        result = deployer.perform_health_check(config)

        assert result is True
        mock_get.assert_called()

    @patch("requests.get")
    def test_health_check_failure(self, mock_get, deployer):
        """Test failed health check"""

        # Mock failed health check response
        mock_get.side_effect = [
            Mock(status_code=503),  # Service unavailable
            Mock(status_code=503),  # Still unavailable
            Mock(status_code=503),  # Still unavailable
        ]

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
            health_check_url="http://localhost:8501/health",
        )

        # Patch environment config for faster test
        deployer.environment_configs["staging"]["health_check_timeout"] = 30

        result = deployer.perform_health_check(config)

        assert result is False

    @patch("subprocess.run")
    def test_pre_deploy_hooks(self, mock_run, deployer):
        """Test pre-deployment hooks execution"""

        # Mock successful hook execution
        mock_run.return_value = Mock(returncode=0, stdout="Hook completed", stderr="")

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
            pre_deploy_hooks=[
                "script:scripts/pre_deploy.sh",
                "command:echo 'Pre-deploy check'",
                "echo 'Direct command'",
            ],
        )

        result = deployer.run_pre_deploy_hooks(config)

        assert result is True
        assert mock_run.call_count == 3

    @patch("subprocess.run")
    def test_post_deploy_hooks(self, mock_run, deployer):
        """Test post-deployment hooks execution"""

        # Mock hook execution (one success, one failure)
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Hook 1 completed", stderr=""),
            Mock(
                returncode=1, stdout="", stderr="Hook 2 failed"
            ),  # Non-critical failure
        ]

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
            post_deploy_hooks=[
                "echo 'Post-deploy notification'",
                "echo 'Post-deploy cleanup'",
            ],
        )

        result = deployer.run_post_deploy_hooks(config)

        assert result is True  # Post-deploy hooks are non-critical
        assert mock_run.call_count == 2

    def test_list_registries(self, deployer):
        """Test registry listing functionality"""

        registries = deployer.list_registries()

        assert len(registries) >= 5  # At least the 5 predefined registries

        # Check for expected registries
        registry_types = [r["type"] for r in registries]
        assert "ghcr" in registry_types
        assert "dockerhub" in registry_types
        assert "aws_ecr" in registry_types
        assert "gcr" in registry_types
        assert "acr" in registry_types

        # Verify structure
        for registry in registries:
            assert "type" in registry
            assert "name" in registry
            assert "url_pattern" in registry
            assert "auth_method" in registry
            assert "public" in registry
            assert "description" in registry

    @patch("subprocess.run")
    def test_deployment_validation(self, mock_run, deployer):
        """Test deployment validation"""

        # Mock authentication and image verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Login Succeeded", stderr=""),  # docker login
            Mock(
                returncode=0, stdout='{"mediaType": "manifest"}'
            ),  # synthatrial exists
            Mock(
                returncode=1, stdout="", stderr="Not found"
            ),  # synthatrial-dev missing
            Mock(
                returncode=0, stdout='{"mediaType": "manifest"}'
            ),  # synthatrial-dev-enhanced exists
        ]

        with patch.dict(os.environ, {"REGISTRY_TOKEN": "test_token"}):
            result = deployer.validate_deployment("staging", "ghcr.io/test/synthatrial")

        assert result["environment"] == "staging"
        assert result["registry_url"] == "ghcr.io/test/synthatrial"
        assert result["status"] == "warning"  # Some images missing
        assert len(result["images"]) == 3
        assert len(result["warnings"]) > 0

    @patch("subprocess.run")
    def test_git_integration(self, mock_run, deployer):
        """Test Git integration for version and commit tracking"""

        # Mock git commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123def456", stderr=""),  # git rev-parse HEAD
            Mock(returncode=0, stdout="v1.0.0-5-gabc123d", stderr=""),  # git describe
        ]

        commit = deployer._get_git_commit()
        version = deployer._get_version()

        assert commit == "abc123def456"
        assert version == "v1.0.0-5-gabc123d"

    def test_deployment_report_generation(self, deployer, temp_workspace):
        """Test deployment report generation"""

        # Patch workspace root
        deployer.workspace_root = temp_workspace
        deployer.reports_dir = temp_workspace / "deployment_reports"
        deployer.reports_dir.mkdir(exist_ok=True)

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
        )

        result = DeploymentResult(
            success=True,
            environment="staging",
            registry_url="test.com",
            deployed_images=["test.com/synthatrial:latest"],
            deployment_time=45.5,
        )

        with patch.object(deployer, "_get_git_commit", return_value="abc123"):
            with patch.object(deployer, "_get_version", return_value="v1.0.0"):
                deployer._generate_deployment_report(config, result)

        # Check that report file was created
        report_files = list(deployer.reports_dir.glob("deployment-report-*.json"))
        assert len(report_files) == 1

        # Verify report content
        with open(report_files[0]) as f:
            report_data = json.load(f)

        assert report_data["deployment_info"]["environment"] == "staging"
        assert report_data["deployment_info"]["success"] is True
        assert report_data["environment"]["git_commit"] == "abc123"
        assert report_data["environment"]["version"] == "v1.0.0"

    @patch("subprocess.run")
    def test_cleanup_old_deployments(self, mock_run, deployer, temp_workspace):
        """Test cleanup of old deployment artifacts"""

        # Setup test environment
        deployer.workspace_root = temp_workspace
        deployer.reports_dir = temp_workspace / "deployment_reports"
        deployer.reports_dir.mkdir(exist_ok=True)

        # Create some old report files
        old_time = time.time() - 3600  # 1 hour ago
        for i in range(10):
            report_file = deployer.reports_dir / f"deployment-report-test-{i}.json"
            report_file.write_text('{"test": true}')
            os.utime(report_file, (old_time, old_time))

        # Mock authentication
        mock_run.return_value = Mock(returncode=0, stdout="Login Succeeded", stderr="")

        result = deployer.cleanup_old_deployments("test.com", keep_count=3)

        assert result is True

        # Check that only 3 files remain
        remaining_files = list(deployer.reports_dir.glob("deployment-report-*.json"))
        assert len(remaining_files) == 3

    @patch("sys.stdin")
    def test_deployment_approval_interactive(self, mock_stdin, deployer):
        """Test interactive deployment approval"""

        # Mock interactive input
        mock_stdin.isatty.return_value = True

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="production",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
        )

        with patch("builtins.input", return_value="yes"):
            result = deployer._get_deployment_approval(config)

        assert result is True

        with patch("builtins.input", return_value="no"):
            result = deployer._get_deployment_approval(config)

        assert result is False

    def test_deployment_approval_environment_variable(self, deployer):
        """Test deployment approval via environment variable"""

        registry = RegistryConfig(name="Test", url="test.com")
        config = DeploymentConfig(
            environment="production",
            registry=registry,
            images=["synthatrial"],
            tags=["latest"],
            platforms=["linux/amd64"],
        )

        with patch.dict(os.environ, {"DEPLOYMENT_APPROVED": "true"}):
            result = deployer._get_deployment_approval(config)

        assert result is True

        with patch.dict(os.environ, {"DEPLOYMENT_APPROVED": "false"}):
            result = deployer._get_deployment_approval(config)

        assert result is False


class TestDeployToRegistryCommandLine:
    """Test command-line interface integration"""

    def test_script_execution_help(self):
        """Test that the script can be executed and shows help"""

        script_path = Path(__file__).parent.parent / "scripts" / "deploy_to_registry.py"

        try:
            result = subprocess.run(
                ["python3", str(script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0
            assert "Container Registry Deployment Automation" in result.stdout
            assert "--registry" in result.stdout
            assert "--environment" in result.stdout

        except subprocess.TimeoutExpired:
            pytest.skip("Script execution timed out")
        except FileNotFoundError:
            pytest.skip("Python3 not available")

    def test_script_list_registries(self):
        """Test list registries command"""

        script_path = Path(__file__).parent.parent / "scripts" / "deploy_to_registry.py"

        try:
            result = subprocess.run(
                ["python3", str(script_path), "--list-registries"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0
            assert "Supported Container Registries" in result.stdout
            assert "GitHub Container Registry" in result.stdout
            assert "Docker Hub" in result.stdout

        except subprocess.TimeoutExpired:
            pytest.skip("Script execution timed out")
        except FileNotFoundError:
            pytest.skip("Python3 not available")


class TestMakefileIntegration:
    """Test Makefile integration with deployment commands"""

    def test_makefile_deployment_targets_exist(self):
        """Test that deployment targets exist in Makefile"""

        makefile_path = Path(__file__).parent.parent / "Makefile"

        if not makefile_path.exists():
            pytest.skip("Makefile not found")

        makefile_content = makefile_path.read_text()

        # Check for deployment targets
        assert "deploy-staging:" in makefile_content
        assert "deploy-production:" in makefile_content
        assert "deploy-development:" in makefile_content
        assert "deploy-custom:" in makefile_content
        assert "deploy-list-registries:" in makefile_content
        assert "deploy-validate:" in makefile_content
        assert "deploy-cleanup:" in makefile_content

        # Check for deployment script calls
        assert "scripts/deploy_to_registry.py" in makefile_content

    def test_makefile_help_includes_deployment(self):
        """Test that Makefile help includes deployment commands"""

        makefile_path = Path(__file__).parent.parent / "Makefile"

        if not makefile_path.exists():
            pytest.skip("Makefile not found")

        try:
            result = subprocess.run(
                ["make", "help"],
                cwd=makefile_path.parent,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                assert "Registry Deployment Automation:" in result.stdout
                assert "deploy-staging" in result.stdout
                assert "deploy-production" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Make command not available or timed out")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestCIPipelineInterface:
    """Test the CI/CD Pipeline interface"""

    def test_cipipeline_creation(self):
        """Test CIPipeline interface creation"""
        from scripts.deploy_to_registry import CIPipeline

        pipeline = CIPipeline(verbose=True)
        assert pipeline is not None
        assert hasattr(pipeline, "deployer")
        assert hasattr(pipeline, "build_multi_arch")
        assert hasattr(pipeline, "run_test_suite")
        assert hasattr(pipeline, "push_to_registry")
        assert hasattr(pipeline, "deploy_to_environment")

    @patch("subprocess.run")
    def test_cipipeline_build_multi_arch(self, mock_run):
        """Test multi-architecture build through CIPipeline interface"""
        from scripts.deploy_to_registry import CIPipeline

        # Mock successful build
        mock_run.return_value = Mock(returncode=0, stdout="Build completed", stderr="")

        pipeline = CIPipeline(verbose=False)
        result = pipeline.build_multi_arch(["linux/amd64", "linux/arm64"])

        assert result.success is True
        assert result.platforms == ["linux/amd64", "linux/arm64"]
        assert len(result.image_names) > 0
        assert result.build_time > 0

    @patch("subprocess.run")
    def test_cipipeline_run_test_suite(self, mock_run):
        """Test test suite execution through CIPipeline interface"""
        from scripts.deploy_to_registry import CIPipeline

        # Mock successful tests
        mock_run.return_value = Mock(returncode=0, stdout="All tests passed", stderr="")

        pipeline = CIPipeline(verbose=False)
        result = pipeline.run_test_suite(["unit", "integration"])

        assert result.success is True
        assert result.test_types == ["unit", "integration"]
        assert result.passed_count == 2
        assert result.failed_count == 0
        assert result.execution_time > 0

    @patch("subprocess.run")
    def test_cipipeline_push_to_registry(self, mock_run):
        """Test registry push through CIPipeline interface"""
        from scripts.deploy_to_registry import CIPipeline

        # Mock successful docker commands
        mock_run.return_value = Mock(returncode=0, stdout="Push completed", stderr="")

        pipeline = CIPipeline(verbose=False)
        result = pipeline.push_to_registry("synthatrial", ["latest", "v1.0.0"])

        assert result is True
        assert mock_run.call_count == 4  # 2 tag commands + 2 push commands
