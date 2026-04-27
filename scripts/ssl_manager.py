#!/usr/bin/env python3
"""
SSL Certificate Manager for SynthaTrial Docker Enhancements

This module provides automated SSL certificate management including:
- Self-signed certificate generation for development
- Certificate validation and integrity checking
- Expiration monitoring and renewal support
- Production certificate setup guidance

Author: SynthaTrial Development Team
Version: 0.2 Beta
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add the project root to the Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class SSLCertificate:
    """Data model for SSL certificate information"""

    cert_path: str
    key_path: str
    domain: str
    expiration_date: Optional[datetime]
    is_self_signed: bool
    is_valid: bool
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SSLManager:
    """
    SSL Certificate Manager for automated certificate operations

    Provides functionality for:
    - Generating self-signed certificates for development
    - Validating certificate integrity and expiration
    - Setting up certificate renewal workflows
    - Managing certificate file permissions and security
    """

    def __init__(self, default_output_dir: str = "docker/ssl"):
        """
        Initialize SSL Manager

        Args:
            default_output_dir: Default directory for certificate storage
        """
        self.default_output_dir = Path(default_output_dir)
        self.logger = logging.getLogger(f"{__name__}.SSLManager")

        # Ensure output directory exists
        self.default_output_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed_certs(
        self, domain: str, output_dir: Optional[str] = None
    ) -> bool:
        """
        Generate self-signed SSL certificates for development use

        Args:
            domain: Domain name for the certificate (e.g., 'localhost', 'synthatrial.local')
            output_dir: Directory to store certificates (uses default if None)

        Returns:
            bool: True if certificates were generated successfully, False otherwise
        """
        try:
            # Use provided output directory or default
            cert_dir = Path(output_dir) if output_dir else self.default_output_dir
            cert_dir.mkdir(parents=True, exist_ok=True)

            # Define certificate file paths
            cert_path = cert_dir / f"{domain}.crt"
            key_path = cert_dir / f"{domain}.key"

            self.logger.info(f"Generating self-signed certificate for domain: {domain}")
            self.logger.info(f"Certificate will be saved to: {cert_path}")
            self.logger.info(f"Private key will be saved to: {key_path}")

            # Create OpenSSL configuration for the certificate
            config_content = self._create_openssl_config(domain)

            # Write config to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".conf", delete=False
            ) as config_file:
                config_file.write(config_content)
                config_path = config_file.name

            try:
                # Generate private key
                key_cmd = ["openssl", "genrsa", "-out", str(key_path), "2048"]

                result = subprocess.run(
                    key_cmd, capture_output=True, text=True, check=True
                )
                self.logger.info("Private key generated successfully")

                # Generate certificate signing request and self-signed certificate
                cert_cmd = [
                    "openssl",
                    "req",
                    "-new",
                    "-x509",
                    "-key",
                    str(key_path),
                    "-out",
                    str(cert_path),
                    "-days",
                    "365",
                    "-config",
                    config_path,
                ]

                result = subprocess.run(
                    cert_cmd, capture_output=True, text=True, check=True
                )
                self.logger.info("Self-signed certificate generated successfully")

                # Set appropriate file permissions (readable by owner only)
                os.chmod(key_path, 0o600)  # Private key: owner read/write only
                os.chmod(cert_path, 0o644)  # Certificate: owner read/write, others read

                # Validate the generated certificates
                if self.validate_certificates(str(cert_path), str(key_path)):
                    self.logger.info(
                        f"Certificate validation successful for domain: {domain}"
                    )
                    return True
                else:
                    self.logger.error("Generated certificate failed validation")
                    return False

            finally:
                # Clean up temporary config file
                os.unlink(config_path)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"OpenSSL command failed: {e}")
            self.logger.error(f"Command output: {e.stdout}")
            self.logger.error(f"Command error: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to generate self-signed certificates: {e}")
            return False

    def validate_certificates(self, cert_path: str, key_path: str) -> bool:
        """
        Validate SSL certificate and private key integrity

        Args:
            cert_path: Path to the certificate file
            key_path: Path to the private key file

        Returns:
            bool: True if certificates are valid, False otherwise
        """
        try:
            cert_file = Path(cert_path)
            key_file = Path(key_path)

            # Check if files exist
            if not cert_file.exists():
                self.logger.error(f"Certificate file not found: {cert_path}")
                return False

            if not key_file.exists():
                self.logger.error(f"Private key file not found: {key_path}")
                return False

            # Validate certificate format and content
            cert_cmd = ["openssl", "x509", "-in", cert_path, "-text", "-noout"]
            result = subprocess.run(cert_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"Certificate validation failed: {result.stderr}")
                return False

            # Validate private key format
            key_cmd = ["openssl", "rsa", "-in", key_path, "-check", "-noout"]
            result = subprocess.run(key_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"Private key validation failed: {result.stderr}")
                return False

            # Verify that certificate and private key match
            cert_modulus_cmd = [
                "openssl",
                "x509",
                "-noout",
                "-modulus",
                "-in",
                cert_path,
            ]
            key_modulus_cmd = ["openssl", "rsa", "-noout", "-modulus", "-in", key_path]

            cert_result = subprocess.run(
                cert_modulus_cmd, capture_output=True, text=True
            )
            key_result = subprocess.run(key_modulus_cmd, capture_output=True, text=True)

            if cert_result.returncode != 0 or key_result.returncode != 0:
                self.logger.error(
                    "Failed to extract modulus for certificate/key comparison"
                )
                return False

            if cert_result.stdout.strip() != key_result.stdout.strip():
                self.logger.error("Certificate and private key do not match")
                return False

            self.logger.info("Certificate and private key validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Certificate validation error: {e}")
            return False

    def check_expiration(self, cert_path: str) -> Optional[datetime]:
        """
        Check SSL certificate expiration date

        Args:
            cert_path: Path to the certificate file

        Returns:
            datetime: Expiration date of the certificate, None if unable to determine
        """
        try:
            cert_file = Path(cert_path)

            if not cert_file.exists():
                self.logger.error(f"Certificate file not found: {cert_path}")
                return None

            # Extract expiration date using OpenSSL
            cmd = ["openssl", "x509", "-in", cert_path, "-noout", "-enddate"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse the output (format: "notAfter=MMM DD HH:MM:SS YYYY GMT")
            output = result.stdout.strip()
            if not output.startswith("notAfter="):
                self.logger.error(f"Unexpected OpenSSL output format: {output}")
                return None

            date_str = output.replace("notAfter=", "")

            # Parse the date string
            try:
                # Handle different possible formats
                for fmt in ["%b %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y GMT"]:
                    try:
                        expiration_date = datetime.strptime(date_str, fmt)
                        self.logger.info(f"Certificate expires on: {expiration_date}")
                        return expiration_date
                    except ValueError:
                        continue

                self.logger.error(f"Unable to parse expiration date: {date_str}")
                return None

            except ValueError as e:
                self.logger.error(f"Failed to parse expiration date '{date_str}': {e}")
                return None

        except subprocess.CalledProcessError as e:
            self.logger.error(f"OpenSSL command failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error checking certificate expiration: {e}")
            return None

    def setup_renewal_cron(self, cert_path: str) -> bool:
        """
        Setup automated certificate renewal using cron (for production certificates)

        Args:
            cert_path: Path to the certificate file to monitor

        Returns:
            bool: True if renewal cron was setup successfully, False otherwise
        """
        try:
            # Check if certificate exists
            cert_file = Path(cert_path)
            if not cert_file.exists():
                self.logger.error(f"Certificate file not found: {cert_path}")
                return False

            # Get certificate expiration
            expiration_date = self.check_expiration(cert_path)
            if not expiration_date:
                self.logger.error(
                    "Cannot setup renewal for certificate with unknown expiration"
                )
                return False

            # For self-signed certificates, provide guidance instead of actual cron setup
            if self._is_self_signed_certificate(cert_path):
                self.logger.info("Self-signed certificate detected.")
                self.logger.info(
                    "For production use, replace with certificates from a trusted CA."
                )
                self.logger.info(
                    "Consider using Let's Encrypt with certbot for automated renewal."
                )
                return True

            # For production certificates, provide renewal guidance
            self.logger.info("Certificate renewal setup guidance:")
            self.logger.info(
                "1. For Let's Encrypt certificates, use: certbot renew --dry-run"
            )
            self.logger.info(
                "2. Add to crontab: 0 12 * * * /usr/bin/certbot renew --quiet"
            )
            self.logger.info(
                "3. Restart web server after renewal: systemctl reload nginx"
            )

            # Create a renewal check script
            renewal_script_path = self.default_output_dir / "check_renewal.sh"
            renewal_script_content = self._create_renewal_script(cert_path)

            with open(renewal_script_path, "w") as f:
                f.write(renewal_script_content)

            # Make script executable
            os.chmod(renewal_script_path, 0o755)

            self.logger.info(f"Renewal check script created: {renewal_script_path}")
            self.logger.info(
                "Add this to your crontab to check certificate expiration daily:"
            )
            self.logger.info(f"0 9 * * * {renewal_script_path}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to setup certificate renewal: {e}")
            return False

    def get_certificate_info(self, cert_path: str, key_path: str) -> SSLCertificate:
        """
        Get comprehensive information about an SSL certificate

        Args:
            cert_path: Path to the certificate file
            key_path: Path to the private key file

        Returns:
            SSLCertificate: Certificate information object
        """
        errors = []

        try:
            cert_file = Path(cert_path)
            key_file = Path(key_path)

            # Check if files exist first
            if not cert_file.exists():
                errors.append(f"Certificate file not found: {cert_path}")
            if not key_file.exists():
                errors.append(f"Private key file not found: {key_path}")

            # If files don't exist, return early with error info
            if errors:
                return SSLCertificate(
                    cert_path=cert_path,
                    key_path=key_path,
                    domain="unknown",
                    expiration_date=None,
                    is_self_signed=False,
                    is_valid=False,
                    errors=errors,
                )

            # Extract domain from certificate
            domain = self._extract_domain_from_cert(cert_path)

            # Check expiration
            expiration_date = self.check_expiration(cert_path)

            # Check if self-signed
            is_self_signed = self._is_self_signed_certificate(cert_path)

            # Validate certificates
            is_valid = self.validate_certificates(cert_path, key_path)

            return SSLCertificate(
                cert_path=cert_path,
                key_path=key_path,
                domain=domain or "unknown",
                expiration_date=expiration_date,
                is_self_signed=is_self_signed,
                is_valid=is_valid,
                errors=errors,
            )

        except Exception as e:
            self.logger.error(f"Error getting certificate info: {e}")
            errors.append(str(e))
            return SSLCertificate(
                cert_path=cert_path,
                key_path=key_path,
                domain="unknown",
                expiration_date=None,
                is_self_signed=False,
                is_valid=False,
                errors=errors,
            )

    def _create_openssl_config(self, domain: str) -> str:
        """Create OpenSSL configuration for certificate generation"""
        return f"""[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Development
L = Local
O = SynthaTrial
OU = Development
CN = {domain}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = {domain}
DNS.2 = localhost
DNS.3 = *.{domain}
IP.1 = 127.0.0.1
IP.2 = ::1
"""

    def _is_self_signed_certificate(self, cert_path: str) -> bool:
        """Check if certificate is self-signed"""
        try:
            cmd = ["openssl", "x509", "-in", cert_path, "-noout", "-issuer", "-subject"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            lines = result.stdout.strip().split("\n")
            issuer = next((line for line in lines if line.startswith("issuer=")), "")
            subject = next((line for line in lines if line.startswith("subject=")), "")

            self.logger.debug(f"Certificate issuer: {issuer}")
            self.logger.debug(f"Certificate subject: {subject}")

            # Self-signed certificates have the same issuer and subject
            if issuer and subject and issuer != "" and subject != "":
                # Normalize the strings for comparison
                issuer_normalized = issuer.replace("issuer=", "").strip()
                subject_normalized = subject.replace("subject=", "").strip()
                return issuer_normalized == subject_normalized

            return False

        except Exception as e:
            self.logger.debug(f"Error checking if certificate is self-signed: {e}")
            return False

    def _extract_domain_from_cert(self, cert_path: str) -> Optional[str]:
        """Extract domain name from certificate"""
        try:
            cmd = ["openssl", "x509", "-in", cert_path, "-noout", "-subject"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse subject line to extract CN (Common Name)
            subject_line = result.stdout.strip()
            self.logger.debug(f"Certificate subject line: {subject_line}")

            # Handle different CN formats: "CN=value", "CN = value"
            import re

            cn_match = re.search(r"CN\s*=\s*([^,]+)", subject_line)
            if cn_match:
                return cn_match.group(1).strip()

            return None

        except Exception as e:
            self.logger.debug(f"Error extracting domain from certificate: {e}")
            return None

    def _create_renewal_script(self, cert_path: str) -> str:
        """Create a shell script for certificate renewal checking"""
        return f"""#!/bin/bash
# SSL Certificate Renewal Check Script
# Generated by SynthaTrial SSL Manager

CERT_PATH="{cert_path}"
DAYS_BEFORE_EXPIRY=30

# Check if certificate exists
if [ ! -f "$CERT_PATH" ]; then
    echo "ERROR: Certificate file not found: $CERT_PATH"
    exit 1
fi

# Get certificate expiration date
EXPIRY_DATE=$(openssl x509 -in "$CERT_PATH" -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
CURRENT_EPOCH=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))

echo "Certificate: $CERT_PATH"
echo "Expires: $EXPIRY_DATE"
echo "Days until expiry: $DAYS_UNTIL_EXPIRY"

# Check if renewal is needed
if [ $DAYS_UNTIL_EXPIRY -le $DAYS_BEFORE_EXPIRY ]; then
    echo "WARNING: Certificate expires in $DAYS_UNTIL_EXPIRY days!"
    echo "Please renew the certificate soon."

    # Log to syslog
    logger "SSL Certificate renewal needed: $CERT_PATH expires in $DAYS_UNTIL_EXPIRY days"

    exit 1
else
    echo "Certificate is valid for $DAYS_UNTIL_EXPIRY more days."
    exit 0
fi
"""


def main():
    """
    Command-line interface for SSL Manager
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="SSL Certificate Manager for SynthaTrial"
    )
    parser.add_argument(
        "--domain", help="Domain name for certificate (required for generation)"
    )
    parser.add_argument("--output-dir", help="Output directory for certificates")
    parser.add_argument(
        "--validate", help="Validate existing certificate (provide cert path)"
    )
    parser.add_argument("--key", help="Private key path (for validation)")
    parser.add_argument(
        "--check-expiration", help="Check certificate expiration (provide cert path)"
    )
    parser.add_argument(
        "--setup-renewal", help="Setup renewal monitoring (provide cert path)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ssl_manager = SSLManager(args.output_dir or "docker/ssl")

    if args.validate:
        if not args.key:
            print("ERROR: --key is required when using --validate")
            sys.exit(1)

        is_valid = ssl_manager.validate_certificates(args.validate, args.key)
        print(f"Certificate validation: {'PASSED' if is_valid else 'FAILED'}")
        sys.exit(0 if is_valid else 1)

    if args.check_expiration:
        expiration = ssl_manager.check_expiration(args.check_expiration)
        if expiration:
            days_until_expiry = (expiration - datetime.now()).days
            print(f"Certificate expires: {expiration}")
            print(f"Days until expiry: {days_until_expiry}")
        else:
            print("ERROR: Could not determine certificate expiration")
            sys.exit(1)
        sys.exit(0)

    if args.setup_renewal:
        success = ssl_manager.setup_renewal_cron(args.setup_renewal)
        print(f"Renewal setup: {'SUCCESS' if success else 'FAILED'}")
        sys.exit(0 if success else 1)

    # Generate self-signed certificate (only if no other action was specified)
    if not args.domain:
        print("ERROR: --domain is required for certificate generation")
        sys.exit(1)

    success = ssl_manager.generate_self_signed_certs(args.domain, args.output_dir)
    print(f"Certificate generation: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
