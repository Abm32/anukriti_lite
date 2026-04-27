#!/usr/bin/env python3
"""
Example: Using SynthaTrial Deployment Automation

This example demonstrates how to use the deployment automation scripts
for different scenarios and environments.
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from deploy_to_registry import (
    CIPipeline,
    DeploymentConfig,
    RegistryConfig,
    RegistryDeployer,
)


def example_basic_deployment():
    """Example: Basic deployment to staging environment"""
    print("🚀 Example: Basic Deployment to Staging")
    print("=" * 50)

    # Create deployer instance
    deployer = RegistryDeployer(verbose=True)

    # Create registry configuration
    registry = deployer.get_registry_config(
        "ghcr.io/your-org/synthatrial", token="your_github_token_here"
    )

    # Create deployment configuration
    config = DeploymentConfig(
        environment="staging",
        registry=registry,
        images=["synthatrial", "synthatrial-dev"],
        tags=["staging", "latest"],
        platforms=["linux/amd64", "linux/arm64"],
        health_check_url="https://staging.synthatrial.com/health",
    )

    # Note: This is a dry-run example - actual deployment would require valid credentials
    print(f"Registry: {registry.name}")
    print(f"Environment: {config.environment}")
    print(f"Images: {config.images}")
    print(f"Tags: {config.tags}")
    print(f"Platforms: {config.platforms}")
    print()


def example_production_deployment():
    """Example: Production deployment with approval and rollback"""
    print("🏭 Example: Production Deployment")
    print("=" * 50)

    deployer = RegistryDeployer(verbose=True)

    # Production registry configuration
    registry = deployer.get_registry_config(
        "docker.io/your-org/synthatrial",
        username="your_dockerhub_username",
        password="your_dockerhub_password",
    )

    # Production deployment configuration
    config = DeploymentConfig(
        environment="production",
        registry=registry,
        images=["synthatrial"],  # Only production image
        tags=["v1.0.0", "latest"],
        platforms=["linux/amd64", "linux/arm64"],
        health_check_url="https://synthatrial.com/health",
        rollback_enabled=True,
        pre_deploy_hooks=[
            "script:scripts/pre_production_checks.sh",
            "command:echo 'Starting production deployment'",
        ],
        post_deploy_hooks=[
            "command:echo 'Production deployment completed'",
            "script:scripts/notify_deployment.sh",
        ],
    )

    print(f"Registry: {registry.name}")
    print(f"Environment: {config.environment}")
    print(f"Images: {config.images}")
    print(f"Pre-deploy hooks: {len(config.pre_deploy_hooks)}")
    print(f"Post-deploy hooks: {len(config.post_deploy_hooks)}")
    print(f"Rollback enabled: {config.rollback_enabled}")
    print()


def example_multi_registry_deployment():
    """Example: Deploy to multiple registries"""
    print("🌐 Example: Multi-Registry Deployment")
    print("=" * 50)

    deployer = RegistryDeployer(verbose=True)

    # Define multiple registries
    registries = [
        deployer.get_registry_config("ghcr.io/your-org/synthatrial"),
        deployer.get_registry_config("docker.io/your-org/synthatrial"),
        deployer.get_registry_config(
            "your-account.dkr.ecr.us-west-2.amazonaws.com/synthatrial"
        ),
    ]

    for i, registry in enumerate(registries, 1):
        print(f"Registry {i}: {registry.name}")
        print(f"  URL: {registry.url}")
        print(f"  Auth Method: {registry.auth_method}")
        print(f"  Public: {registry.public}")
    print()


def example_cipipeline_interface():
    """Example: Using the CI/CD Pipeline interface"""
    print("⚙️  Example: CI/CD Pipeline Interface")
    print("=" * 50)

    # Create pipeline interface
    pipeline = CIPipeline(verbose=True)

    # Example build configuration
    platforms = ["linux/amd64", "linux/arm64"]
    test_types = ["unit", "integration", "property"]

    print(f"Available methods:")
    print(f"  - build_multi_arch(platforms={platforms})")
    print(f"  - run_test_suite(test_types={test_types})")
    print(f"  - push_to_registry(image_name, tags)")
    print(f"  - deploy_to_environment(env, config)")
    print()

    # Example deployment config for pipeline
    from deploy_to_registry import DeployConfig

    deploy_config = DeployConfig(
        environment="staging",
        registry_url="ghcr.io/your-org/synthatrial",
        images=["synthatrial"],
        tags=["staging"],
        platforms=platforms,
        health_check_url="https://staging.synthatrial.com/health",
    )

    print(f"Example deployment config:")
    print(f"  Environment: {deploy_config.environment}")
    print(f"  Registry: {deploy_config.registry_url}")
    print(f"  Images: {deploy_config.images}")
    print()


def example_deployment_validation():
    """Example: Validate existing deployment"""
    print("🔍 Example: Deployment Validation")
    print("=" * 50)

    deployer = RegistryDeployer(verbose=True)

    # Example validation (would require actual registry access)
    registry_url = "ghcr.io/your-org/synthatrial"
    environment = "staging"

    print(f"Validation command:")
    print(f"  python scripts/deploy_to_registry.py \\")
    print(f"    --validate-deployment \\")
    print(f"    --registry {registry_url} \\")
    print(f"    --environment {environment}")
    print()

    # Show what validation checks
    print(f"Validation checks:")
    print(f"  ✓ Registry authentication")
    print(f"  ✓ Image existence verification")
    print(f"  ✓ Health check status")
    print(f"  ✓ Deployment report generation")
    print()


def example_cleanup_operations():
    """Example: Cleanup old deployments"""
    print("🧹 Example: Cleanup Operations")
    print("=" * 50)

    deployer = RegistryDeployer(verbose=True)

    registry_url = "ghcr.io/your-org/synthatrial"
    keep_count = 5

    print(f"Cleanup command:")
    print(f"  python scripts/deploy_to_registry.py \\")
    print(f"    --cleanup \\")
    print(f"    --registry {registry_url} \\")
    print(f"    --keep-count {keep_count}")
    print()

    print(f"Cleanup operations:")
    print(f"  ✓ Remove old deployment reports (keep {keep_count} most recent)")
    print(f"  ✓ Clean up build artifacts older than 24 hours")
    print(f"  ✓ Maintain deployment history")
    print()


def main():
    """Run all examples"""
    print("SynthaTrial Deployment Automation Examples")
    print("=" * 60)
    print()

    examples = [
        example_basic_deployment,
        example_production_deployment,
        example_multi_registry_deployment,
        example_cipipeline_interface,
        example_deployment_validation,
        example_cleanup_operations,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        print()

    print("📚 Additional Resources:")
    print("  - Makefile targets: make deploy-staging, make deploy-production")
    print("  - GitHub Actions: .github/workflows/docker-build.yml")
    print("  - Documentation: root README")
    print("  - Tests: tests/test_deploy_to_registry_*.py")


if __name__ == "__main__":
    main()
