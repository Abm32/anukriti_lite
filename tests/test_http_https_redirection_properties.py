#!/usr/bin/env python3
"""
Property-Based Tests for HTTP to HTTPS Redirection

This module contains property-based tests for the HTTP to HTTPS redirection functionality
in the Nginx configuration, validating universal properties across different URL patterns
and request types.

Tests validate:
- Property 3: HTTP to HTTPS Redirection

Author: SynthaTrial Development Team
Version: 0.2 Beta
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pytest
import requests
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

# Add the project root to the Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Custom strategies for generating test data
@composite
def http_url_patterns(draw):
    """Generate various HTTP URL patterns for testing redirection"""
    # Base components
    schemes = ["http"]  # Only HTTP for redirection testing
    hosts = ["localhost", "127.0.0.1", "synthatrial.local", "test.local"]
    ports = [80, 8080, 3000]  # Common HTTP ports

    # Path components
    path_segments = st.lists(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Ll", "Lu", "Nd"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
            min_size=1,
            max_size=10,
        ),
        min_size=0,
        max_size=3,
    )

    # Query parameters
    query_params = st.dictionaries(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8),
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=0, max_size=10
        ),
        min_size=0,
        max_size=3,
    )

    scheme = draw(st.sampled_from(schemes))
    host = draw(st.sampled_from(hosts))
    port = draw(st.sampled_from(ports))
    segments = draw(path_segments)
    params = draw(query_params)

    # Build URL
    path = "/" + "/".join(segments) if segments else "/"
    query = "&".join([f"{k}={v}" for k, v in params.items()]) if params else ""

    url = f"{scheme}://{host}:{port}{path}"
    if query:
        url += f"?{query}"

    return {
        "url": url,
        "scheme": scheme,
        "host": host,
        "port": port,
        "path": path,
        "query": query,
    }


@composite
def api_endpoint_patterns(draw):
    """Generate API endpoint patterns that should be redirected"""
    base_paths = [
        "/api/v1/drugs",
        "/api/v1/patients",
        "/api/v1/analysis",
        "/api/status",
        "/_stcore/stream",
        "/_stcore/health",
        "/static/css/main.css",
        "/static/js/app.js",
        "/favicon.ico",
        "/health",  # This is the actual health check endpoint
    ]

    base_path = draw(st.sampled_from(base_paths))

    # Add optional query parameters
    params = draw(
        st.dictionaries(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8
            ),
            min_size=0,
            max_size=2,
        )
    )

    query = "&".join([f"{k}={v}" for k, v in params.items()]) if params else ""

    url = f"http://localhost{base_path}"
    if query:
        url += f"?{query}"

    return {
        "url": url,
        "path": base_path,
        "query": query,
        "is_health_check": base_path == "/health",  # Only exact /health path
    }


class MockNginxRedirectionTester:
    """Mock tester for Nginx HTTP to HTTPS redirection behavior"""

    def __init__(self):
        self.nginx_conf_path = project_root / "docker" / "nginx.conf"
        self.redirection_rules = self._parse_nginx_config()

    def _parse_nginx_config(self) -> Dict[str, str]:
        """Parse Nginx configuration to extract redirection rules"""
        if not self.nginx_conf_path.exists():
            return {}

        with open(self.nginx_conf_path, "r") as f:
            config_content = f.read()

        rules = {}

        # Check for HTTP to HTTPS redirection
        if "return 301 https://" in config_content:
            rules["http_redirect"] = "https"

        # Check for health check exception
        if "location /health" in config_content and "proxy_pass" in config_content:
            rules["health_exception"] = True

        return rules

    def simulate_http_request(self, url: str) -> Dict[str, any]:
        """Simulate HTTP request and return expected response based on Nginx config"""
        parsed = urlparse(url)

        # Health check exception - should not redirect (only exact /health path)
        if parsed.path == "/health" and self.redirection_rules.get("health_exception"):
            return {
                "status_code": 200,
                "redirected": False,
                "final_url": url,
                "headers": {"content-type": "application/json"},
            }

        # All other HTTP requests should redirect to HTTPS
        if (
            parsed.scheme == "http"
            and self.redirection_rules.get("http_redirect") == "https"
        ):
            https_url = url.replace("http://", "https://", 1)
            # Handle port changes (80 -> 443)
            if ":80/" in https_url or https_url.endswith(":80"):
                https_url = https_url.replace(":80", ":443")
            elif "://localhost/" in https_url or https_url.endswith("://localhost"):
                https_url = https_url.replace("://localhost", "://localhost:443")

            return {
                "status_code": 301,
                "redirected": True,
                "final_url": https_url,
                "headers": {"location": https_url},
            }

        # Default response for non-redirected requests
        return {
            "status_code": 200,
            "redirected": False,
            "final_url": url,
            "headers": {},
        }

    def validate_redirection_response(
        self, response: Dict[str, any], original_url: str
    ) -> bool:
        """Validate that redirection response follows expected patterns"""
        parsed_original = urlparse(original_url)

        # Health check should not redirect (only exact /health path)
        if parsed_original.path == "/health":
            return not response["redirected"] and response["status_code"] == 200

        # HTTP requests should redirect to HTTPS
        if parsed_original.scheme == "http":
            if not response["redirected"]:
                return False

            if response["status_code"] != 301:
                return False

            # Check that redirect URL is HTTPS
            parsed_final = urlparse(response["final_url"])
            if parsed_final.scheme != "https":
                return False

            # Check that host and path are preserved
            if (
                parsed_final.netloc.split(":")[0]
                != parsed_original.netloc.split(":")[0]
            ):
                return False

            if parsed_final.path != parsed_original.path:
                return False

            if parsed_final.query != parsed_original.query:
                return False

            return True

        return True


class TestHTTPSRedirectionProperties:
    """Property-based tests for HTTP to HTTPS redirection functionality"""

    def setup_method(self):
        """Setup test environment for each test method"""
        self.tester = MockNginxRedirectionTester()

    @pytest.mark.property
    @pytest.mark.http_redirection
    @given(url_data=http_url_patterns())
    @settings(max_examples=4, deadline=6000)  # Reduced examples for faster execution
    @example(
        url_data={
            "url": "http://localhost:80/",
            "scheme": "http",
            "host": "localhost",
            "port": 80,
            "path": "/",
            "query": "",
        }
    )
    @example(
        url_data={
            "url": "http://localhost:80/app?param=value",
            "scheme": "http",
            "host": "localhost",
            "port": 80,
            "path": "/app",
            "query": "param=value",
        }
    )
    @example(
        url_data={
            "url": "http://127.0.0.1:80/api/v1/drugs",
            "scheme": "http",
            "host": "127.0.0.1",
            "port": 80,
            "path": "/api/v1/drugs",
            "query": "",
        }
    )
    def test_property_3_http_to_https_redirection(self, url_data):
        """
        **Feature: docker-enhancements, Property 3: HTTP to HTTPS Redirection**

        For any HTTP request made to an SSL-enabled endpoint, the system should
        automatically redirect to the corresponding HTTPS URL with proper status codes.

        **Validates: Requirements 1.5**
        """
        url = url_data["url"]

        # Assume valid URL structure
        assume(url_data["scheme"] == "http")
        assume(len(url_data["host"]) > 0)
        assume(url_data["port"] in [80, 8080, 3000])

        # Property: HTTP requests should be redirected to HTTPS
        response = self.tester.simulate_http_request(url)

        # Validate redirection behavior
        is_valid = self.tester.validate_redirection_response(response, url)
        assert (
            is_valid
        ), f"Invalid redirection behavior for URL: {url}, Response: {response}"

        # Property: Non-health-check HTTP requests should return 301 status
        if url_data["path"] != "/health":
            assert (
                response["status_code"] == 301
            ), f"Expected 301 redirect for {url}, got {response['status_code']}"
            assert response["redirected"], f"Expected redirection for {url}"

            # Property: Redirected URL should be HTTPS
            final_parsed = urlparse(response["final_url"])
            assert (
                final_parsed.scheme == "https"
            ), f"Redirect should be to HTTPS: {response['final_url']}"

            # Property: Host should be preserved in redirection
            original_host = url_data["host"]
            final_host = final_parsed.netloc.split(":")[0]
            assert (
                final_host == original_host
            ), f"Host should be preserved: {original_host} -> {final_host}"

            # Property: Path should be preserved in redirection
            assert (
                final_parsed.path == url_data["path"]
            ), f"Path should be preserved: {url_data['path']} -> {final_parsed.path}"

            # Property: Query parameters should be preserved in redirection
            assert (
                final_parsed.query == url_data["query"]
            ), f"Query should be preserved: {url_data['query']} -> {final_parsed.query}"

        # Property: Health check requests should not be redirected
        else:
            assert not response[
                "redirected"
            ], f"Health check should not be redirected: {url}"
            assert (
                response["status_code"] == 200
            ), f"Health check should return 200: {url}"

    @pytest.mark.property
    @pytest.mark.api_redirection
    @given(endpoint_data=api_endpoint_patterns())
    @settings(max_examples=3, deadline=5000)  # Reduced examples for faster execution
    @example(
        endpoint_data={
            "url": "http://localhost/health",
            "path": "/health",
            "query": "",
            "is_health_check": True,
        }
    )
    @example(
        endpoint_data={
            "url": "http://localhost/api/v1/drugs",
            "path": "/api/v1/drugs",
            "query": "",
            "is_health_check": False,
        }
    )
    @example(
        endpoint_data={
            "url": "http://localhost/_stcore/stream",
            "path": "/_stcore/stream",
            "query": "",
            "is_health_check": False,
        }
    )
    def test_property_api_endpoint_redirection_behavior(self, endpoint_data):
        """
        **Feature: docker-enhancements, Property 3: HTTP to HTTPS Redirection - API Endpoints**

        API endpoints should follow consistent redirection rules, with health checks
        being exempt from redirection while other endpoints are redirected to HTTPS.

        **Validates: Requirements 1.5**
        """
        url = endpoint_data["url"]
        is_health_check = endpoint_data["is_health_check"]

        # Property: API endpoint redirection should be consistent
        response = self.tester.simulate_http_request(url)

        if is_health_check:
            # Property: Health check endpoints should not redirect
            assert not response[
                "redirected"
            ], f"Health check endpoint should not redirect: {url}"
            assert (
                response["status_code"] == 200
            ), f"Health check should return 200: {url}"
            assert (
                response["final_url"] == url
            ), f"Health check URL should not change: {url}"
        else:
            # Property: Non-health API endpoints should redirect to HTTPS
            assert response[
                "redirected"
            ], f"API endpoint should redirect to HTTPS: {url}"
            assert (
                response["status_code"] == 301
            ), f"API endpoint should return 301: {url}"

            # Property: HTTPS URL should be properly formed
            final_parsed = urlparse(response["final_url"])
            assert (
                final_parsed.scheme == "https"
            ), f"API redirect should be to HTTPS: {response['final_url']}"

            # Property: API path should be preserved
            original_parsed = urlparse(url)
            assert (
                final_parsed.path == original_parsed.path
            ), f"API path should be preserved: {original_parsed.path} -> {final_parsed.path}"

    @pytest.mark.property
    @pytest.mark.redirection_consistency
    @given(url_data=http_url_patterns())
    @settings(max_examples=3, deadline=4000)  # Reduced examples for faster execution
    @example(
        url_data={
            "url": "http://localhost:80/",
            "scheme": "http",
            "host": "localhost",
            "port": 80,
            "path": "/",
            "query": "",
        }
    )
    def test_property_redirection_consistency(self, url_data):
        """
        **Feature: docker-enhancements, Property: Redirection Consistency**

        HTTP to HTTPS redirection should be consistent across multiple requests
        for the same URL pattern.
        """
        url = url_data["url"]

        assume(url_data["scheme"] == "http")
        assume(len(url_data["host"]) > 0)

        # Property: Multiple requests should produce consistent redirection behavior
        responses = []
        for _ in range(3):
            response = self.tester.simulate_http_request(url)
            responses.append(response)

        # All responses should be identical
        first_response = responses[0]
        for response in responses[1:]:
            assert (
                response["status_code"] == first_response["status_code"]
            ), f"Inconsistent status codes: {[r['status_code'] for r in responses]}"
            assert (
                response["redirected"] == first_response["redirected"]
            ), f"Inconsistent redirection behavior: {[r['redirected'] for r in responses]}"
            assert (
                response["final_url"] == first_response["final_url"]
            ), f"Inconsistent final URLs: {[r['final_url'] for r in responses]}"

    @pytest.mark.property
    @pytest.mark.security_headers
    def test_property_security_headers_in_redirection(self):
        """
        **Feature: docker-enhancements, Property: Security Headers in Redirection**

        HTTP redirection responses should include appropriate security headers
        as configured in the Nginx setup.
        """
        # Test with a standard HTTP request
        url = "http://localhost:80/"
        response = self.tester.simulate_http_request(url)

        # Property: Redirection should occur
        assert response["redirected"], f"Expected redirection for {url}"
        assert response["status_code"] == 301, f"Expected 301 status for {url}"

        # Property: Security headers should be present (simulated based on Nginx config)
        # Note: In real implementation, these would come from actual HTTP response headers
        # For mock testing, we verify the configuration includes security headers
        nginx_config_path = project_root / "docker" / "nginx.conf"
        if nginx_config_path.exists():
            with open(nginx_config_path, "r") as f:
                config_content = f.read()

            # Verify security headers are configured
            security_headers = [
                "X-Frame-Options",
                "X-Content-Type-Options",
                "X-XSS-Protection",
                "Referrer-Policy",
            ]

            for header in security_headers:
                assert (
                    header in config_content
                ), f"Security header {header} should be configured in Nginx"

    @pytest.mark.property
    @pytest.mark.edge_cases
    def test_property_edge_case_url_patterns(self):
        """
        **Feature: docker-enhancements, Property: Edge Case URL Patterns**

        Redirection should handle edge cases like empty paths, special characters,
        and malformed URLs gracefully.
        """
        edge_case_urls = [
            "http://localhost/",
            "http://localhost",
            "http://localhost:80",
            "http://localhost:80/",
            "http://localhost/path/with/multiple/segments",
            "http://localhost/path?query=value&other=param",
            "http://localhost/path#fragment",  # Fragment should be preserved
        ]

        for url in edge_case_urls:
            # Property: All edge case URLs should be handled consistently
            response = self.tester.simulate_http_request(url)

            # Should redirect unless it's a health check
            parsed = urlparse(url)
            if parsed.path != "/health":
                assert response["redirected"], f"Edge case URL should redirect: {url}"
                assert (
                    response["status_code"] == 301
                ), f"Edge case URL should return 301: {url}"

                # Final URL should be HTTPS
                final_parsed = urlparse(response["final_url"])
                assert (
                    final_parsed.scheme == "https"
                ), f"Edge case redirect should be HTTPS: {url}"


class TestNginxConfigurationValidation:
    """Tests to validate Nginx configuration for HTTP to HTTPS redirection"""

    def test_nginx_config_redirection_rules(self):
        """Test that Nginx configuration contains proper redirection rules"""
        nginx_conf_path = project_root / "docker" / "nginx.conf"

        assert nginx_conf_path.exists(), "Nginx configuration file should exist"

        with open(nginx_conf_path, "r") as f:
            config_content = f.read()

        # Property: HTTP server block should exist
        assert "listen 80;" in config_content, "HTTP listener should be configured"

        # Property: HTTPS server block should exist
        assert "listen 443 ssl" in config_content, "HTTPS listener should be configured"

        # Property: HTTP to HTTPS redirection should be configured
        assert (
            "return 301 https://" in config_content
        ), "HTTP to HTTPS redirect should be configured"

        # Property: Health check exception should be configured
        assert (
            "location /health" in config_content
        ), "Health check location should be configured"

        # Property: Security headers should be configured
        security_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
        ]

        for header in security_headers:
            assert (
                header in config_content
            ), f"Security header {header} should be configured"

    def test_nginx_config_ssl_configuration(self):
        """Test that SSL configuration is properly set up for HTTPS"""
        nginx_conf_path = project_root / "docker" / "nginx.conf"

        with open(nginx_conf_path, "r") as f:
            config_content = f.read()

        # Property: SSL certificate paths should be configured
        assert (
            "ssl_certificate" in config_content
        ), "SSL certificate should be configured"
        assert (
            "ssl_certificate_key" in config_content
        ), "SSL certificate key should be configured"

        # Property: SSL protocols should be configured
        assert "ssl_protocols" in config_content, "SSL protocols should be configured"

        # Property: SSL ciphers should be configured
        assert "ssl_ciphers" in config_content, "SSL ciphers should be configured"

        # Property: HSTS header should be configured for HTTPS
        assert (
            "Strict-Transport-Security" in config_content
        ), "HSTS header should be configured"


if __name__ == "__main__":
    # Run the property-based tests
    pytest.main([__file__, "-v", "--tb=short"])
