#!/usr/bin/env python3
"""
Integration tests for multi-architecture build orchestration

These tests validate the multi-architecture build orchestration functionality
including build configuration, platform optimization, artifact management,
and integration with existing Docker infrastructure.
"""

import json
import os
import subprocess

# Add the scripts directory to the path
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from multi_arch_build import (
    BuildConfig,
    BuildResult,
    MultiArchBuilder,
    PlatformOptimization,
)


class TestMultiArchBuildIntegration(unittest.TestCase):
    """Integration tests for multi-architecture build orchestration"""

    def setUp(self):
        """Set up test environment"""
        self.builder = MultiArchBuilder(verbose=True)
        self.test_dir = Path(tempfile.mkdtemp())

        # Override directories for testing
        self.builder.artifacts_dir = self.test_dir / "artifacts"
        self.builder.reports_dir = self.test_dir / "reports"
        self.builder.artifacts_dir.mkdir(exist_ok=True)
        self.builder.reports_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_builder_initialization(self):
        """Test builder initialization and configuration"""
        # Test builder properties
        self.assertEqual(self.builder.builder_name, "synthatrial-multi-arch")
        self.assertIn("linux/amd64", self.builder.platform_optimizations)
        self.assertIn("linux/arm64", self.builder.platform_optimizations)

        # Test target configurations
        self.assertIn("dev", self.builder.target_configs)
        self.assertIn("prod", self.builder.target_configs)
        self.assertIn("dev-enhanced", self.builder.target_configs)

        # Test directories exist
        self.assertTrue(self.builder.artifacts_dir.exists())
        self.assertTrue(self.builder.reports_dir.exists())

    def test_platform_optimization_configuration(self):
        """Test platform-specific optimization settings"""
        # Test AMD64 optimization
        amd64_opt = self.builder.get_platform_optimization("linux/amd64")
        self.assertEqual(amd64_opt.platform, "linux/amd64")
        self.assertIn("TARGETARCH", amd64_opt.build_args)
        self.assertEqual(amd64_opt.build_args["TARGETARCH"], "amd64")

        # Test ARM64 optimization
        arm64_opt = self.builder.get_platform_optimization("linux/arm64")
        self.assertEqual(arm64_opt.platform, "linux/arm64")
        self.assertIn("TARGETARCH", arm64_opt.build_args)
        self.assertEqual(arm64_opt.build_args["TARGETARCH"], "arm64")

        # Test unknown platform
        unknown_opt = self.builder.get_platform_optimization("linux/unknown")
        self.assertEqual(unknown_opt.platform, "linux/unknown")
        self.assertEqual(unknown_opt.build_args, {})

    def test_build_config_generation(self):
        """Test build configuration generation from targets"""
        platforms = ["linux/amd64", "linux/arm64"]

        # Test production config
        prod_config = self.builder.build_config_from_target("prod", platforms)
        self.assertEqual(prod_config.target, "prod")
        self.assertEqual(prod_config.platforms, platforms)
        self.assertEqual(prod_config.dockerfile, "docker/Dockerfile.prod")
        self.assertIn("synthatrial:latest", prod_config.tags)

        # Test development config
        dev_config = self.builder.build_config_from_target("dev", platforms)
        self.assertEqual(dev_config.target, "dev")
        self.assertEqual(dev_config.dockerfile, "docker/Dockerfile.dev")

        # Test with registry
        registry = "ghcr.io/test/repo"
        registry_config = self.builder.build_config_from_target(
            "prod", platforms, registry=registry
        )
        self.assertTrue(any(registry in tag for tag in registry_config.tags))

        # Test invalid target
        with self.assertRaises(ValueError):
            self.builder.build_config_from_target("invalid", platforms)

    def test_build_config_validation(self):
        """Test build configuration validation"""
        config = BuildConfig(
            target="prod",
            platforms=["linux/amd64"],
            dockerfile="docker/Dockerfile.prod",
            context=".",
        )

        # Test required fields
        self.assertEqual(config.target, "prod")
        self.assertEqual(config.platforms, ["linux/amd64"])
        self.assertEqual(config.dockerfile, "docker/Dockerfile.prod")

        # Test default values
        self.assertEqual(config.tags, [])
        self.assertEqual(config.build_args, {})
        self.assertEqual(config.labels, {})
        self.assertFalse(config.push)

    @patch("subprocess.run")
    def test_docker_availability_check(self, mock_run):
        """Test Docker and Buildx availability checking"""
        # Test Docker available, Buildx not available
        mock_run.side_effect = [
            Mock(stdout="Docker version 20.10.0", returncode=0),  # docker --version
            subprocess.CalledProcessError(
                1, "docker buildx version"
            ),  # buildx not available
        ]

        result = self.builder.check_docker_buildx()
        self.assertFalse(result)

        # Test both Docker and Buildx available
        mock_run.side_effect = [
            Mock(stdout="Docker version 20.10.0", returncode=0),  # docker --version
            Mock(stdout="buildx version", returncode=0),  # docker buildx version
            Mock(
                stdout="NAME/NODE    DRIVER/ENDPOINT\ndefault      docker", returncode=0
            ),  # docker buildx ls
        ]

        result = self.builder.check_docker_buildx()
        self.assertFalse(result)  # Builder doesn't exist yet

    @patch("subprocess.run")
    def test_builder_list_functionality(self, mock_run):
        """Test builder listing functionality"""
        # Test Docker not available
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker --version")
        builders = self.builder.list_builders()
        self.assertEqual(builders, [])

        # Test Buildx not available
        mock_run.side_effect = [
            Mock(stdout="Docker version 20.10.0", returncode=0),  # docker --version
            subprocess.CalledProcessError(
                1, "docker buildx version"
            ),  # buildx not available
        ]
        builders = self.builder.list_builders()
        self.assertEqual(builders, [])

        # Test successful listing (text format)
        mock_run.side_effect = [
            Mock(stdout="Docker version 20.10.0", returncode=0),  # docker --version
            Mock(stdout="buildx version", returncode=0),  # docker buildx version
            subprocess.CalledProcessError(
                1, "docker buildx ls --format json"
            ),  # JSON not supported
            Mock(
                stdout="NAME/NODE    DRIVER/ENDPOINT    STATUS     PLATFORMS\ndefault      docker         running    linux/amd64",
                returncode=0,
            ),  # text format
        ]
        builders = self.builder.list_builders()
        self.assertEqual(len(builders), 1)
        self.assertEqual(builders[0]["name"], "default")
        self.assertEqual(builders[0]["driver"], "docker")

    def test_build_result_initialization(self):
        """Test build result initialization and properties"""
        result = BuildResult(
            success=True, target="prod", platforms=["linux/amd64", "linux/arm64"]
        )

        # Test required fields
        self.assertTrue(result.success)
        self.assertEqual(result.target, "prod")
        self.assertEqual(result.platforms, ["linux/amd64", "linux/arm64"])

        # Test default values
        self.assertEqual(result.artifacts, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertIsNone(result.image_id)
        self.assertIsNone(result.digest)

    def test_build_output_parsing(self):
        """Test build output parsing functionality"""
        result = BuildResult(success=True, target="test", platforms=["linux/amd64"])

        # Test image ID parsing
        output_with_image = "writing image sha256:abc123def456 done"
        self.builder._parse_build_output(output_with_image, result)
        self.assertEqual(result.image_id, "sha256:abc123def456")

        # Test digest parsing
        output_with_digest = "exporting manifest sha256:def456abc123 done"
        result = BuildResult(success=True, target="test", platforms=["linux/amd64"])
        self.builder._parse_build_output(output_with_digest, result)
        self.assertEqual(result.digest, "sha256:def456abc123")

        # Test warning parsing
        output_with_warning = "WARNING: Something might be wrong"
        result = BuildResult(success=True, target="test", platforms=["linux/amd64"])
        self.builder._parse_build_output(output_with_warning, result)
        self.assertIn("WARNING: Something might be wrong", result.warnings)

    def test_build_report_generation(self):
        """Test build report generation"""
        config = BuildConfig(
            target="test",
            platforms=["linux/amd64"],
            dockerfile="Dockerfile.test",
            context=".",
        )

        result = BuildResult(
            success=True,
            target="test",
            platforms=["linux/amd64"],
            build_time_seconds=120.5,
        )

        # Generate report
        self.builder._generate_build_report(config, result)

        # Check that report file was created
        report_files = list(self.builder.reports_dir.glob("build-report-test-*.json"))
        self.assertEqual(len(report_files), 1)

        # Check report content
        with open(report_files[0], "r") as f:
            report_data = json.load(f)

        self.assertEqual(report_data["build_info"]["target"], "test")
        self.assertEqual(report_data["build_info"]["success"], True)
        self.assertEqual(report_data["build_info"]["build_time_seconds"], 120.5)
        self.assertIn("config", report_data)
        self.assertIn("result", report_data)
        self.assertIn("environment", report_data)

    def test_artifact_validation(self):
        """Test build artifact validation"""
        result = BuildResult(success=True, target="test", platforms=["linux/amd64"])

        # Test with no artifacts
        validation_result = self.builder.validate_build_artifacts(result)
        self.assertTrue(validation_result)

        # Test with existing artifact
        test_file = self.builder.artifacts_dir / "test-artifact.json"
        test_file.write_text('{"test": "data"}')
        result.artifacts = [str(test_file)]

        validation_result = self.builder.validate_build_artifacts(result)
        self.assertTrue(validation_result)

        # Test with missing artifact
        result.artifacts = [str(self.builder.artifacts_dir / "missing-file.json")]
        validation_result = self.builder.validate_build_artifacts(result)
        self.assertFalse(validation_result)

        # Test with invalid JSON metadata
        invalid_file = self.builder.artifacts_dir / "metadata-invalid.json"
        invalid_file.write_text("invalid json content")
        result.artifacts = [str(invalid_file)]

        validation_result = self.builder.validate_build_artifacts(result)
        self.assertFalse(validation_result)

    def test_artifact_cleanup(self):
        """Test artifact cleanup functionality"""
        # Create test artifacts
        old_artifact = self.builder.artifacts_dir / "old-artifact.json"
        old_report = self.builder.reports_dir / "old-report.json"
        new_artifact = self.builder.artifacts_dir / "new-artifact.json"

        old_artifact.write_text('{"old": "data"}')
        old_report.write_text('{"old": "report"}')
        new_artifact.write_text('{"new": "data"}')

        # Modify timestamps to simulate old files
        import time

        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(old_artifact, (old_time, old_time))
        os.utime(old_report, (old_time, old_time))

        # Run cleanup
        result = self.builder.cleanup_artifacts(older_than_hours=24)
        self.assertTrue(result)

        # Check that old files were removed and new files remain
        self.assertFalse(old_artifact.exists())
        self.assertFalse(old_report.exists())
        self.assertTrue(new_artifact.exists())

    @patch("subprocess.run")
    def test_git_information_extraction(self, mock_run):
        """Test git commit and version extraction"""
        # Test successful git commit extraction
        mock_run.return_value = Mock(stdout="abc123def456\n", returncode=0)
        commit = self.builder._get_git_commit()
        self.assertEqual(commit, "abc123def456")

        # Test git command failure
        mock_run.side_effect = subprocess.CalledProcessError(1, "git rev-parse HEAD")
        commit = self.builder._get_git_commit()
        self.assertEqual(commit, "unknown")

        # Test version extraction
        mock_run.side_effect = None
        mock_run.return_value = Mock(stdout="v0.2-beta-5-gabc123\n", returncode=0)
        version = self.builder._get_version()
        self.assertEqual(version, "v0.2-beta-5-gabc123")

    def test_error_handling_and_logging(self):
        """Test error handling and logging functionality"""
        # Test with verbose logging
        verbose_builder = MultiArchBuilder(verbose=True)
        self.assertEqual(verbose_builder.logger.level, 10)  # DEBUG level

        # Test with normal logging
        normal_builder = MultiArchBuilder(verbose=False)
        self.assertEqual(normal_builder.logger.level, 20)  # INFO level

    def test_integration_with_existing_infrastructure(self):
        """Test integration with existing Docker infrastructure"""
        # Test target configuration matches existing Dockerfiles
        for target in ["dev", "prod", "dev-enhanced"]:
            config = self.builder.target_configs[target]
            dockerfile_path = Path(self.builder.workspace_root) / config["dockerfile"]

            # Note: In a real environment, these files would exist
            # For testing, we just verify the paths are correctly configured
            expected_paths = {
                "dev": "docker/Dockerfile.dev",
                "prod": "docker/Dockerfile.prod",
                "dev-enhanced": "docker/Dockerfile.dev-enhanced",
            }
            self.assertEqual(config["dockerfile"], expected_paths[target])

    def test_build_configuration_completeness(self):
        """Test that build configurations include all necessary components"""
        platforms = ["linux/amd64", "linux/arm64"]
        config = self.builder.build_config_from_target("prod", platforms)

        # Test build arguments include required fields
        self.assertIn("BUILD_DATE", config.build_args)
        self.assertIn("VCS_REF", config.build_args)
        self.assertIn("VERSION", config.build_args)
        self.assertIn("BUILDKIT_INLINE_CACHE", config.build_args)

        # Test labels include OCI standard fields
        self.assertIn("org.opencontainers.image.title", config.labels)
        self.assertIn("org.opencontainers.image.description", config.labels)
        self.assertIn("org.opencontainers.image.vendor", config.labels)
        self.assertIn("org.opencontainers.image.version", config.labels)
        self.assertIn("org.opencontainers.image.revision", config.labels)
        self.assertIn("org.opencontainers.image.created", config.labels)


if __name__ == "__main__":
    unittest.main()
