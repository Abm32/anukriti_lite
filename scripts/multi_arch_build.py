#!/usr/bin/env python3
"""
Multi-Architecture Build Orchestration Script

This script coordinates Docker builds across multiple platforms (AMD64 and ARM64),
handles platform-specific optimizations, manages build artifacts, and integrates
with the existing CI/CD infrastructure.

Features:
- Multi-platform build coordination (AMD64, ARM64)
- Platform-specific optimization handling
- Build artifact management and validation
- Integration with existing Docker infrastructure
- Comprehensive logging and error handling
- Build caching and performance optimization
- Registry push coordination
- Build status reporting

Usage:
    python scripts/multi_arch_build.py --target prod --platforms linux/amd64,linux/arm64
    python scripts/multi_arch_build.py --target dev --registry ghcr.io/org/repo --push
    python scripts/multi_arch_build.py --list-builders
    python scripts/multi_arch_build.py --cleanup
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BuildConfig:
    """Configuration for multi-architecture builds"""

    target: str
    platforms: List[str]
    dockerfile: str
    context: str
    registry: Optional[str] = None
    tags: List[str] = None
    push: bool = False
    cache_from: Optional[str] = None
    cache_to: Optional[str] = None
    build_args: Dict[str, str] = None
    labels: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.build_args is None:
            self.build_args = {}
        if self.labels is None:
            self.labels = {}


@dataclass
class BuildResult:
    """Result of a multi-architecture build"""

    success: bool
    target: str
    platforms: List[str]
    image_id: Optional[str] = None
    digest: Optional[str] = None
    size_bytes: Optional[int] = None
    build_time_seconds: Optional[float] = None
    artifacts: List[str] = None
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class PlatformOptimization:
    """Platform-specific optimization settings"""

    platform: str
    build_args: Dict[str, str]
    cache_mount: Optional[str] = None
    target_stage: Optional[str] = None

    def __post_init__(self):
        if self.build_args is None:
            self.build_args = {}


class MultiArchBuilder:
    """Multi-architecture Docker build orchestrator"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = self._setup_logging()
        self.builder_name = "synthatrial-multi-arch"
        self.workspace_root = Path(__file__).parent.parent
        self.artifacts_dir = self.workspace_root / "build_artifacts"
        self.reports_dir = self.workspace_root / "build_reports"

        # Ensure directories exist
        self.artifacts_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)

        # Platform-specific optimizations
        self.platform_optimizations = {
            "linux/amd64": PlatformOptimization(
                platform="linux/amd64",
                build_args={
                    "BUILDKIT_INLINE_CACHE": "1",
                    "TARGETPLATFORM": "linux/amd64",
                    "TARGETARCH": "amd64",
                },
                cache_mount="/tmp/.buildx-cache-amd64",
            ),
            "linux/arm64": PlatformOptimization(
                platform="linux/arm64",
                build_args={
                    "BUILDKIT_INLINE_CACHE": "1",
                    "TARGETPLATFORM": "linux/arm64",
                    "TARGETARCH": "arm64",
                },
                cache_mount="/tmp/.buildx-cache-arm64",
            ),
        }

        # Target configurations
        self.target_configs = {
            "dev": {
                "dockerfile": "docker/Dockerfile.dev",
                "context": ".",
                "cache_from": "type=gha",
                "cache_to": "type=gha,mode=max",
            },
            "prod": {
                "dockerfile": "docker/Dockerfile.prod",
                "context": ".",
                "cache_from": "type=gha",
                "cache_to": "type=gha,mode=max",
            },
            "dev-enhanced": {
                "dockerfile": "docker/Dockerfile.dev-enhanced",
                "context": ".",
                "cache_from": "type=gha",
                "cache_to": "type=gha,mode=max",
            },
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("multi_arch_builder")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _run_command(
        self,
        cmd: List[str],
        capture_output: bool = True,
        check: bool = True,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess:
        """Run a command with proper logging and error handling"""
        self.logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=check,
                timeout=timeout,
                cwd=self.workspace_root,
            )

            if self.verbose and result.stdout:
                self.logger.debug(f"Command output: {result.stdout}")

            return result

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {' '.join(cmd)}")
            self.logger.error(f"Exit code: {e.returncode}")
            if e.stdout:
                self.logger.error(f"Stdout: {e.stdout}")
            if e.stderr:
                self.logger.error(f"Stderr: {e.stderr}")
            raise

        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Command timed out: {' '.join(cmd)}")
            raise

    def check_docker_buildx(self) -> bool:
        """Check if Docker Buildx is available and properly configured"""
        try:
            # First check if Docker is available
            result = self._run_command(["docker", "--version"])
            self.logger.debug(f"Docker version: {result.stdout.strip()}")

            # Check if buildx is available
            try:
                result = self._run_command(["docker", "buildx", "version"])
                self.logger.info("Docker Buildx is available")
            except subprocess.CalledProcessError:
                self.logger.error(
                    "Docker Buildx is not available. Please install Docker Buildx plugin."
                )
                self.logger.info("Installation instructions:")
                self.logger.info(
                    "  - For Docker Desktop: Buildx is included by default"
                )
                self.logger.info(
                    "  - For Docker Engine: Install buildx plugin or use newer Docker version"
                )
                return False

            # Check current builder
            try:
                result = self._run_command(["docker", "buildx", "ls"])
                builders = result.stdout

                if self.builder_name in builders:
                    self.logger.info(f"Builder '{self.builder_name}' already exists")
                    return True
                else:
                    self.logger.info(
                        f"Builder '{self.builder_name}' not found, will create"
                    )
                    return False
            except subprocess.CalledProcessError:
                self.logger.warning("Could not list builders, but buildx is available")
                return False

        except subprocess.CalledProcessError:
            self.logger.error("Docker is not available or not properly configured")
            return False

    def setup_builder(self, platforms: List[str]) -> bool:
        """Setup multi-architecture builder"""
        try:
            self.logger.info(
                f"Setting up builder '{self.builder_name}' for platforms: {platforms}"
            )

            # Create builder if it doesn't exist
            if not self.check_docker_buildx():
                cmd = [
                    "docker",
                    "buildx",
                    "create",
                    "--name",
                    self.builder_name,
                    "--driver",
                    "docker-container",
                    "--platform",
                    ",".join(platforms),
                    "--use",
                ]
                self._run_command(cmd)
                self.logger.info(f"Created builder '{self.builder_name}'")
            else:
                # Use existing builder
                self._run_command(["docker", "buildx", "use", self.builder_name])
                self.logger.info(f"Using existing builder '{self.builder_name}'")

            # Bootstrap the builder
            self.logger.info("Bootstrapping builder...")
            self._run_command(
                ["docker", "buildx", "inspect", "--bootstrap"], timeout=300
            )

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to setup builder: {e}")
            return False

    def cleanup_builder(self) -> bool:
        """Cleanup multi-architecture builder"""
        try:
            self.logger.info(f"Cleaning up builder '{self.builder_name}'")

            # Remove builder
            self._run_command(
                ["docker", "buildx", "rm", self.builder_name], check=False
            )
            self.logger.info(f"Removed builder '{self.builder_name}'")

            # Clean up build cache
            self._run_command(["docker", "buildx", "prune", "-f"], check=False)
            self.logger.info("Cleaned up build cache")

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to cleanup builder: {e}")
            return False

    def list_builders(self) -> List[Dict[str, Any]]:
        """List available builders"""
        try:
            # First check if Docker and Buildx are available
            try:
                self._run_command(["docker", "--version"])
            except subprocess.CalledProcessError:
                self.logger.error("Docker is not available")
                return []

            try:
                self._run_command(["docker", "buildx", "version"])
            except subprocess.CalledProcessError:
                self.logger.error("Docker Buildx is not available")
                return []

            # Try with --format json first (newer Docker versions)
            try:
                result = self._run_command(
                    ["docker", "buildx", "ls", "--format", "json"]
                )
                builders = []

                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            builder_info = json.loads(line)
                            builders.append(builder_info)
                        except json.JSONDecodeError:
                            # Fallback to parsing text format
                            pass

                return builders

            except subprocess.CalledProcessError:
                # Fallback to regular format for older Docker versions
                result = self._run_command(["docker", "buildx", "ls"])
                builders = []

                # Parse text output
                lines = result.stdout.strip().split("\n")
                for i, line in enumerate(lines):
                    if i == 0:  # Skip header
                        continue

                    parts = line.split()
                    if len(parts) >= 2:
                        builder_info = {
                            "name": parts[0],
                            "driver": parts[1] if len(parts) > 1 else "unknown",
                            "status": parts[2] if len(parts) > 2 else "unknown",
                            "platforms": parts[3:] if len(parts) > 3 else [],
                        }
                        builders.append(builder_info)

                return builders

        except subprocess.CalledProcessError:
            self.logger.error("Failed to list builders")
            return []

    def get_platform_optimization(self, platform: str) -> PlatformOptimization:
        """Get platform-specific optimization settings"""
        return self.platform_optimizations.get(
            platform, PlatformOptimization(platform=platform, build_args={})
        )

    def build_config_from_target(
        self,
        target: str,
        platforms: List[str],
        registry: Optional[str] = None,
        push: bool = False,
    ) -> BuildConfig:
        """Create build configuration from target name"""
        if target not in self.target_configs:
            raise ValueError(
                f"Unknown target: {target}. Available: {list(self.target_configs.keys())}"
            )

        config = self.target_configs[target]

        # Generate tags
        tags = []
        if registry:
            base_image = f"{registry}/synthatrial"
            if target == "prod":
                tags.extend(
                    [
                        f"{base_image}:latest",
                        f"{base_image}:{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    ]
                )
            else:
                tags.extend(
                    [
                        f"{base_image}:{target}",
                        f"{base_image}:{target}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    ]
                )
        else:
            if target == "prod":
                tags.extend(
                    [
                        "synthatrial:latest",
                        f"synthatrial:{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    ]
                )
            else:
                tags.extend(
                    [
                        f"synthatrial:{target}",
                        f"synthatrial:{target}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    ]
                )

        # Build arguments
        build_args = {
            "BUILD_DATE": datetime.now().isoformat(),
            "VCS_REF": self._get_git_commit(),
            "VERSION": self._get_version(),
            "BUILDKIT_INLINE_CACHE": "1",
        }

        # Labels
        labels = {
            "org.opencontainers.image.title": "SynthaTrial",
            "org.opencontainers.image.description": "In Silico Pharmacogenomics Platform",
            "org.opencontainers.image.vendor": "SynthaTrial",
            "org.opencontainers.image.version": self._get_version(),
            "org.opencontainers.image.revision": self._get_git_commit(),
            "org.opencontainers.image.created": datetime.now().isoformat(),
            "org.opencontainers.image.source": "https://github.com/synthatrial/synthatrial",
        }

        return BuildConfig(
            target=target,
            platforms=platforms,
            dockerfile=config["dockerfile"],
            context=config["context"],
            registry=registry,
            tags=tags,
            push=push,
            cache_from=config.get("cache_from"),
            cache_to=config.get("cache_to"),
            build_args=build_args,
            labels=labels,
        )

    def _get_git_commit(self) -> str:
        """Get current git commit hash"""
        try:
            result = self._run_command(["git", "rev-parse", "HEAD"])
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"

    def _get_version(self) -> str:
        """Get version from git tag or default"""
        try:
            result = self._run_command(["git", "describe", "--tags", "--always"])
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "v0.2-beta"

    def build_multi_arch(self, config: BuildConfig) -> BuildResult:
        """Execute multi-architecture build"""
        start_time = time.time()
        result = BuildResult(
            success=False, target=config.target, platforms=config.platforms
        )

        try:
            self.logger.info(
                f"Starting multi-architecture build for target '{config.target}'"
            )
            self.logger.info(f"Platforms: {config.platforms}")
            self.logger.info(f"Dockerfile: {config.dockerfile}")

            # Setup builder
            if not self.setup_builder(config.platforms):
                result.errors.append("Failed to setup builder")
                return result

            # Build command
            cmd = [
                "docker",
                "buildx",
                "build",
                "--platform",
                ",".join(config.platforms),
                "--file",
                config.dockerfile,
            ]

            # Add tags
            for tag in config.tags:
                cmd.extend(["--tag", tag])

            # Add build arguments
            for key, value in config.build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])

            # Add labels
            for key, value in config.labels.items():
                cmd.extend(["--label", f"{key}={value}"])

            # Add cache configuration
            if config.cache_from:
                cmd.extend(["--cache-from", config.cache_from])
            if config.cache_to:
                cmd.extend(["--cache-to", config.cache_to])

            # Add push or load option
            if config.push:
                cmd.append("--push")
                self.logger.info("Will push to registry after build")
            else:
                # For multi-arch builds without push, we can't use --load
                # Instead, we'll build and export metadata
                cmd.append("--metadata-file")
                metadata_file = (
                    self.artifacts_dir
                    / f"metadata-{config.target}-{int(time.time())}.json"
                )
                cmd.append(str(metadata_file))
                result.artifacts.append(str(metadata_file))

            # Add context
            cmd.append(config.context)

            # Execute build
            self.logger.info(f"Executing build command: {' '.join(cmd)}")
            build_result = self._run_command(cmd, timeout=3600)  # 1 hour timeout

            # Parse build output for information
            if build_result.stdout:
                self._parse_build_output(build_result.stdout, result)

            result.success = True
            result.build_time_seconds = time.time() - start_time

            self.logger.info(
                f"Build completed successfully in {result.build_time_seconds:.2f} seconds"
            )

            # Generate build report
            self._generate_build_report(config, result)

            return result

        except subprocess.CalledProcessError as e:
            result.errors.append(f"Build failed: {e}")
            result.build_time_seconds = time.time() - start_time
            self.logger.error(
                f"Build failed after {result.build_time_seconds:.2f} seconds"
            )
            return result

        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            result.build_time_seconds = time.time() - start_time
            self.logger.error(f"Unexpected error during build: {e}")
            return result

    def _parse_build_output(self, output: str, result: BuildResult):
        """Parse build output to extract useful information"""
        lines = output.split("\n")

        for line in lines:
            line = line.strip()

            # Look for image ID
            if "writing image" in line.lower() and "sha256:" in line:
                parts = line.split("sha256:")
                if len(parts) > 1:
                    result.image_id = f"sha256:{parts[1].split()[0]}"

            # Look for digest (multiple patterns)
            if (
                "digest:" in line.lower() or "exporting manifest" in line.lower()
            ) and "sha256:" in line:
                parts = line.split("sha256:")
                if len(parts) > 1:
                    result.digest = f"sha256:{parts[1].split()[0]}"

            # Look for warnings
            if "warning" in line.lower():
                result.warnings.append(line)

    def _generate_build_report(self, config: BuildConfig, result: BuildResult):
        """Generate detailed build report"""
        report = {
            "build_info": {
                "timestamp": datetime.now().isoformat(),
                "target": config.target,
                "platforms": config.platforms,
                "dockerfile": config.dockerfile,
                "success": result.success,
                "build_time_seconds": result.build_time_seconds,
            },
            "config": asdict(config),
            "result": asdict(result),
            "environment": {
                "git_commit": self._get_git_commit(),
                "version": self._get_version(),
                "builder_name": self.builder_name,
            },
        }

        # Save report
        report_file = (
            self.reports_dir / f"build-report-{config.target}-{int(time.time())}.json"
        )
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        result.artifacts.append(str(report_file))
        self.logger.info(f"Build report saved to: {report_file}")

    def validate_build_artifacts(self, result: BuildResult) -> bool:
        """Validate build artifacts"""
        try:
            self.logger.info("Validating build artifacts...")

            # Check if all artifacts exist
            for artifact in result.artifacts:
                if not Path(artifact).exists():
                    self.logger.error(f"Artifact not found: {artifact}")
                    return False

            # If we have metadata file, validate it
            metadata_files = [
                a for a in result.artifacts if "metadata" in a and a.endswith(".json")
            ]
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                    self.logger.debug(f"Metadata validation passed: {metadata_file}")
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid metadata file: {metadata_file}")
                    return False

            self.logger.info("Build artifact validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Artifact validation failed: {e}")
            return False

    def push_to_registry(self, config: BuildConfig, result: BuildResult) -> bool:
        """Push built images to registry (if not already pushed)"""
        if config.push:
            self.logger.info("Images already pushed during build")
            return True

        if not config.registry:
            self.logger.warning("No registry specified, skipping push")
            return True

        try:
            self.logger.info(f"Pushing images to registry: {config.registry}")

            for tag in config.tags:
                if config.registry in tag:
                    self.logger.info(f"Pushing tag: {tag}")
                    # Note: For multi-arch images, we need to rebuild with --push
                    # This is a limitation of the current approach
                    self.logger.warning(
                        "Multi-arch push requires rebuild with --push flag"
                    )

            return True

        except Exception as e:
            self.logger.error(f"Failed to push to registry: {e}")
            return False

    def cleanup_artifacts(self, older_than_hours: int = 24) -> bool:
        """Cleanup old build artifacts"""
        try:
            self.logger.info(
                f"Cleaning up artifacts older than {older_than_hours} hours"
            )

            cutoff_time = time.time() - (older_than_hours * 3600)
            cleaned_count = 0

            for artifacts_dir in [self.artifacts_dir, self.reports_dir]:
                for file_path in artifacts_dir.glob("*"):
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                        self.logger.debug(f"Removed old artifact: {file_path}")

            self.logger.info(f"Cleaned up {cleaned_count} old artifacts")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cleanup artifacts: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Multi-Architecture Docker Build Orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build production image for multiple platforms
  python scripts/multi_arch_build.py --target prod --platforms linux/amd64,linux/arm64

  # Build and push to registry
  python scripts/multi_arch_build.py --target prod --registry ghcr.io/org/repo --push

  # Build development image
  python scripts/multi_arch_build.py --target dev --platforms linux/amd64

  # List available builders
  python scripts/multi_arch_build.py --list-builders

  # Cleanup old artifacts
  python scripts/multi_arch_build.py --cleanup --older-than-hours 48
        """,
    )

    parser.add_argument(
        "--target",
        choices=["dev", "prod", "dev-enhanced"],
        help="Build target (dev, prod, dev-enhanced)",
    )

    parser.add_argument(
        "--platforms",
        default="linux/amd64,linux/arm64",
        help="Comma-separated list of platforms (default: linux/amd64,linux/arm64)",
    )

    parser.add_argument(
        "--registry", help="Container registry URL (e.g., ghcr.io/org/repo)"
    )

    parser.add_argument(
        "--push", action="store_true", help="Push images to registry after build"
    )

    parser.add_argument(
        "--list-builders",
        action="store_true",
        help="List available Docker Buildx builders",
    )

    parser.add_argument(
        "--cleanup", action="store_true", help="Cleanup old build artifacts"
    )

    parser.add_argument(
        "--cleanup-builder",
        action="store_true",
        help="Cleanup the multi-architecture builder",
    )

    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=24,
        help="Hours threshold for artifact cleanup (default: 24)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Create builder instance
    builder = MultiArchBuilder(verbose=args.verbose)

    try:
        # Handle list builders
        if args.list_builders:
            builders = builder.list_builders()
            if builders:
                print("Available Docker Buildx builders:")
                for builder_info in builders:
                    print(f"  - {json.dumps(builder_info, indent=4)}")
            else:
                print("No builders found or failed to list builders")
            return 0

        # Handle cleanup
        if args.cleanup:
            success = builder.cleanup_artifacts(args.older_than_hours)
            return 0 if success else 1

        # Handle builder cleanup
        if args.cleanup_builder:
            success = builder.cleanup_builder()
            return 0 if success else 1

        # Require target for build operations
        if not args.target:
            parser.error("--target is required for build operations")

        # Parse platforms
        platforms = [p.strip() for p in args.platforms.split(",")]

        # Create build configuration
        config = builder.build_config_from_target(
            target=args.target,
            platforms=platforms,
            registry=args.registry,
            push=args.push,
        )

        # Execute build
        result = builder.build_multi_arch(config)

        # Validate artifacts
        if result.success:
            artifact_validation = builder.validate_build_artifacts(result)
            if not artifact_validation:
                builder.logger.warning("Artifact validation failed")

        # Print results
        if result.success:
            print(f"✅ Build completed successfully!")
            print(f"   Target: {result.target}")
            print(f"   Platforms: {', '.join(result.platforms)}")
            print(f"   Build time: {result.build_time_seconds:.2f} seconds")
            if result.image_id:
                print(f"   Image ID: {result.image_id}")
            if result.digest:
                print(f"   Digest: {result.digest}")
            if result.artifacts:
                print(f"   Artifacts: {len(result.artifacts)} files")
            if result.warnings:
                print(f"   Warnings: {len(result.warnings)}")
        else:
            print(f"❌ Build failed!")
            print(f"   Target: {result.target}")
            print(f"   Build time: {result.build_time_seconds:.2f} seconds")
            if result.errors:
                print(f"   Errors:")
                for error in result.errors:
                    print(f"     - {error}")

        return 0 if result.success else 1

    except KeyboardInterrupt:
        builder.logger.info("Build interrupted by user")
        return 130

    except Exception as e:
        builder.logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
