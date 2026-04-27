#!/usr/bin/env python3
"""
SynthaTrial Security Scanner
============================

Container image vulnerability scanner with support for multiple scanning tools
(Trivy, Grype) and comprehensive security reporting.

Features:
- Multi-tool vulnerability scanning (Trivy, Grype)
- Detailed security reports with remediation guidance
- Severity-based filtering and alerting
- Integration with CI/CD pipelines
- Support for both local and remote images
- Comprehensive error handling and logging

Usage:
    python scripts/security_scanner.py --image synthatrial:latest
    python scripts/security_scanner.py --image synthatrial:latest --scanner trivy
    python scripts/security_scanner.py --image synthatrial:latest --output-format json
    python scripts/security_scanner.py --image synthatrial:latest --severity high,critical
    python scripts/security_scanner.py --scan-all-images
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class SeverityLevel(Enum):
    """Vulnerability severity levels"""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScannerType(Enum):
    """Supported vulnerability scanners"""

    TRIVY = "trivy"
    GRYPE = "grype"
    AUTO = "auto"  # Automatically detect available scanner


@dataclass
class Vulnerability:
    """Individual vulnerability information"""

    id: str
    severity: str
    title: str
    description: str
    package_name: str
    package_version: str
    fixed_version: Optional[str] = None
    cvss_score: Optional[float] = None
    references: List[str] = None

    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class SecurityReport:
    """Comprehensive security scan report"""

    image_name: str
    scan_date: datetime
    scanner_used: str
    scanner_version: str
    vulnerabilities: List[Vulnerability]
    severity_counts: Dict[str, int]
    total_vulnerabilities: int
    scan_duration_seconds: float
    recommendations: List[str]
    overall_score: float
    scan_success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization"""
        result = asdict(self)
        result["scan_date"] = self.scan_date.isoformat()
        return result


class SecurityScanner:
    """Main security scanner class"""

    def __init__(
        self,
        scanner_type: ScannerType = ScannerType.AUTO,
        output_dir: str = "security_reports",
        verbose: bool = False,
    ):
        """
        Initialize security scanner

        Args:
            scanner_type: Type of scanner to use (trivy, grype, auto)
            output_dir: Directory to store security reports
            verbose: Enable verbose logging
        """
        self.scanner_type = scanner_type
        self.output_dir = Path(output_dir)
        self.verbose = verbose

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Detect available scanners
        self.available_scanners = self._detect_scanners()

        # Select scanner to use
        self.selected_scanner = self._select_scanner()

        self.logger.info(f"Security scanner initialized with {self.selected_scanner}")

    def _detect_scanners(self) -> Dict[str, bool]:
        """Detect which security scanners are available"""
        scanners = {}

        # Check for Trivy
        try:
            result = subprocess.run(
                ["trivy", "--version"], capture_output=True, text=True, timeout=10
            )
            scanners["trivy"] = result.returncode == 0
            if scanners["trivy"]:
                self.logger.debug(f"Trivy detected: {result.stdout.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            scanners["trivy"] = False
        except Exception:
            # Handle any other exceptions (e.g., from mocks)
            scanners["trivy"] = False

        # Check for Grype
        try:
            result = subprocess.run(
                ["grype", "--version"], capture_output=True, text=True, timeout=10
            )
            scanners["grype"] = result.returncode == 0
            if scanners["grype"]:
                self.logger.debug(f"Grype detected: {result.stdout.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            scanners["grype"] = False
        except Exception:
            # Handle any other exceptions (e.g., from mocks)
            scanners["grype"] = False

        return scanners

    def _select_scanner(self) -> str:
        """Select which scanner to use based on availability and preference"""
        if self.scanner_type == ScannerType.AUTO:
            # Prefer Trivy, fallback to Grype
            if self.available_scanners.get("trivy", False):
                return "trivy"
            elif self.available_scanners.get("grype", False):
                return "grype"
            else:
                raise RuntimeError(
                    "No supported vulnerability scanners found. "
                    "Please install Trivy or Grype."
                )
        else:
            scanner_name = self.scanner_type.value
            if not self.available_scanners.get(scanner_name, False):
                raise RuntimeError(
                    f"Requested scanner '{scanner_name}' not available. "
                    f"Available scanners: {list(self.available_scanners.keys())}"
                )
            return scanner_name

    def _get_scanner_version(self, scanner: str) -> str:
        """Get version of the selected scanner"""
        try:
            result = subprocess.run(
                [scanner, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return "unknown"

    def comprehensive_scan(self) -> Dict[str, Any]:
        """Run comprehensive security scan (stub for integration tests)."""
        return {
            "overall_passed": False,
            "security_score": 0.0,
            "vulnerabilities": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "compliance_checks": {},
        }

    def scan_image(
        self,
        image_name: str,
        severity_filter: Optional[List[str]] = None,
        output_format: str = "json",
    ) -> SecurityReport:
        """
        Scan container image for vulnerabilities

        Args:
            image_name: Name/tag of the container image to scan
            severity_filter: List of severity levels to include (e.g., ['high', 'critical'])
            output_format: Output format for detailed reports ('json', 'table', 'sarif')

        Returns:
            SecurityReport with scan results
        """
        start_time = datetime.now()
        self.logger.info(f"Starting security scan of image: {image_name}")

        try:
            if self.selected_scanner == "trivy":
                report = self._scan_with_trivy(image_name, severity_filter)
            elif self.selected_scanner == "grype":
                report = self._scan_with_grype(image_name, severity_filter)
            else:
                raise ValueError(f"Unsupported scanner: {self.selected_scanner}")

            # Calculate scan duration
            end_time = datetime.now()
            report.scan_duration_seconds = (end_time - start_time).total_seconds()

            # Generate recommendations
            report.recommendations = self._generate_recommendations(report)

            # Calculate overall security score
            report.overall_score = self._calculate_security_score(report)

            # Save detailed report
            self._save_report(report, output_format)

            self.logger.info(
                f"Security scan completed in {report.scan_duration_seconds:.2f}s. "
                f"Found {report.total_vulnerabilities} vulnerabilities."
            )

            return report

        except Exception as e:
            self.logger.error(f"Security scan failed: {str(e)}")
            return SecurityReport(
                image_name=image_name,
                scan_date=start_time,
                scanner_used=self.selected_scanner,
                scanner_version=self._get_scanner_version(self.selected_scanner),
                vulnerabilities=[],
                severity_counts={},
                total_vulnerabilities=0,
                scan_duration_seconds=(datetime.now() - start_time).total_seconds(),
                recommendations=[],
                overall_score=0.0,
                scan_success=False,
                error_message=str(e),
            )

    def _scan_with_trivy(
        self, image_name: str, severity_filter: Optional[List[str]] = None
    ) -> SecurityReport:
        """Scan image using Trivy scanner"""
        self.logger.debug(f"Scanning with Trivy: {image_name}")

        # Build Trivy command
        cmd = ["trivy", "image", "--format", "json", "--quiet"]

        if severity_filter:
            cmd.extend(["--severity", ",".join(severity_filter).upper()])

        cmd.append(image_name)

        # Run Trivy scan
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise RuntimeError(f"Trivy scan failed: {result.stderr}")

        # Parse Trivy output
        try:
            trivy_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Trivy output: {e}")

        # Convert to our format
        vulnerabilities = []
        severity_counts = {level.value: 0 for level in SeverityLevel}

        for result_item in trivy_data.get("Results", []):
            for vuln in result_item.get("Vulnerabilities", []):
                severity = vuln.get("Severity", "unknown").lower()

                vulnerability = Vulnerability(
                    id=vuln.get("VulnerabilityID", "unknown"),
                    severity=severity,
                    title=vuln.get("Title", "No title available"),
                    description=vuln.get("Description", "No description available"),
                    package_name=vuln.get("PkgName", "unknown"),
                    package_version=vuln.get("InstalledVersion", "unknown"),
                    fixed_version=vuln.get("FixedVersion"),
                    cvss_score=self._extract_cvss_score(vuln),
                    references=vuln.get("References", []),
                )

                vulnerabilities.append(vulnerability)
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return SecurityReport(
            image_name=image_name,
            scan_date=datetime.now(),
            scanner_used="trivy",
            scanner_version=self._get_scanner_version("trivy"),
            vulnerabilities=vulnerabilities,
            severity_counts=severity_counts,
            total_vulnerabilities=len(vulnerabilities),
            scan_duration_seconds=0.0,  # Will be set by caller
            recommendations=[],  # Will be generated by caller
            overall_score=0.0,  # Will be calculated by caller
            scan_success=True,
        )

    def _scan_with_grype(
        self, image_name: str, severity_filter: Optional[List[str]] = None
    ) -> SecurityReport:
        """Scan image using Grype scanner"""
        self.logger.debug(f"Scanning with Grype: {image_name}")

        # Build Grype command
        cmd = ["grype", image_name, "-o", "json"]

        # Run Grype scan
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise RuntimeError(f"Grype scan failed: {result.stderr}")

        # Parse Grype output
        try:
            grype_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Grype output: {e}")

        # Convert to our format
        vulnerabilities = []
        severity_counts = {level.value: 0 for level in SeverityLevel}

        for match in grype_data.get("matches", []):
            vuln = match.get("vulnerability", {})
            artifact = match.get("artifact", {})

            severity = vuln.get("severity", "unknown").lower()

            # Apply severity filter if specified
            if severity_filter and severity not in [s.lower() for s in severity_filter]:
                continue

            vulnerability = Vulnerability(
                id=vuln.get("id", "unknown"),
                severity=severity,
                title=vuln.get("description", "No title available"),
                description=vuln.get("description", "No description available"),
                package_name=artifact.get("name", "unknown"),
                package_version=artifact.get("version", "unknown"),
                fixed_version=(
                    vuln.get("fix", {}).get("versions", [None])[0]
                    if vuln.get("fix")
                    else None
                ),
                cvss_score=self._extract_grype_cvss_score(vuln),
                references=vuln.get("urls", []),
            )

            vulnerabilities.append(vulnerability)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return SecurityReport(
            image_name=image_name,
            scan_date=datetime.now(),
            scanner_used="grype",
            scanner_version=self._get_scanner_version("grype"),
            vulnerabilities=vulnerabilities,
            severity_counts=severity_counts,
            total_vulnerabilities=len(vulnerabilities),
            scan_duration_seconds=0.0,  # Will be set by caller
            recommendations=[],  # Will be generated by caller
            overall_score=0.0,  # Will be calculated by caller
            scan_success=True,
        )

    def _extract_cvss_score(self, vuln: Dict) -> Optional[float]:
        """Extract CVSS score from Trivy vulnerability data"""
        cvss_data = vuln.get("CVSS", {})
        if isinstance(cvss_data, dict):
            for version in ["nvd", "redhat", "ubuntu"]:
                if version in cvss_data:
                    score = cvss_data[version].get("V3Score") or cvss_data[version].get(
                        "V2Score"
                    )
                    if score:
                        return float(score)
        return None

    def _extract_grype_cvss_score(self, vuln: Dict) -> Optional[float]:
        """Extract CVSS score from Grype vulnerability data"""
        cvss_list = vuln.get("cvss", [])
        if cvss_list and isinstance(cvss_list, list):
            for cvss in cvss_list:
                if isinstance(cvss, dict) and "metrics" in cvss:
                    score = cvss["metrics"].get("baseScore")
                    if score:
                        return float(score)
        return None

    def _generate_recommendations(self, report: SecurityReport) -> List[str]:
        """Generate security recommendations based on scan results"""
        recommendations = []

        # Critical vulnerabilities
        critical_count = report.severity_counts.get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"🚨 URGENT: {critical_count} critical vulnerabilities found. "
                "Address immediately before production deployment."
            )

        # High severity vulnerabilities
        high_count = report.severity_counts.get("high", 0)
        if high_count > 0:
            recommendations.append(
                f"⚠️  HIGH PRIORITY: {high_count} high-severity vulnerabilities found. "
                "Plan remediation within 7 days."
            )

        # Package updates
        fixable_vulns = [v for v in report.vulnerabilities if v.fixed_version]
        if fixable_vulns:
            recommendations.append(
                f"📦 {len(fixable_vulns)} vulnerabilities can be fixed by updating packages. "
                "Review and update affected packages."
            )

        # Base image recommendations
        if report.total_vulnerabilities > 50:
            recommendations.append(
                "🐳 Consider using a more secure base image (e.g., distroless, alpine) "
                "to reduce attack surface."
            )

        # Security best practices
        if report.total_vulnerabilities > 0:
            recommendations.extend(
                [
                    "🔒 Implement regular security scanning in CI/CD pipeline",
                    "📋 Establish vulnerability management process with SLAs",
                    "🔄 Keep base images and dependencies updated regularly",
                ]
            )

        # Good security posture
        if report.total_vulnerabilities == 0:
            recommendations.append(
                "✅ Excellent! No vulnerabilities detected. Maintain regular scanning."
            )

        return recommendations

    def _calculate_security_score(self, report: SecurityReport) -> float:
        """Calculate overall security score (0-100, higher is better)"""
        if not report.scan_success:
            return 0.0

        if report.total_vulnerabilities == 0:
            return 100.0

        # Weight vulnerabilities by severity
        severity_weights = {
            "critical": 10.0,
            "high": 5.0,
            "medium": 2.0,
            "low": 1.0,
            "unknown": 0.5,
        }

        weighted_score = 0.0
        for severity, count in report.severity_counts.items():
            weight = severity_weights.get(severity, 0.5)
            weighted_score += count * weight

        # Convert to 0-100 scale (lower weighted score = higher security score)
        # Use logarithmic scale to avoid extreme penalties for many low-severity issues
        import math

        max_score = 100.0
        penalty = min(90.0, 20.0 * math.log10(1 + weighted_score))

        return max(10.0, max_score - penalty)

    def _save_report(self, report: SecurityReport, output_format: str = "json"):
        """Save security report to file"""
        timestamp = report.scan_date.strftime("%Y%m%d_%H%M%S")
        safe_image_name = report.image_name.replace(":", "_").replace("/", "_")

        if output_format.lower() == "json":
            filename = f"security_report_{safe_image_name}_{timestamp}.json"
            filepath = self.output_dir / filename

            with open(filepath, "w") as f:
                json.dump(report.to_dict(), f, indent=2, default=str)

            self.logger.info(f"Security report saved: {filepath}")

        elif output_format.lower() == "html":
            filename = f"security_report_{safe_image_name}_{timestamp}.html"
            filepath = self.output_dir / filename

            html_content = self._generate_html_report(report)
            with open(filepath, "w") as f:
                f.write(html_content)

            self.logger.info(f"HTML security report saved: {filepath}")

    def _generate_html_report(self, report: SecurityReport) -> str:
        """Generate HTML security report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Security Scan Report - {image_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; text-align: center; }}
        .critical {{ background-color: #dc3545; color: white; }}
        .high {{ background-color: #fd7e14; color: white; }}
        .medium {{ background-color: #ffc107; }}
        .low {{ background-color: #28a745; color: white; }}
        .vulnerability {{ border: 1px solid #dee2e6; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .recommendations {{ background-color: #d1ecf1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Security Scan Report</h1>
        <p><strong>Image:</strong> {image_name}</p>
        <p><strong>Scan Date:</strong> {scan_date}</p>
        <p><strong>Scanner:</strong> {scanner_used} ({scanner_version})</p>
        <p><strong>Security Score:</strong> {overall_score:.1f}/100</p>
    </div>

    <div class="summary">
        <div class="metric critical">
            <h3>{critical_count}</h3>
            <p>Critical</p>
        </div>
        <div class="metric high">
            <h3>{high_count}</h3>
            <p>High</p>
        </div>
        <div class="metric medium">
            <h3>{medium_count}</h3>
            <p>Medium</p>
        </div>
        <div class="metric low">
            <h3>{low_count}</h3>
            <p>Low</p>
        </div>
    </div>

    <div class="recommendations">
        <h2>📋 Recommendations</h2>
        <ul>
            {recommendations_html}
        </ul>
    </div>

    <h2>🐛 Vulnerabilities ({total_vulnerabilities})</h2>
    {vulnerabilities_html}
</body>
</html>
        """

        # Format recommendations
        recommendations_html = "\n".join(
            [f"<li>{rec}</li>" for rec in report.recommendations]
        )

        # Format vulnerabilities
        vulnerabilities_html = ""
        for vuln in report.vulnerabilities[:50]:  # Limit to first 50 for readability
            vuln_html = f"""
            <div class="vulnerability {vuln.severity}">
                <h3>{vuln.id} - {vuln.title}</h3>
                <p><strong>Package:</strong> {vuln.package_name} ({vuln.package_version})</p>
                <p><strong>Severity:</strong> {vuln.severity.upper()}</p>
                {f'<p><strong>Fixed Version:</strong> {vuln.fixed_version}</p>' if vuln.fixed_version else ''}
                {f'<p><strong>CVSS Score:</strong> {vuln.cvss_score}</p>' if vuln.cvss_score else ''}
                <p>{vuln.description}</p>
            </div>
            """
            vulnerabilities_html += vuln_html

        if len(report.vulnerabilities) > 50:
            vulnerabilities_html += f"<p><em>... and {len(report.vulnerabilities) - 50} more vulnerabilities</em></p>"

        return html_template.format(
            image_name=report.image_name,
            scan_date=report.scan_date.strftime("%Y-%m-%d %H:%M:%S"),
            scanner_used=report.scanner_used,
            scanner_version=report.scanner_version,
            overall_score=report.overall_score,
            critical_count=report.severity_counts.get("critical", 0),
            high_count=report.severity_counts.get("high", 0),
            medium_count=report.severity_counts.get("medium", 0),
            low_count=report.severity_counts.get("low", 0),
            total_vulnerabilities=report.total_vulnerabilities,
            recommendations_html=recommendations_html,
            vulnerabilities_html=vulnerabilities_html,
        )

    def scan_all_local_images(
        self, severity_filter: Optional[List[str]] = None
    ) -> List[SecurityReport]:
        """Scan all local Docker images"""
        self.logger.info("Scanning all local Docker images...")

        # Get list of local images
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to list Docker images: {result.stderr}")

            images = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
            images = [img for img in images if not img.endswith(":<none>")]

        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout while listing Docker images")

        if not images:
            self.logger.warning("No local Docker images found")
            return []

        self.logger.info(f"Found {len(images)} local images to scan")

        # Scan each image
        reports = []
        for image in images:
            try:
                self.logger.info(f"Scanning image: {image}")
                report = self.scan_image(image, severity_filter)
                reports.append(report)
            except Exception as e:
                self.logger.error(f"Failed to scan image {image}: {e}")
                # Create error report
                error_report = SecurityReport(
                    image_name=image,
                    scan_date=datetime.now(),
                    scanner_used=self.selected_scanner,
                    scanner_version=self._get_scanner_version(self.selected_scanner),
                    vulnerabilities=[],
                    severity_counts={},
                    total_vulnerabilities=0,
                    scan_duration_seconds=0.0,
                    recommendations=[],
                    overall_score=0.0,
                    scan_success=False,
                    error_message=str(e),
                )
                reports.append(error_report)

        return reports

    def generate_summary_report(self, reports: List[SecurityReport]) -> Dict[str, Any]:
        """Generate summary report from multiple scan results"""
        total_images = len(reports)
        successful_scans = len([r for r in reports if r.scan_success])
        failed_scans = total_images - successful_scans

        # Aggregate vulnerability counts
        total_vulnerabilities = sum(
            r.total_vulnerabilities for r in reports if r.scan_success
        )
        severity_totals = {level.value: 0 for level in SeverityLevel}

        for report in reports:
            if report.scan_success:
                for severity, count in report.severity_counts.items():
                    severity_totals[severity] = severity_totals.get(severity, 0) + count

        # Calculate average security score
        successful_reports = [r for r in reports if r.scan_success]
        avg_security_score = (
            (sum(r.overall_score for r in successful_reports) / len(successful_reports))
            if successful_reports
            else 0.0
        )

        # Identify most vulnerable images
        most_vulnerable = sorted(
            [r for r in reports if r.scan_success],
            key=lambda x: x.total_vulnerabilities,
            reverse=True,
        )[:5]

        summary = {
            "scan_summary": {
                "total_images_scanned": total_images,
                "successful_scans": successful_scans,
                "failed_scans": failed_scans,
                "scan_date": datetime.now().isoformat(),
            },
            "vulnerability_summary": {
                "total_vulnerabilities": total_vulnerabilities,
                "severity_breakdown": severity_totals,
                "average_security_score": round(avg_security_score, 1),
            },
            "most_vulnerable_images": [
                {
                    "image": r.image_name,
                    "vulnerabilities": r.total_vulnerabilities,
                    "security_score": r.overall_score,
                    "critical_count": r.severity_counts.get("critical", 0),
                    "high_count": r.severity_counts.get("high", 0),
                }
                for r in most_vulnerable
            ],
            "recommendations": self._generate_fleet_recommendations(reports),
        }

        return summary

    def _generate_fleet_recommendations(
        self, reports: List[SecurityReport]
    ) -> List[str]:
        """Generate recommendations for entire image fleet"""
        recommendations = []

        successful_reports = [r for r in reports if r.scan_success]
        if not successful_reports:
            return ["❌ No successful scans to analyze"]

        # Critical vulnerabilities across fleet
        total_critical = sum(
            r.severity_counts.get("critical", 0) for r in successful_reports
        )
        if total_critical > 0:
            recommendations.append(
                f"🚨 FLEET ALERT: {total_critical} critical vulnerabilities across {len(successful_reports)} images. "
                "Implement emergency patching process."
            )

        # Images with poor security scores
        poor_images = [r for r in successful_reports if r.overall_score < 50]
        if poor_images:
            recommendations.append(
                f"⚠️  {len(poor_images)} images have security scores below 50. "
                "Prioritize rebuilding these images with updated base images."
            )

        # Fleet-wide recommendations
        avg_score = sum(r.overall_score for r in successful_reports) / len(
            successful_reports
        )
        if avg_score < 70:
            recommendations.extend(
                [
                    "📋 Implement automated security scanning in CI/CD pipeline",
                    "🔄 Establish regular base image update schedule",
                    "🐳 Consider migration to more secure base images (distroless, alpine)",
                    "📊 Set up security metrics dashboard for continuous monitoring",
                ]
            )

        return recommendations


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="SynthaTrial Container Security Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan single image
  python scripts/security_scanner.py --image synthatrial:latest

  # Scan with specific scanner
  python scripts/security_scanner.py --image synthatrial:latest --scanner trivy

  # Filter by severity
  python scripts/security_scanner.py --image synthatrial:latest --severity high,critical

  # Scan all local images
  python scripts/security_scanner.py --scan-all-images

  # Generate HTML report
  python scripts/security_scanner.py --image synthatrial:latest --output-format html
        """,
    )

    # Image selection
    image_group = parser.add_mutually_exclusive_group(required=True)
    image_group.add_argument("--image", help="Container image to scan (name:tag)")
    image_group.add_argument(
        "--scan-all-images", action="store_true", help="Scan all local Docker images"
    )

    # Scanner options
    parser.add_argument(
        "--scanner",
        choices=["trivy", "grype", "auto"],
        default="auto",
        help="Security scanner to use (default: auto)",
    )

    parser.add_argument(
        "--severity",
        help="Comma-separated list of severity levels to include (e.g., high,critical)",
    )

    parser.add_argument(
        "--output-format",
        choices=["json", "html", "table"],
        default="json",
        help="Output format for reports (default: json)",
    )

    parser.add_argument(
        "--output-dir",
        default="security_reports",
        help="Directory to save reports (default: security_reports)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with non-zero code if critical vulnerabilities found",
    )

    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with non-zero code if high+ severity vulnerabilities found",
    )

    args = parser.parse_args()

    # Parse severity filter
    severity_filter = None
    if args.severity:
        severity_filter = [s.strip().lower() for s in args.severity.split(",")]

    try:
        # Initialize scanner
        scanner = SecurityScanner(
            scanner_type=ScannerType(args.scanner),
            output_dir=args.output_dir,
            verbose=args.verbose,
        )

        # Perform scan(s)
        if args.scan_all_images:
            reports = scanner.scan_all_local_images(severity_filter)

            # Generate and save summary report
            summary = scanner.generate_summary_report(reports)
            summary_file = (
                Path(args.output_dir)
                / f"security_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2, default=str)

            print(f"\n📊 Security Summary Report")
            print(f"========================")
            print(f"Images scanned: {summary['scan_summary']['total_images_scanned']}")
            print(f"Successful scans: {summary['scan_summary']['successful_scans']}")
            print(
                f"Total vulnerabilities: {summary['vulnerability_summary']['total_vulnerabilities']}"
            )
            print(
                f"Average security score: {summary['vulnerability_summary']['average_security_score']}/100"
            )
            print(f"\nSeverity breakdown:")
            for severity, count in summary["vulnerability_summary"][
                "severity_breakdown"
            ].items():
                if count > 0:
                    print(f"  {severity.upper()}: {count}")

            print(f"\nDetailed reports saved to: {args.output_dir}")
            print(f"Summary report saved to: {summary_file}")

            # Check exit conditions
            critical_total = summary["vulnerability_summary"]["severity_breakdown"].get(
                "critical", 0
            )
            high_total = summary["vulnerability_summary"]["severity_breakdown"].get(
                "high", 0
            )

            if args.fail_on_critical and critical_total > 0:
                print(f"\n❌ CRITICAL: {critical_total} critical vulnerabilities found!")
                sys.exit(1)

            if args.fail_on_high and (critical_total > 0 or high_total > 0):
                print(
                    f"\n❌ HIGH SEVERITY: {critical_total + high_total} high+ severity vulnerabilities found!"
                )
                sys.exit(1)

        else:
            # Single image scan
            report = scanner.scan_image(args.image, severity_filter, args.output_format)

            if not report.scan_success:
                print(f"❌ Scan failed: {report.error_message}")
                sys.exit(1)

            # Display results
            print(f"\n🔒 Security Scan Results for {args.image}")
            print(f"=" * 50)
            print(f"Scanner: {report.scanner_used} ({report.scanner_version})")
            print(f"Scan duration: {report.scan_duration_seconds:.2f}s")
            print(f"Security score: {report.overall_score:.1f}/100")
            print(f"Total vulnerabilities: {report.total_vulnerabilities}")

            if report.total_vulnerabilities > 0:
                print(f"\nSeverity breakdown:")
                for severity, count in report.severity_counts.items():
                    if count > 0:
                        print(f"  {severity.upper()}: {count}")

            if report.recommendations:
                print(f"\n📋 Recommendations:")
                for rec in report.recommendations:
                    print(f"  • {rec}")

            print(f"\nDetailed report saved to: {args.output_dir}")

            # Check exit conditions
            if args.fail_on_critical and report.severity_counts.get("critical", 0) > 0:
                print(f"\n❌ CRITICAL vulnerabilities found!")
                sys.exit(1)

            if args.fail_on_high and (
                report.severity_counts.get("critical", 0) > 0
                or report.severity_counts.get("high", 0) > 0
            ):
                print(f"\n❌ HIGH+ severity vulnerabilities found!")
                sys.exit(1)

    except Exception as e:
        print(f"❌ Security scanner error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
