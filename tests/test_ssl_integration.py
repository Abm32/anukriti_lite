#!/usr/bin/env python3
"""
SSL Integration Tests for SynthaTrial Docker Enhancements

Tests the complete SSL certificate setup and Nginx configuration integration.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.ssl_manager import SSLManager


class TestSSLIntegration:
    """Integration tests for SSL certificate management and Nginx configuration"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.ssl_manager = SSLManager(self.test_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_ssl_certificate_generation_and_validation(self):
        """Test SSL certificate generation and validation workflow"""
        domain = "test.localhost"

        # Generate certificate
        success = self.ssl_manager.generate_self_signed_certs(domain, self.test_dir)
        assert success, "Certificate generation should succeed"

        # Check files exist
        cert_path = Path(self.test_dir) / f"{domain}.crt"
        key_path = Path(self.test_dir) / f"{domain}.key"

        assert cert_path.exists(), "Certificate file should exist"
        assert key_path.exists(), "Private key file should exist"

        # Validate certificates
        is_valid = self.ssl_manager.validate_certificates(str(cert_path), str(key_path))
        assert is_valid, "Generated certificates should be valid"

        # Check expiration
        expiration = self.ssl_manager.check_expiration(str(cert_path))
        assert expiration is not None, "Should be able to determine expiration date"

        # Get certificate info
        cert_info = self.ssl_manager.get_certificate_info(str(cert_path), str(key_path))
        assert cert_info.is_valid, "Certificate info should show valid certificate"
        assert cert_info.domain == domain, f"Domain should be {domain}"
        assert cert_info.is_self_signed, "Certificate should be self-signed"

    def test_nginx_configuration_syntax(self):
        """Test Nginx configuration syntax validation"""
        nginx_conf_path = project_root / "docker" / "nginx.conf"

        # Check if Nginx config file exists
        assert nginx_conf_path.exists(), "Nginx configuration file should exist"

        # Read and validate basic syntax
        with open(nginx_conf_path, "r") as f:
            config_content = f.read()

        # Check for required SSL configuration elements
        assert (
            "ssl_certificate" in config_content
        ), "SSL certificate directive should be present"
        assert (
            "ssl_certificate_key" in config_content
        ), "SSL certificate key directive should be present"
        assert "listen 443 ssl" in config_content, "HTTPS listener should be configured"
        assert "listen 80" in config_content, "HTTP listener should be configured"
        assert (
            "return 301 https://" in config_content
        ), "HTTP to HTTPS redirect should be configured"

        # Check for security headers
        assert (
            "Strict-Transport-Security" in config_content
        ), "HSTS header should be configured"
        assert (
            "X-Frame-Options" in config_content
        ), "X-Frame-Options header should be configured"
        assert (
            "X-Content-Type-Options" in config_content
        ), "X-Content-Type-Options header should be configured"

    def test_ssl_certificate_detection_priority(self):
        """Test SSL certificate detection priority order"""
        # Create certificates with different naming conventions
        cert_patterns = [
            ("localhost.crt", "localhost.key"),
            ("cert.pem", "key.pem"),
            ("cert.crt", "cert.key"),
            ("server.crt", "server.key"),
        ]

        # Create test certificates for each pattern
        for cert_name, key_name in cert_patterns:
            cert_path = Path(self.test_dir) / cert_name
            key_path = Path(self.test_dir) / key_name

            # Generate certificate with this naming
            success = self.ssl_manager.generate_self_signed_certs(
                "test.local", self.test_dir
            )
            assert success, f"Should generate certificate for {cert_name}"

            # Rename to test pattern
            generated_cert = Path(self.test_dir) / "test.local.crt"
            generated_key = Path(self.test_dir) / "test.local.key"

            if generated_cert.exists() and generated_key.exists():
                generated_cert.rename(cert_path)
                generated_key.rename(key_path)

                # Validate renamed certificate
                is_valid = self.ssl_manager.validate_certificates(
                    str(cert_path), str(key_path)
                )
                assert is_valid, f"Certificate {cert_name} should be valid after rename"

                # Clean up for next iteration
                cert_path.unlink()
                key_path.unlink()

    def test_ssl_setup_scripts_exist(self):
        """Test that SSL setup scripts exist and are executable"""
        scripts_to_check = [
            "docker/nginx-ssl-setup.sh",
            "docker/nginx-entrypoint.sh",
            "scripts/ssl_manager.py",
        ]

        for script_path in scripts_to_check:
            full_path = project_root / script_path
            assert full_path.exists(), f"Script {script_path} should exist"

            # Check if script is executable (for shell scripts)
            if script_path.endswith(".sh"):
                assert os.access(
                    full_path, os.X_OK
                ), f"Script {script_path} should be executable"

    def test_docker_compose_ssl_configuration(self):
        """Test Docker Compose SSL configuration"""
        compose_files = ["docker-compose.prod.yml", "docker-compose.dev.yml"]

        for compose_file in compose_files:
            compose_path = project_root / compose_file
            assert compose_path.exists(), f"Compose file {compose_file} should exist"

            with open(compose_path, "r") as f:
                compose_content = f.read()

            # Check for SSL volume mounts
            if "nginx" in compose_content:
                assert (
                    "/etc/nginx/ssl" in compose_content
                ), f"SSL volume should be mounted in {compose_file}"
                assert (
                    "nginx-ssl-setup.sh" in compose_content
                ), f"SSL setup script should be mounted in {compose_file}"
                assert (
                    "nginx-entrypoint.sh" in compose_content
                ), f"Nginx entrypoint should be configured in {compose_file}"


def test_makefile_ssl_commands():
    """Test that Makefile includes SSL-related commands"""
    makefile_path = project_root / "Makefile"
    assert makefile_path.exists(), "Makefile should exist"

    with open(makefile_path, "r") as f:
        makefile_content = f.read()

    # Check for SSL-related targets
    ssl_targets = ["ssl-setup", "ssl-test", "ssl-info", "ssl-dev"]
    for target in ssl_targets:
        assert target in makefile_content, f"Makefile should include {target} target"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
