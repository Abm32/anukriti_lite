#!/usr/bin/env python3
"""
Development Environment Setup Script for SynthaTrial

This script automates the setup of a complete development environment including:
- Pre-commit hooks installation and configuration
- Development dependencies validation
- Code quality tools setup
- Environment validation and health checks
- Hot reload configuration

Usage:
    python scripts/setup_dev_env.py [--validate-only] [--skip-hooks] [--verbose]

Requirements: 3.1, 3.5
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DevEnvironmentSetup:
    """Handles automated development environment setup and validation."""

    def __init__(self, verbose: bool = False, project_root: Optional[Path] = None):
        self.verbose = verbose
        self.project_root = project_root or Path(__file__).parent.parent
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def log(self, message: str, level: str = "INFO") -> None:
        """Log messages with appropriate formatting."""
        if level == "ERROR":
            self.errors.append(message)
            print(f"❌ ERROR: {message}")
        elif level == "WARNING":
            self.warnings.append(message)
            print(f"⚠️  WARNING: {message}")
        elif level == "SUCCESS":
            print(f"✅ SUCCESS: {message}")
        elif self.verbose or level == "INFO":
            print(f"ℹ️  INFO: {message}")

    def run_command(
        self, command: List[str], capture_output: bool = True
    ) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            if self.verbose:
                self.log(f"Running command: {' '.join(command)}")

            result = subprocess.run(
                command, capture_output=capture_output, text=True, cwd=self.project_root
            )

            if result.returncode == 0:
                return True, result.stdout.strip() if capture_output else ""
            else:
                error_msg = (
                    result.stderr.strip()
                    if capture_output
                    else f"Command failed with code {result.returncode}"
                )
                return False, error_msg

        except FileNotFoundError:
            return False, f"Command not found: {command[0]}"
        except Exception as e:
            return False, f"Command execution error: {str(e)}"

    def check_python_version(self) -> bool:
        """Validate Python version compatibility."""
        self.log("Checking Python version...")

        version_info = sys.version_info
        if version_info.major != 3 or version_info.minor < 10:
            self.log(
                f"Python 3.10+ required, found {version_info.major}.{version_info.minor}",
                "ERROR",
            )
            return False

        self.log(
            f"Python {version_info.major}.{version_info.minor}.{version_info.micro} - Compatible",
            "SUCCESS",
        )
        return True

    def check_git_repository(self) -> bool:
        """Validate that we're in a git repository."""
        self.log("Checking git repository...")

        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            self.log("Not in a git repository", "ERROR")
            return False

        success, output = self.run_command(["git", "status", "--porcelain"])
        if not success:
            self.log(f"Git status check failed: {output}", "ERROR")
            return False

        self.log("Git repository validated", "SUCCESS")
        return True

    def install_pre_commit(self) -> bool:
        """Install pre-commit if not already installed."""
        self.log("Checking pre-commit installation...")

        # Check if pre-commit is available
        success, _ = self.run_command(["pre-commit", "--version"])
        if not success:
            self.log("Installing pre-commit...")
            success, output = self.run_command(
                [sys.executable, "-m", "pip", "install", "pre-commit"]
            )
            if not success:
                self.log(f"Failed to install pre-commit: {output}", "ERROR")
                return False
            self.log("Pre-commit installed successfully", "SUCCESS")
        else:
            self.log("Pre-commit already installed", "SUCCESS")

        return True

    def setup_pre_commit_hooks(self) -> bool:
        """Install and configure pre-commit hooks."""
        self.log("Setting up pre-commit hooks...")

        # Check if .pre-commit-config.yaml exists
        config_file = self.project_root / ".pre-commit-config.yaml"
        if not config_file.exists():
            self.log("Pre-commit configuration file not found", "ERROR")
            return False

        # Install pre-commit hooks
        success, output = self.run_command(["pre-commit", "install"])
        if not success:
            self.log(f"Failed to install pre-commit hooks: {output}", "ERROR")
            return False

        # Install commit-msg hook for additional validation
        success, output = self.run_command(
            ["pre-commit", "install", "--hook-type", "commit-msg"]
        )
        if not success:
            self.log(f"Warning: Could not install commit-msg hook: {output}", "WARNING")

        self.log("Pre-commit hooks installed successfully", "SUCCESS")
        return True

    def validate_pre_commit_config(self) -> bool:
        """Validate pre-commit configuration."""
        self.log("Validating pre-commit configuration...")

        success, output = self.run_command(["pre-commit", "validate-config"])
        if not success:
            self.log(f"Pre-commit configuration validation failed: {output}", "ERROR")
            return False

        self.log("Pre-commit configuration is valid", "SUCCESS")
        return True

    def install_development_dependencies(self) -> bool:
        """Install additional development dependencies."""
        self.log("Installing development dependencies...")

        dev_packages = [
            "black>=23.12.0",
            "isort>=5.13.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "bandit>=1.7.5",
            "pytest-cov>=4.1.0",
            "pytest-xdist>=3.5.0",  # Parallel test execution
            "pytest-mock>=3.12.0",  # Mocking support
            "coverage>=7.4.0",  # Coverage reporting
        ]

        for package in dev_packages:
            success, output = self.run_command(
                [sys.executable, "-m", "pip", "install", package]
            )
            if not success:
                self.log(f"Failed to install {package}: {output}", "WARNING")
            elif self.verbose:
                self.log(f"Installed {package}")

        self.log("Development dependencies installation completed", "SUCCESS")
        return True

    def check_required_files(self) -> bool:
        """Check for required project files."""
        self.log("Checking required project files...")

        required_files = [
            "requirements.txt",
            "pytest.ini",
            "README.md",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "src/__init__.py",
            "tests/__init__.py",
        ]

        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)

        if missing_files:
            self.log(f"Missing required files: {', '.join(missing_files)}", "ERROR")
            return False

        self.log("All required project files found", "SUCCESS")
        return True

    def validate_docker_setup(self) -> bool:
        """Validate Docker setup and configuration."""
        self.log("Validating Docker setup...")

        # Check if Docker is available
        success, output = self.run_command(["docker", "--version"])
        if not success:
            self.log("Docker not found - Docker setup will be skipped", "WARNING")
            return True  # Not a hard requirement

        # Check if Docker Compose is available
        success, output = self.run_command(["docker", "compose", "version"])
        if not success:
            # Try legacy docker-compose
            success, output = self.run_command(["docker-compose", "--version"])
            if not success:
                self.log("Docker Compose not found", "WARNING")
                return True  # Not a hard requirement

        # Validate Docker Compose files
        compose_files = ["docker-compose.yml", "docker-compose.dev.yml"]
        for compose_file in compose_files:
            if (self.project_root / compose_file).exists():
                success, output = self.run_command(
                    ["docker", "compose", "-f", compose_file, "config"]
                )
                if not success:
                    self.log(
                        f"Invalid Docker Compose file {compose_file}: {output}",
                        "WARNING",
                    )

        self.log("Docker setup validated", "SUCCESS")
        return True

    def create_development_config(self) -> bool:
        """Create development-specific configuration files."""
        self.log("Creating development configuration...")

        # Create .env.dev if it doesn't exist
        env_dev_file = self.project_root / ".env.dev"
        if not env_dev_file.exists():
            env_content = """# Development Environment Configuration
# This file contains development-specific environment variables

# Development mode
ENVIRONMENT=development
DEBUG=true

# Hot reload settings
STREAMLIT_SERVER_RUNONFORK=true
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLECORS=false

# Development database settings
USE_MOCK_DATA=true

# Logging configuration
LOG_LEVEL=DEBUG
LOG_FORMAT=detailed

# Development API keys (use mock values for testing)
# GOOGLE_API_KEY=your_development_key_here
# PINECONE_API_KEY=your_development_key_here
"""
            env_dev_file.write_text(env_content)
            self.log("Created .env.dev file", "SUCCESS")

        # Create development-specific pytest configuration
        pytest_dev_file = self.project_root / "pytest.dev.ini"
        if not pytest_dev_file.exists():
            pytest_content = """[pytest]
# Development-specific pytest configuration
addopts =
    --verbose
    --tb=short
    --strict-markers
    --strict-config
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
    -p no:warnings

# Test discovery
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    property: Property-based test using hypothesis
    integration: Integration tests
    unit: Unit tests
    slow: Slow running tests
    fast: Fast running tests
    dev: Development-specific tests

# Minimum version
minversion = 7.0

# Filter warnings
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
"""
            pytest_dev_file.write_text(pytest_content)
            self.log("Created pytest.dev.ini file", "SUCCESS")

        return True

    def run_initial_quality_checks(self) -> bool:
        """Run initial code quality checks to validate setup."""
        self.log("Running initial code quality checks...")

        # Run pre-commit on all files (dry run)
        success, output = self.run_command(
            ["pre-commit", "run", "--all-files", "--show-diff-on-failure"]
        )
        if not success:
            self.log(
                "Pre-commit checks found issues - run 'pre-commit run --all-files' to fix",
                "WARNING",
            )
            if self.verbose:
                self.log(f"Pre-commit output: {output}")
        else:
            self.log("All pre-commit checks passed", "SUCCESS")

        return True

    def generate_setup_report(self) -> Dict:
        """Generate a comprehensive setup report."""
        report = {
            "setup_status": "success" if not self.errors else "failed",
            "timestamp": subprocess.run(
                ["date", "-Iseconds"], capture_output=True, text=True
            ).stdout.strip(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "project_root": str(self.project_root),
            "errors": self.errors,
            "warnings": self.warnings,
            "installed_tools": {},
            "next_steps": [],
        }

        # Check installed tools
        tools = ["pre-commit", "black", "isort", "flake8", "mypy", "bandit", "pytest"]
        for tool in tools:
            success, output = self.run_command([tool, "--version"])
            report["installed_tools"][tool] = output if success else "not installed"

        # Add next steps
        if not self.errors:
            report["next_steps"] = [
                "Run 'pre-commit run --all-files' to check all files",
                "Run 'pytest' to execute the test suite",
                "Run 'make quick-start' to start development environment",
                "Check root README for additional setup instructions",
            ]
        else:
            report["next_steps"] = [
                "Fix the errors listed above",
                "Re-run the setup script",
                "Check the documentation for troubleshooting",
            ]

        return report

    def setup_development_environment(self, skip_hooks: bool = False) -> bool:
        """Main setup method that orchestrates the entire process."""
        self.log("Starting development environment setup for SynthaTrial...")

        success = True

        # Core validation
        success &= self.check_python_version()
        success &= self.check_git_repository()
        success &= self.check_required_files()

        if not success:
            self.log("Core validation failed - cannot continue", "ERROR")
            return False

        # Development tools setup
        if not skip_hooks:
            success &= self.install_pre_commit()
            success &= self.setup_pre_commit_hooks()
            success &= self.validate_pre_commit_config()

        success &= self.install_development_dependencies()
        success &= self.create_development_config()

        # Optional validation (warnings only)
        self.validate_docker_setup()

        # Final quality checks
        if not skip_hooks:
            self.run_initial_quality_checks()

        return success

    def validate_environment_only(self) -> bool:
        """Validate existing environment without making changes."""
        self.log("Validating development environment...")

        success = True
        success &= self.check_python_version()
        success &= self.check_git_repository()
        success &= self.check_required_files()
        success &= self.validate_docker_setup()

        # Check if pre-commit is set up
        if (self.project_root / ".pre-commit-config.yaml").exists():
            success &= self.validate_pre_commit_config()

        return success


def main():
    """Main entry point for the development environment setup script."""
    parser = argparse.ArgumentParser(
        description="Setup and validate SynthaTrial development environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_dev_env.py                    # Full setup
  python scripts/setup_dev_env.py --validate-only    # Validation only
  python scripts/setup_dev_env.py --skip-hooks       # Skip pre-commit setup
  python scripts/setup_dev_env.py --verbose          # Detailed output
        """,
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate environment, don't make changes",
    )

    parser.add_argument(
        "--skip-hooks", action="store_true", help="Skip pre-commit hooks installation"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument(
        "--report", action="store_true", help="Generate detailed setup report"
    )

    args = parser.parse_args()

    # Initialize setup handler
    setup = DevEnvironmentSetup(verbose=args.verbose)

    try:
        if args.validate_only:
            success = setup.validate_environment_only()
        else:
            success = setup.setup_development_environment(skip_hooks=args.skip_hooks)

        # Generate report if requested
        if args.report:
            report = setup.generate_setup_report()
            report_file = setup.project_root / "dev_setup_report.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
            setup.log(f"Setup report saved to {report_file}")

        # Print summary
        if setup.errors:
            setup.log(
                f"Setup completed with {len(setup.errors)} errors and {len(setup.warnings)} warnings",
                "ERROR",
            )
            for error in setup.errors:
                print(f"  - {error}")
        elif setup.warnings:
            setup.log(
                f"Setup completed successfully with {len(setup.warnings)} warnings",
                "WARNING",
            )
            for warning in setup.warnings:
                print(f"  - {warning}")
        else:
            setup.log(
                "Development environment setup completed successfully!", "SUCCESS"
            )

        return 0 if success else 1

    except KeyboardInterrupt:
        setup.log("Setup interrupted by user", "ERROR")
        return 1
    except Exception as e:
        setup.log(f"Unexpected error during setup: {str(e)}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
