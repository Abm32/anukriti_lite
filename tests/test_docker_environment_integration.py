#!/usr/bin/env python3
"""
Docker Environment Integration Tests for SynthaTrial Docker Enhancements

Tests the integration between all Docker components, ensuring that containers,
compose files, networking, volumes, and automation work together seamlessly.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestDockerEnvironmentIntegration:
    """Integration tests for Docker environment components"""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # Create Docker environment structure
            directories = [
                "docker",
                "docker/ssl",
                "data/genomes",
                "data/chembl",
                "logs",
                "backups",
                "monitoring",
            ]

            for directory in directories:
                (workspace / directory).mkdir(parents=True, exist_ok=True)

            yield workspace

    def test_dockerfile_consistency_across_environments(self):
        """Test Dockerfile consistency across different environments"""
        print("\n🐳 Testing Dockerfile Consistency Across Environments")

        dockerfile_paths = [
            "Dockerfile",
            "docker/Dockerfile.dev",
            "docker/Dockerfile.dev-enhanced",
            "docker/Dockerfile.prod",
        ]

        dockerfile_configs = {}

        for dockerfile_path in dockerfile_paths:
            full_path = project_root / dockerfile_path

            if not full_path.exists():
                print(f"  ⚠️ Dockerfile not found: {dockerfile_path}")
                continue

            dockerfile_content = full_path.read_text()

            # Extract key configurations
            config = {
                "base_image": None,
                "python_version": None,
                "workdir": None,
                "exposed_ports": [],
                "volumes": [],
                "env_vars": [],
                "multi_stage": "FROM" in dockerfile_content
                and dockerfile_content.count("FROM") > 1,
            }

            # Parse Dockerfile content
            lines = dockerfile_content.split("\n")
            for line in lines:
                line = line.strip()

                if line.startswith("FROM"):
                    if config["base_image"] is None:  # First FROM statement
                        config["base_image"] = line.split()[1]
                        if "python" in line.lower():
                            # Extract Python version
                            parts = line.split(":")
                            if len(parts) > 1:
                                config["python_version"] = parts[1].split("-")[0]

                elif line.startswith("WORKDIR"):
                    config["workdir"] = line.split()[1]

                elif line.startswith("EXPOSE"):
                    ports = line.split()[1:]
                    config["exposed_ports"].extend(ports)

                elif line.startswith("VOLUME"):
                    volumes = line.split()[1:]
                    config["volumes"].extend(volumes)

                elif line.startswith("ENV"):
                    env_parts = line.split()[1:]
                    if env_parts:
                        config["env_vars"].append(env_parts[0])

            dockerfile_configs[dockerfile_path] = config
            print(f"  ✓ Analyzed {dockerfile_path}")

        # Verify consistency across environments
        if len(dockerfile_configs) > 1:
            base_config = list(dockerfile_configs.values())[0]

            for dockerfile_path, config in dockerfile_configs.items():
                # Python version should be consistent
                if base_config["python_version"] and config["python_version"]:
                    if base_config["python_version"] != config["python_version"]:
                        print(f"  ⚠️ Python version mismatch in {dockerfile_path}")

                # Workdir should be consistent
                if base_config["workdir"] and config["workdir"]:
                    if base_config["workdir"] != config["workdir"]:
                        print(f"  ⚠️ Workdir mismatch in {dockerfile_path}")

                # Main application port should be exposed
                if (
                    "8501" not in config["exposed_ports"]
                    and "prod" not in dockerfile_path
                ):
                    print(f"  ⚠️ Streamlit port 8501 not exposed in {dockerfile_path}")

    def test_docker_compose_service_integration(self):
        """Test Docker Compose service integration and networking"""
        print("\n🔗 Testing Docker Compose Service Integration")

        compose_files = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.dev-enhanced.yml",
            "docker-compose.prod.yml",
        ]

        compose_configs = {}

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                print(f"  ⚠️ Compose file not found: {compose_file}")
                continue

            try:
                with open(compose_path) as f:
                    compose_data = yaml.safe_load(f)

                compose_configs[compose_file] = compose_data
                print(f"  ✓ Loaded {compose_file}")

                # Validate basic structure
                assert (
                    "services" in compose_data
                ), f"{compose_file} should have services"

                services = compose_data["services"]

                # Check for main application service
                app_services = ["synthatrial", "app", "web"]
                app_service_found = any(service in services for service in app_services)

                if not app_service_found:
                    print(f"  ⚠️ No main application service found in {compose_file}")

                # Validate service configurations
                for service_name, service_config in services.items():
                    # Check for essential configurations
                    if "image" not in service_config and "build" not in service_config:
                        print(
                            f"  ⚠️ Service {service_name} has no image or build config"
                        )

                    # Check port mappings
                    if "ports" in service_config:
                        ports = service_config["ports"]
                        for port in ports:
                            if isinstance(port, str) and ":" in port:
                                host_port, container_port = port.split(":")
                                print(
                                    f"    - {service_name} maps {host_port} -> {container_port}"
                                )

                    # Check volume mounts
                    if "volumes" in service_config:
                        volumes = service_config["volumes"]
                        for volume in volumes:
                            if isinstance(volume, str) and ":" in volume:
                                host_path, container_path = volume.split(":")[:2]
                                print(
                                    f"    - {service_name} mounts {host_path} -> {container_path}"
                                )

            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {compose_file}: {e}")

        # Test service networking compatibility
        self._test_service_networking(compose_configs)

    def _test_service_networking(self, compose_configs):
        """Test service networking configuration"""
        print("\n🌐 Testing Service Networking Configuration")

        for compose_file, compose_data in compose_configs.items():
            services = compose_data.get("services", {})

            # Check for network configurations
            if "networks" in compose_data:
                networks = compose_data["networks"]
                print(f"  ✓ {compose_file} defines {len(networks)} network(s)")

            # Check service network assignments
            for service_name, service_config in services.items():
                if "networks" in service_config:
                    service_networks = service_config["networks"]
                    if isinstance(service_networks, list):
                        print(
                            f"    - {service_name} uses networks: {', '.join(service_networks)}"
                        )
                    elif isinstance(service_networks, dict):
                        print(
                            f"    - {service_name} uses {len(service_networks)} network(s)"
                        )

                # Check for depends_on relationships
                if "depends_on" in service_config:
                    dependencies = service_config["depends_on"]
                    if isinstance(dependencies, list):
                        print(
                            f"    - {service_name} depends on: {', '.join(dependencies)}"
                        )
                    elif isinstance(dependencies, dict):
                        print(
                            f"    - {service_name} depends on: {', '.join(dependencies.keys())}"
                        )

    def test_volume_mount_integration(self):
        """Test volume mount integration across environments"""
        print("\n💾 Testing Volume Mount Integration")

        compose_files = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml",
        ]

        volume_mappings = {}

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                continue

            with open(compose_path) as f:
                compose_data = yaml.safe_load(f)

            services = compose_data.get("services", {})
            file_volumes = []

            for service_name, service_config in services.items():
                if "volumes" in service_config:
                    volumes = service_config["volumes"]

                    for volume in volumes:
                        if isinstance(volume, str) and ":" in volume:
                            host_path, container_path = volume.split(":")[:2]
                            file_volumes.append(
                                {
                                    "service": service_name,
                                    "host_path": host_path,
                                    "container_path": container_path,
                                    "type": self._classify_volume_type(host_path),
                                }
                            )

            volume_mappings[compose_file] = file_volumes

        # Analyze volume consistency
        self._analyze_volume_consistency(volume_mappings)

    def _classify_volume_type(self, host_path):
        """Classify volume type based on host path"""
        if host_path.startswith("./") or host_path.startswith("../"):
            return "relative_bind"
        elif host_path.startswith("/"):
            return "absolute_bind"
        elif "/" not in host_path:
            return "named_volume"
        else:
            return "unknown"

    def _analyze_volume_consistency(self, volume_mappings):
        """Analyze volume consistency across environments"""
        print("\n📊 Analyzing Volume Consistency")

        # Essential volumes that should be present
        essential_volumes = ["data", "ssl", "logs"]

        for compose_file, volumes in volume_mappings.items():
            print(f"\n  {compose_file}:")

            volume_types = {}
            for volume in volumes:
                vol_type = volume["type"]
                if vol_type not in volume_types:
                    volume_types[vol_type] = 0
                volume_types[vol_type] += 1

                print(
                    f"    - {volume['service']}: {volume['host_path']} -> {volume['container_path']} ({vol_type})"
                )

            # Check for essential volume coverage
            for essential in essential_volumes:
                essential_found = any(
                    essential in vol["host_path"] or essential in vol["container_path"]
                    for vol in volumes
                )
                if essential_found:
                    print(f"    ✓ {essential} volume configured")
                else:
                    print(f"    ⚠️ {essential} volume not found")

    def test_environment_variable_integration(self):
        """Test environment variable integration across Docker environments"""
        print("\n🔧 Testing Environment Variable Integration")

        # Check .env file
        env_file_path = project_root / ".env"
        env_example_path = project_root / ".env.example"

        if env_example_path.exists():
            with open(env_example_path) as f:
                env_example_content = f.read()

            # Extract environment variables from example
            env_vars = []
            for line in env_example_content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    var_name = line.split("=")[0]
                    env_vars.append(var_name)

            print(f"  ✓ Found {len(env_vars)} environment variables in .env.example")

            # Check if variables are used in compose files
            self._check_env_var_usage(env_vars)

        else:
            print("  ⚠️ .env.example file not found")

    def _check_env_var_usage(self, env_vars):
        """Check environment variable usage in compose files"""
        compose_files = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml",
        ]

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                continue

            compose_content = compose_path.read_text()

            used_vars = []
            for var in env_vars:
                if f"${{{var}}}" in compose_content or f"${var}" in compose_content:
                    used_vars.append(var)

            if used_vars:
                print(f"    {compose_file} uses: {', '.join(used_vars)}")

    @patch("subprocess.run")
    def test_container_health_check_integration(self, mock_run):
        """Test container health check integration"""
        print("\n🏥 Testing Container Health Check Integration")

        # Mock Docker commands
        mock_run.return_value = Mock(returncode=0, stdout="healthy", stderr="")

        compose_files = ["docker-compose.yml", "docker-compose.prod.yml"]

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                continue

            with open(compose_path) as f:
                compose_data = yaml.safe_load(f)

            services = compose_data.get("services", {})

            for service_name, service_config in services.items():
                # Check for health check configuration
                if "healthcheck" in service_config:
                    healthcheck = service_config["healthcheck"]
                    print(f"  ✓ {service_name} has health check configured")

                    # Validate health check structure
                    required_fields = ["test"]
                    for field in required_fields:
                        if field not in healthcheck:
                            print(f"    ⚠️ Missing {field} in health check")

                    # Check health check command
                    if "test" in healthcheck:
                        test_cmd = healthcheck["test"]
                        if isinstance(test_cmd, list) and len(test_cmd) > 1:
                            print(f"    - Test: {' '.join(test_cmd[1:])}")
                        elif isinstance(test_cmd, str):
                            print(f"    - Test: {test_cmd}")

    def test_docker_entrypoint_integration(self):
        """Test Docker entrypoint script integration"""
        print("\n🚀 Testing Docker Entrypoint Integration")

        entrypoint_files = ["docker-entrypoint.sh", "docker/nginx-entrypoint.sh"]

        for entrypoint_file in entrypoint_files:
            entrypoint_path = project_root / entrypoint_file

            if not entrypoint_path.exists():
                print(f"  ⚠️ Entrypoint not found: {entrypoint_file}")
                continue

            # Check if file is executable
            if not os.access(entrypoint_path, os.X_OK):
                print(f"  ⚠️ Entrypoint not executable: {entrypoint_file}")
                continue

            entrypoint_content = entrypoint_path.read_text()

            # Check for essential entrypoint features
            features = {
                "shebang": entrypoint_content.startswith("#!"),
                "error_handling": "set -e" in entrypoint_content,
                "environment_setup": any(
                    keyword in entrypoint_content
                    for keyword in ["export", "ENV", "source"]
                ),
                "data_validation": any(
                    keyword in entrypoint_content
                    for keyword in ["validate", "check", "verify"]
                ),
                "ssl_setup": "ssl" in entrypoint_content.lower(),
                "exec_command": "exec" in entrypoint_content,
            }

            print(f"  ✓ {entrypoint_file}:")
            for feature, present in features.items():
                status = "✓" if present else "⚠️"
                print(f"    {status} {feature.replace('_', ' ').title()}")

    def test_docker_build_context_integration(self):
        """Test Docker build context integration"""
        print("\n🏗️ Testing Docker Build Context Integration")

        # Check .dockerignore file
        dockerignore_path = project_root / ".dockerignore"

        if dockerignore_path.exists():
            dockerignore_content = dockerignore_path.read_text()
            ignored_patterns = [
                line.strip()
                for line in dockerignore_content.split("\n")
                if line.strip() and not line.startswith("#")
            ]

            print(f"  ✓ .dockerignore excludes {len(ignored_patterns)} patterns")

            # Check for common exclusions
            common_exclusions = [
                "*.git*",
                "node_modules",
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                "tests",
                "docs",
            ]

            for exclusion in common_exclusions:
                if any(exclusion in pattern for pattern in ignored_patterns):
                    print(f"    ✓ Excludes {exclusion}")

        else:
            print("  ⚠️ .dockerignore file not found")

        # Check build context size implications
        self._analyze_build_context()

    def _analyze_build_context(self):
        """Analyze Docker build context size and efficiency"""
        print("\n📏 Analyzing Build Context")

        # Estimate build context size
        total_size = 0
        file_count = 0

        for root, dirs, files in os.walk(project_root):
            # Skip common excluded directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in ["node_modules", "__pycache__"]
            ]

            for file in files:
                file_path = Path(root) / file
                try:
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    file_count += 1
                except (OSError, PermissionError):
                    pass

        total_size_mb = total_size / (1024 * 1024)
        print(
            f"  📊 Estimated build context: {total_size_mb:.1f} MB ({file_count} files)"
        )

        if total_size_mb > 100:
            print("  ⚠️ Large build context - consider optimizing .dockerignore")
        elif total_size_mb > 50:
            print("  ⚠️ Moderate build context size")
        else:
            print("  ✓ Reasonable build context size")

    def test_multi_stage_build_integration(self):
        """Test multi-stage build integration"""
        print("\n🏭 Testing Multi-Stage Build Integration")

        dockerfile_paths = ["Dockerfile", "docker/Dockerfile.prod"]

        for dockerfile_path in dockerfile_paths:
            full_path = project_root / dockerfile_path

            if not full_path.exists():
                continue

            dockerfile_content = full_path.read_text()

            # Count FROM statements (indicates multi-stage)
            from_count = dockerfile_content.count("FROM")

            if from_count > 1:
                print(
                    f"  ✓ {dockerfile_path} uses multi-stage build ({from_count} stages)"
                )

                # Extract stage names
                stages = []
                lines = dockerfile_content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("FROM"):
                        parts = line.split()
                        if "AS" in parts:
                            as_index = parts.index("AS")
                            if as_index + 1 < len(parts):
                                stages.append(parts[as_index + 1])

                if stages:
                    print(f"    Stages: {', '.join(stages)}")

                # Check for COPY --from usage
                copy_from_count = dockerfile_content.count("COPY --from=")
                if copy_from_count > 0:
                    print(f"    ✓ Uses {copy_from_count} inter-stage copies")

            else:
                print(f"  ⚠️ {dockerfile_path} uses single-stage build")

    def test_container_resource_limits_integration(self):
        """Test container resource limits integration"""
        print("\n⚡ Testing Container Resource Limits Integration")

        compose_files = ["docker-compose.prod.yml", "docker-compose.yml"]

        for compose_file in compose_files:
            compose_path = project_root / compose_file

            if not compose_path.exists():
                continue

            with open(compose_path) as f:
                compose_data = yaml.safe_load(f)

            services = compose_data.get("services", {})

            print(f"\n  {compose_file}:")

            for service_name, service_config in services.items():
                resource_config = {}

                # Check for resource limits (Docker Compose v3+ format)
                if (
                    "deploy" in service_config
                    and "resources" in service_config["deploy"]
                ):
                    resources = service_config["deploy"]["resources"]
                    if "limits" in resources:
                        resource_config["limits"] = resources["limits"]
                    if "reservations" in resources:
                        resource_config["reservations"] = resources["reservations"]

                # Check for legacy resource limits
                legacy_limits = [
                    "mem_limit",
                    "memswap_limit",
                    "cpu_quota",
                    "cpu_shares",
                ]
                for limit in legacy_limits:
                    if limit in service_config:
                        resource_config[limit] = service_config[limit]

                if resource_config:
                    print(
                        f"    ✓ {service_name} has resource limits: {resource_config}"
                    )
                else:
                    print(f"    ⚠️ {service_name} has no resource limits")


def run_docker_environment_integration_tests():
    """Run all Docker environment integration tests"""
    print("🧪 Running Docker Environment Integration Tests")
    print("=" * 80)

    # Run pytest with verbose output
    pytest_args = [__file__, "-v", "--tb=short"]

    result = pytest.main(pytest_args)

    print("\n" + "=" * 80)
    if result == 0:
        print("✅ All Docker environment integration tests passed!")
    else:
        print("❌ Some Docker environment integration tests failed")

    return result == 0


if __name__ == "__main__":
    success = run_docker_environment_integration_tests()
    sys.exit(0 if success else 1)
