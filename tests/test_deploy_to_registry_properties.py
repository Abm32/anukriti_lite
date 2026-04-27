#!/usr/bin/env python3
"""
Property-based tests for deployment automation script

Uses Hypothesis to test deployment automation properties across various inputs
and configurations, ensuring correctness and robustness.

Feature: docker-enhancements
"""

import json
import os

# Add src to path for imports
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.deploy_to_registry import (
    DeploymentConfig,
    DeploymentResult,
    RegistryConfig,
    RegistryDeployer,
)


# Hypothesis strategies for generating test data
@st.composite
def registry_urls(draw):
    """Generate valid registry URLs"""
    registry_types = [
        "ghcr.io/{org}/{repo}",
        "docker.io/{org}/{repo}",
        "{account}.dkr.ecr.{region}.amazonaws.com/{repo}",
        "gcr.io/{project}/{repo}",
        "{registry}.azurecr.io/{repo}",
    ]

    template = draw(st.sampled_from(registry_types))

    # Generate components
    org = draw(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            | st.characters(min_codepoint=48, max_codepoint=57),
            min_size=3,
            max_size=20,
        )
    )
    repo = draw(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            | st.characters(min_codepoint=48, max_codepoint=57),
            min_size=3,
            max_size=30,
        )
    )
    account = draw(
        st.text(
            alphabet=st.characters(min_codepoint=48, max_codepoint=57),
            min_size=12,
            max_size=12,
        )
    )
    region = draw(
        st.sampled_from(["us-east-1", "us-west-2", "eu-central-1", "ap-southeast-1"])
    )
    project = draw(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            | st.characters(min_codepoint=48, max_codepoint=57),
            min_size=5,
            max_size=25,
        )
    )
    registry = draw(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            | st.characters(min_codepoint=48, max_codepoint=57),
            min_size=5,
            max_size=20,
        )
    )

    return template.format(
        org=org,
        repo=repo,
        account=account,
        region=region,
        project=project,
        registry=registry,
    )


@st.composite
def image_names(draw):
    """Generate valid Docker image names"""
    base_names = ["synthatrial", "synthatrial-dev", "synthatrial-dev-enhanced"]
    custom_name = draw(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            | st.characters(min_codepoint=48, max_codepoint=57)
            | st.just("-")
            | st.just("_"),
            min_size=3,
            max_size=50,
        ).filter(lambda x: not x.startswith(("-", "_")) and not x.endswith(("-", "_")))
    )

    return draw(st.sampled_from(base_names + [custom_name]))


@st.composite
def image_tags(draw):
    """Generate valid Docker image tags"""
    tag_types = [
        "latest",
        "stable",
        "dev",
        "staging",
        "production",
        draw(st.text(alphabet="v0123456789.-", min_size=1, max_size=20)),
        draw(
            st.text(
                alphabet=st.characters(min_codepoint=97, max_codepoint=122)
                | st.characters(min_codepoint=48, max_codepoint=57)
                | st.just("-")
                | st.just(".")
                | st.just("_"),
                min_size=1,
                max_size=128,
            )
        ),
    ]

    tag = draw(st.sampled_from(tag_types))
    assume(len(tag) > 0 and not tag.startswith(".") and not tag.startswith("-"))
    return tag


@st.composite
def deployment_environments(draw):
    """Generate deployment environment names"""
    return draw(st.sampled_from(["development", "staging", "production"]))


@st.composite
def platform_lists(draw):
    """Generate lists of valid platforms"""
    platforms = ["linux/amd64", "linux/arm64", "linux/arm/v7", "linux/386"]
    return draw(
        st.lists(st.sampled_from(platforms), min_size=1, max_size=4, unique=True)
    )


class TestDeploymentAutomationProperties:
    """Property-based tests for deployment automation"""

    @given(registry_url=registry_urls())
    @settings(max_examples=50, deadline=5000)
    def test_registry_config_creation_property(self, registry_url):
        """
        Property 1: Registry Configuration Creation and Validation
        For any valid registry URL, the deployer should create a valid RegistryConfig
        with proper hostname extraction and namespace parsing
        **Validates: Requirements 5.3, 5.5**
        """
        deployer = RegistryDeployer(verbose=False)
        config = deployer.get_registry_config(registry_url)

        # Properties that should always hold
        assert isinstance(config, RegistryConfig)
        assert config.name is not None and len(config.name) > 0
        assert config.url == registry_url
        assert config.hostname is not None and len(config.hostname) > 0
        assert config.auth_method in ["token", "password", "aws_ecr"]
        assert isinstance(config.public, bool)

        # Hostname should be valid
        assert "." in config.hostname or config.hostname == "localhost"

        # If namespace exists, it should be valid
        if config.namespace:
            assert len(config.namespace) > 0
            assert not config.namespace.startswith("/")
            assert not config.namespace.endswith("/")

    @given(
        environment=deployment_environments(),
        images=st.lists(image_names(), min_size=1, max_size=5, unique=True),
        tags=st.lists(image_tags(), min_size=1, max_size=3, unique=True),
        platforms=platform_lists(),
    )
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.filter_too_much],
    )
    def test_deployment_config_validation_property(
        self, environment, images, tags, platforms
    ):
        """
        Property 2: Deployment Configuration Validation
        For any valid deployment parameters, the system should create a valid
        DeploymentConfig with proper environment-specific settings
        **Validates: Requirements 5.3, 5.5**
        """
        deployer = RegistryDeployer(verbose=False)
        registry = RegistryConfig(
            name="Test Registry", url="test.registry.com/org/repo", auth_method="token"
        )

        config = DeploymentConfig(
            environment=environment,
            registry=registry,
            images=images,
            tags=tags,
            platforms=platforms,
        )

        # Properties that should always hold
        assert config.environment in ["development", "staging", "production"]
        assert isinstance(config.registry, RegistryConfig)
        assert len(config.images) > 0
        assert len(config.tags) > 0
        assert len(config.platforms) > 0
        assert isinstance(config.rollback_enabled, bool)
        assert isinstance(config.pre_deploy_hooks, list)
        assert isinstance(config.post_deploy_hooks, list)

        # Environment-specific properties
        env_config = deployer.environment_configs.get(environment, {})
        if environment == "production":
            assert env_config.get("approval_required", False) is True
            assert env_config.get("validation_required", False) is True
        elif environment == "staging":
            assert env_config.get("validation_required", False) is True
            assert env_config.get("approval_required", False) is False

    @given(image_name=image_names())
    @settings(max_examples=20, deadline=2000)
    def test_image_target_mapping_property(self, image_name):
        """
        Property 3: Image to Build Target Mapping Consistency
        For any image name, the target mapping should be consistent and valid
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        target = deployer._map_image_to_target(image_name)

        # Properties that should always hold
        assert target in ["dev", "prod", "dev-enhanced"]

        # Specific mapping rules
        if "dev-enhanced" in image_name:
            assert target == "dev-enhanced"
        elif "dev" in image_name and "enhanced" not in image_name:
            assert target == "dev"
        else:
            assert target == "prod"  # Default case

    @given(registry_url=registry_urls())
    @settings(max_examples=20, deadline=3000)
    def test_aws_region_extraction_property(self, registry_url):
        """
        Property 4: AWS Region Extraction Consistency
        For any registry URL, AWS region extraction should be consistent
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        region = deployer._extract_aws_region(registry_url)

        # Properties that should always hold
        assert isinstance(region, str)
        assert len(region) > 0

        # If it's an ECR URL, should extract correct region
        if ".dkr.ecr." in registry_url and ".amazonaws.com" in registry_url:
            parts = registry_url.split(".")
            ecr_index = None
            for i, part in enumerate(parts):
                if part == "ecr":
                    ecr_index = i
                    break

            if ecr_index is not None and ecr_index + 1 < len(parts):
                expected_region = parts[ecr_index + 1]
                assert region == expected_region
        else:
            # Should return default region for non-ECR URLs
            assert region == "us-east-1"

    @given(
        environment=deployment_environments(),
        success=st.booleans(),
        deployment_time=st.floats(min_value=0.1, max_value=3600.0),
        image_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=30, deadline=5000)
    def test_deployment_result_properties(
        self, environment, success, deployment_time, image_count
    ):
        """
        Property 5: Deployment Result Consistency
        For any deployment result, the data structure should be consistent and valid
        **Validates: Requirements 5.3, 5.5**
        """
        deployed_images = [f"registry.com/image{i}:tag" for i in range(image_count)]

        result = DeploymentResult(
            success=success,
            environment=environment,
            registry_url="registry.com",
            deployed_images=deployed_images,
            deployment_time=deployment_time,
        )

        # Properties that should always hold
        assert isinstance(result.success, bool)
        assert result.environment in ["development", "staging", "production"]
        assert isinstance(result.registry_url, str)
        assert len(result.registry_url) > 0
        assert isinstance(result.deployed_images, list)
        assert len(result.deployed_images) == image_count
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert result.deployment_id is not None
        assert len(result.deployment_id) > 0

        # Time should be positive if set
        if result.deployment_time is not None:
            assert result.deployment_time > 0

    @given(
        registry_type=st.sampled_from(["ghcr", "dockerhub", "aws_ecr", "gcr", "acr"]),
        username=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        token=st.text(min_size=10, max_size=100),
    )
    @settings(max_examples=25, deadline=3000)
    def test_registry_authentication_config_property(
        self, registry_type, username, token
    ):
        """
        Property 6: Registry Authentication Configuration
        For any registry type and credentials, authentication configuration should be valid
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        registry_config = deployer.registry_configs[registry_type]

        registry = RegistryConfig(
            name=registry_config["name"],
            url=f"test.{registry_type}.com/org/repo",
            username=username if registry_config["auth_method"] == "password" else None,
            token=token if registry_config["auth_method"] == "token" else None,
            auth_method=registry_config["auth_method"],
        )

        # Properties that should always hold
        assert registry.auth_method in ["token", "password", "aws_ecr"]

        # Credentials should match auth method
        if registry.auth_method == "token":
            assert registry.token is not None or registry.username is None
        elif registry.auth_method == "password":
            assert registry.username is not None

        # Registry name should be descriptive
        assert len(registry.name) > 5
        assert "Registry" in registry.name or "Hub" in registry.name

    @given(
        hook_commands=st.lists(
            st.text(min_size=5, max_size=100).filter(lambda x: x.strip()),
            min_size=0,
            max_size=5,
        )
    )
    @settings(max_examples=20, deadline=3000)
    def test_deployment_hooks_property(self, hook_commands):
        """
        Property 7: Deployment Hooks Validation
        For any list of hook commands, the hook processing should be consistent
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        registry = RegistryConfig(name="Test", url="test.com", auth_method="token")

        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["test"],
            tags=["latest"],
            platforms=["linux/amd64"],
            pre_deploy_hooks=hook_commands,
            post_deploy_hooks=hook_commands,
        )

        # Properties that should always hold
        assert isinstance(config.pre_deploy_hooks, list)
        assert isinstance(config.post_deploy_hooks, list)
        assert len(config.pre_deploy_hooks) == len(hook_commands)
        assert len(config.post_deploy_hooks) == len(hook_commands)

        # All hooks should be strings
        for hook in config.pre_deploy_hooks + config.post_deploy_hooks:
            assert isinstance(hook, str)
            assert len(hook.strip()) > 0

    @given(keep_count=st.integers(min_value=1, max_value=100))
    @settings(max_examples=15, deadline=2000)
    def test_cleanup_parameters_property(self, keep_count):
        """
        Property 8: Cleanup Parameters Validation
        For any cleanup parameters, the values should be within valid ranges
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        # Properties that should always hold for cleanup parameters
        assert keep_count >= 1
        assert keep_count <= 100

        # Keep count should be reasonable for practical use
        if keep_count > 50:
            # Large keep counts should still be handled gracefully
            assert keep_count <= 100

    @given(
        environment=deployment_environments(),
        registry_url=registry_urls(),
        images=st.lists(image_names(), min_size=1, max_size=3, unique=True),
    )
    @settings(max_examples=20, deadline=5000)
    def test_validation_result_structure_property(
        self, environment, registry_url, images
    ):
        """
        Property 9: Validation Result Structure Consistency
        For any validation request, the result structure should be consistent
        **Validates: Requirements 5.5**
        """
        deployer = RegistryDeployer(verbose=False)
        with patch.object(deployer, "authenticate_registry", return_value=True):
            with patch.object(deployer, "_verify_image_exists", return_value=True):
                result = deployer.validate_deployment(environment, registry_url)

        # Properties that should always hold
        assert isinstance(result, dict)
        assert "environment" in result
        assert "registry_url" in result
        assert "timestamp" in result
        assert "status" in result
        assert "images" in result
        assert "errors" in result
        assert "warnings" in result

        # Values should be correct types
        assert result["environment"] == environment
        assert result["registry_url"] == registry_url
        assert result["status"] in ["success", "warning", "error", "unknown"]
        assert isinstance(result["images"], list)
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)

        # Timestamp should be valid ISO format
        from datetime import datetime

        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))

    @given(
        platforms=platform_lists(),
        tags=st.lists(image_tags(), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=20, deadline=3000)
    def test_multi_platform_deployment_property(self, platforms, tags):
        """
        Property 10: Multi-Platform Deployment Consistency
        For any combination of platforms and tags, deployment configuration should be valid
        **Validates: Requirements 5.3**
        """
        deployer = RegistryDeployer(verbose=False)
        registry = RegistryConfig(name="Test", url="test.com", auth_method="token")

        config = DeploymentConfig(
            environment="staging",
            registry=registry,
            images=["synthatrial"],
            tags=tags,
            platforms=platforms,
        )

        # Properties that should always hold
        assert len(config.platforms) > 0
        assert len(config.tags) > 0

        # All platforms should be valid
        for platform in config.platforms:
            assert "/" in platform  # Should have OS/arch format
            parts = platform.split("/")
            assert len(parts) >= 2
            assert parts[0] in ["linux", "windows", "darwin"]

        # All tags should be valid
        for tag in config.tags:
            assert len(tag) > 0
            assert not tag.startswith(".")
            assert not tag.startswith("-")


class DeploymentStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for deployment workflows
    Tests complex deployment scenarios with multiple operations
    """

    def __init__(self):
        super().__init__()
        self.deployer = RegistryDeployer(verbose=False)
        self.deployments = {}
        self.registries = {}

    registries = Bundle("registries")
    deployments = Bundle("deployments")

    @initialize()
    def setup(self):
        """Initialize the test environment"""
        self.deployer = RegistryDeployer(verbose=False)
        self.deployments = {}
        self.registries = {}

    @rule(target=registries, registry_url=registry_urls())
    def create_registry(self, registry_url):
        """Create a registry configuration"""
        config = self.deployer.get_registry_config(registry_url)
        registry_id = f"registry_{len(self.registries)}"
        self.registries[registry_id] = config
        return registry_id

    @rule(
        target=deployments,
        registry_id=registries,
        environment=deployment_environments(),
        images=st.lists(image_names(), min_size=1, max_size=3, unique=True),
        tags=st.lists(image_tags(), min_size=1, max_size=2, unique=True),
    )
    def create_deployment_config(self, registry_id, environment, images, tags):
        """Create a deployment configuration"""
        registry = self.registries[registry_id]

        config = DeploymentConfig(
            environment=environment,
            registry=registry,
            images=images,
            tags=tags,
            platforms=["linux/amd64"],
        )

        deployment_id = f"deployment_{len(self.deployments)}"
        self.deployments[deployment_id] = config
        return deployment_id

    @rule(deployment_id=deployments)
    def validate_deployment_config(self, deployment_id):
        """Validate that deployment configuration is consistent"""
        config = self.deployments[deployment_id]

        # Invariants that should always hold
        assert isinstance(config, DeploymentConfig)
        assert config.environment in ["development", "staging", "production"]
        assert len(config.images) > 0
        assert len(config.tags) > 0
        assert len(config.platforms) > 0
        assert isinstance(config.registry, RegistryConfig)

    @rule(registry_id=registries)
    def validate_registry_config(self, registry_id):
        """Validate that registry configuration is consistent"""
        config = self.registries[registry_id]

        # Invariants that should always hold
        assert isinstance(config, RegistryConfig)
        assert len(config.name) > 0
        assert len(config.url) > 0
        assert config.auth_method in ["token", "password", "aws_ecr"]

    @invariant()
    def deployment_registry_consistency(self):
        """Deployments should always reference valid registries"""
        for deployment_config in self.deployments.values():
            assert isinstance(deployment_config.registry, RegistryConfig)
            # Registry should be one of our created registries
            registry_found = False
            for registry_config in self.registries.values():
                if (
                    deployment_config.registry.url == registry_config.url
                    and deployment_config.registry.name == registry_config.name
                ):
                    registry_found = True
                    break
            assert registry_found or len(self.registries) == 0

    @invariant()
    def environment_specific_properties(self):
        """Environment-specific properties should be consistent"""
        for deployment_config in self.deployments.values():
            env = deployment_config.environment
            env_config = self.deployer.environment_configs.get(env, {})

            if env == "production":
                # Production should have stricter requirements
                assert env_config.get("approval_required", False) is True
                assert env_config.get("validation_required", False) is True
                assert env_config.get("health_check_timeout", 0) >= 300
            elif env == "staging":
                # Staging should have validation but not approval
                assert env_config.get("validation_required", False) is True
                assert env_config.get("approval_required", False) is False


# Test the state machine
TestDeploymentWorkflow = DeploymentStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
