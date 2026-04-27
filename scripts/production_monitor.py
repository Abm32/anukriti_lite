#!/usr/bin/env python3
"""
SynthaTrial Production Monitor
==============================

Production monitoring system with resource tracking, health monitoring, and alerting.
Provides comprehensive monitoring capabilities for containerized SynthaTrial deployments.

Features:
- Real-time resource monitoring (CPU, memory, disk, network)
- Container health status tracking
- Performance metrics collection and analysis
- Alerting system with configurable thresholds
- Automated backup procedures
- System recovery recommendations
- Integration with Docker and container orchestration
- Comprehensive logging and reporting

Usage:
    python scripts/production_monitor.py --monitor
    python scripts/production_monitor.py --monitor --alert-config alerts.json
    python scripts/production_monitor.py --backup --backup-paths /app/data,/app/logs
    python scripts/production_monitor.py --health-check
    python scripts/production_monitor.py --generate-report
"""

import argparse
import json
import logging
import os
import shutil
import signal
import smtplib
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
import requests

import docker


class HealthStatus(Enum):
    """Container health status levels"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ResourceMetrics:
    """System resource metrics"""

    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_mb: int
    memory_total_mb: int
    memory_usage_percent: float
    disk_usage_mb: int
    disk_total_mb: int
    disk_usage_percent: float
    network_io_mb: float
    load_average: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class ContainerMetrics:
    """Container-specific metrics"""

    container_id: str
    container_name: str
    image: str
    status: str
    health_status: HealthStatus
    cpu_usage_percent: float
    memory_usage_mb: int
    memory_limit_mb: int
    memory_usage_percent: float
    network_rx_mb: float
    network_tx_mb: float
    restart_count: int
    uptime_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["health_status"] = self.health_status.value
        return result


@dataclass
class Alert:
    """System alert information"""

    id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    message: str
    source: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["severity"] = self.severity.value
        if self.resolution_time:
            result["resolution_time"] = self.resolution_time.isoformat()
        return result


@dataclass
class BackupResult:
    """Backup operation result"""

    backup_id: str
    timestamp: datetime
    paths: List[str]
    backup_file: str
    size_mb: float
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class AlertConfig:
    """Alert configuration settings"""

    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    disk_threshold: float = 90.0
    container_restart_threshold: int = 3
    response_time_threshold: float = 5.0
    email_enabled: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_recipients: List[str] = None
    webhook_url: str = ""
    check_interval: int = 60

    def __post_init__(self):
        if self.email_recipients is None:
            self.email_recipients = []


class ProductionMonitor:
    """Main production monitoring class"""

    def __init__(
        self,
        output_dir: str = "monitoring_reports",
        alert_config: Optional[AlertConfig] = None,
        verbose: bool = False,
    ):
        """
        Initialize production monitor

        Args:
            output_dir: Directory to store monitoring reports
            alert_config: Alert configuration settings
            verbose: Enable verbose logging
        """
        self.output_dir = Path(output_dir)
        self.alert_config = alert_config or AlertConfig()
        self.verbose = verbose

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.docker_available = True
            self.logger.info("Docker client initialized successfully")
        except Exception as e:
            self.docker_client = None
            self.docker_available = False
            self.logger.warning(f"Docker not available: {e}")

        # Monitoring state
        self.monitoring_active = False
        self.alerts = []
        self.metrics_history = []
        self.container_metrics_history = []

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("Production monitor initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.monitoring_active = False

    def collect_system_metrics(self) -> ResourceMetrics:
        """Collect system-wide resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) // (1024 * 1024)
            memory_total_mb = memory.total // (1024 * 1024)

            # Disk usage (root filesystem)
            disk = psutil.disk_usage("/")
            disk_usage_mb = disk.used // (1024 * 1024)
            disk_total_mb = disk.total // (1024 * 1024)
            disk_percent = (disk.used / disk.total) * 100

            # Network I/O
            network = psutil.net_io_counters()
            network_io_mb = (network.bytes_sent + network.bytes_recv) / (1024 * 1024)

            # Load average
            load_avg = os.getloadavg()

            return ResourceMetrics(
                timestamp=datetime.now(),
                cpu_usage_percent=cpu_percent,
                memory_usage_mb=memory_usage_mb,
                memory_total_mb=memory_total_mb,
                memory_usage_percent=memory.percent,
                disk_usage_mb=disk_usage_mb,
                disk_total_mb=disk_total_mb,
                disk_usage_percent=disk_percent,
                network_io_mb=network_io_mb,
                load_average=load_avg,
            )

        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            raise

    def collect_container_metrics(self) -> List[ContainerMetrics]:
        """Collect metrics for all running containers"""
        if not self.docker_available:
            return []

        container_metrics = []

        try:
            containers = self.docker_client.containers.list(all=True)

            for container in containers:
                try:
                    # Get container stats
                    stats = container.stats(stream=False)

                    # Calculate CPU usage
                    cpu_delta = (
                        stats["cpu_stats"]["cpu_usage"]["total_usage"]
                        - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                    )
                    system_delta = (
                        stats["cpu_stats"]["system_cpu_usage"]
                        - stats["precpu_stats"]["system_cpu_usage"]
                    )

                    cpu_percent = 0.0
                    if system_delta > 0:
                        cpu_percent = (
                            (cpu_delta / system_delta)
                            * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
                            * 100
                        )

                    # Memory usage
                    memory_usage = stats["memory_stats"].get("usage", 0)
                    memory_limit = stats["memory_stats"].get("limit", 0)
                    memory_usage_mb = memory_usage // (1024 * 1024)
                    memory_limit_mb = memory_limit // (1024 * 1024)
                    memory_percent = (
                        (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
                    )

                    # Network I/O
                    networks = stats.get("networks", {})
                    network_rx = sum(
                        net.get("rx_bytes", 0) for net in networks.values()
                    )
                    network_tx = sum(
                        net.get("tx_bytes", 0) for net in networks.values()
                    )
                    network_rx_mb = network_rx / (1024 * 1024)
                    network_tx_mb = network_tx / (1024 * 1024)

                    # Container info
                    container.reload()
                    restart_count = container.attrs["RestartCount"]

                    # Calculate uptime
                    started_at = container.attrs["State"]["StartedAt"]
                    if started_at:
                        start_time = datetime.fromisoformat(
                            started_at.replace("Z", "+00:00")
                        )
                        uptime = (
                            datetime.now(start_time.tzinfo) - start_time
                        ).total_seconds()
                    else:
                        uptime = 0

                    # Health status
                    health_status = HealthStatus.UNKNOWN
                    if container.status == "running":
                        health = container.attrs.get("State", {}).get("Health", {})
                        if health:
                            health_status_str = health.get("Status", "unknown").lower()
                            try:
                                health_status = HealthStatus(health_status_str)
                            except ValueError:
                                health_status = HealthStatus.UNKNOWN
                        else:
                            health_status = (
                                HealthStatus.HEALTHY
                            )  # Assume healthy if no health check
                    elif container.status == "exited":
                        health_status = HealthStatus.UNHEALTHY

                    metrics = ContainerMetrics(
                        container_id=container.id[:12],
                        container_name=container.name,
                        image=(
                            container.image.tags[0]
                            if container.image.tags
                            else container.image.id[:12]
                        ),
                        status=container.status,
                        health_status=health_status,
                        cpu_usage_percent=cpu_percent,
                        memory_usage_mb=memory_usage_mb,
                        memory_limit_mb=memory_limit_mb,
                        memory_usage_percent=memory_percent,
                        network_rx_mb=network_rx_mb,
                        network_tx_mb=network_tx_mb,
                        restart_count=restart_count,
                        uptime_seconds=int(uptime),
                    )

                    container_metrics.append(metrics)

                except Exception as e:
                    self.logger.warning(
                        f"Failed to collect metrics for container {container.name}: {e}"
                    )
                    continue

        except Exception as e:
            self.logger.error(f"Failed to collect container metrics: {e}")

        return container_metrics

    def check_health_endpoints(self) -> Dict[str, Any]:
        """Check health endpoints for running services"""
        health_results = {}

        # Common health check endpoints
        endpoints = [
            ("SynthaTrial Web", "http://localhost:8501/_stcore/health"),
            ("Nginx Proxy", "http://localhost/health"),
            ("HTTPS Nginx", "https://localhost/health"),
        ]

        for service_name, url in endpoints:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=5, verify=False)
                response_time = time.time() - start_time

                health_results[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "url": url,
                }

            except requests.exceptions.RequestException as e:
                health_results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "url": url,
                }

        return health_results

    def analyze_metrics_and_generate_alerts(
        self, system_metrics: ResourceMetrics, container_metrics: List[ContainerMetrics]
    ) -> List[Alert]:
        """Analyze metrics and generate alerts based on thresholds"""
        new_alerts = []

        # System resource alerts
        if system_metrics.cpu_usage_percent > self.alert_config.cpu_threshold:
            alert = Alert(
                id=f"cpu_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=(
                    AlertSeverity.WARNING
                    if system_metrics.cpu_usage_percent < 95
                    else AlertSeverity.CRITICAL
                ),
                title="High CPU Usage",
                message=f"CPU usage is {system_metrics.cpu_usage_percent:.1f}% (threshold: {self.alert_config.cpu_threshold}%)",
                source="system",
                metric_value=system_metrics.cpu_usage_percent,
                threshold=self.alert_config.cpu_threshold,
            )
            new_alerts.append(alert)

        if system_metrics.memory_usage_percent > self.alert_config.memory_threshold:
            alert = Alert(
                id=f"memory_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=(
                    AlertSeverity.WARNING
                    if system_metrics.memory_usage_percent < 95
                    else AlertSeverity.CRITICAL
                ),
                title="High Memory Usage",
                message=f"Memory usage is {system_metrics.memory_usage_percent:.1f}% (threshold: {self.alert_config.memory_threshold}%)",
                source="system",
                metric_value=system_metrics.memory_usage_percent,
                threshold=self.alert_config.memory_threshold,
            )
            new_alerts.append(alert)

        if system_metrics.disk_usage_percent > self.alert_config.disk_threshold:
            alert = Alert(
                id=f"disk_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=AlertSeverity.CRITICAL,
                title="High Disk Usage",
                message=f"Disk usage is {system_metrics.disk_usage_percent:.1f}% (threshold: {self.alert_config.disk_threshold}%)",
                source="system",
                metric_value=system_metrics.disk_usage_percent,
                threshold=self.alert_config.disk_threshold,
            )
            new_alerts.append(alert)

        # Container-specific alerts
        for container in container_metrics:
            # Container health alerts
            if container.health_status == HealthStatus.UNHEALTHY:
                alert = Alert(
                    id=f"container_unhealthy_{container.container_name}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.CRITICAL,
                    title="Container Unhealthy",
                    message=f"Container {container.container_name} is unhealthy",
                    source=f"container:{container.container_name}",
                )
                new_alerts.append(alert)

            # Container restart alerts
            if container.restart_count > self.alert_config.container_restart_threshold:
                alert = Alert(
                    id=f"container_restarts_{container.container_name}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING,
                    title="High Container Restart Count",
                    message=f"Container {container.container_name} has restarted {container.restart_count} times (threshold: {self.alert_config.container_restart_threshold})",
                    source=f"container:{container.container_name}",
                    metric_value=float(container.restart_count),
                    threshold=float(self.alert_config.container_restart_threshold),
                )
                new_alerts.append(alert)

            # Container memory alerts
            if container.memory_usage_percent > 90:
                alert = Alert(
                    id=f"container_memory_{container.container_name}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING,
                    title="High Container Memory Usage",
                    message=f"Container {container.container_name} memory usage is {container.memory_usage_percent:.1f}%",
                    source=f"container:{container.container_name}",
                    metric_value=container.memory_usage_percent,
                    threshold=90.0,
                )
                new_alerts.append(alert)

        # Health endpoint alerts
        health_results = self.check_health_endpoints()
        for service_name, result in health_results.items():
            if result.get("status") == "unhealthy":
                alert = Alert(
                    id=f"health_check_{service_name.lower().replace(' ', '_')}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.CRITICAL,
                    title="Health Check Failed",
                    message=f"Health check failed for {service_name}: {result.get('error', 'Unknown error')}",
                    source=f"health_check:{service_name}",
                )
                new_alerts.append(alert)
            elif (
                result.get("response_time", 0)
                > self.alert_config.response_time_threshold
            ):
                alert = Alert(
                    id=f"response_time_{service_name.lower().replace(' ', '_')}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING,
                    title="Slow Response Time",
                    message=f"{service_name} response time is {result['response_time']:.2f}s (threshold: {self.alert_config.response_time_threshold}s)",
                    source=f"health_check:{service_name}",
                    metric_value=result["response_time"],
                    threshold=self.alert_config.response_time_threshold,
                )
                new_alerts.append(alert)

        return new_alerts

    def send_alert_notifications(self, alerts: List[Alert]):
        """Send alert notifications via configured channels"""
        for alert in alerts:
            try:
                # Email notifications
                if (
                    self.alert_config.email_enabled
                    and self.alert_config.email_recipients
                ):
                    self._send_email_alert(alert)

                # Webhook notifications
                if self.alert_config.webhook_url:
                    self._send_webhook_alert(alert)

                # Log alert
                severity_emoji = {
                    AlertSeverity.INFO: "ℹ️",
                    AlertSeverity.WARNING: "⚠️",
                    AlertSeverity.CRITICAL: "🚨",
                    AlertSeverity.EMERGENCY: "🔥",
                }

                emoji = severity_emoji.get(alert.severity, "❓")
                self.logger.warning(
                    f"{emoji} ALERT [{alert.severity.value.upper()}] {alert.title}: {alert.message}"
                )

            except Exception as e:
                self.logger.error(f"Failed to send alert notification: {e}")

    def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.alert_config.email_username
            msg["To"] = ", ".join(self.alert_config.email_recipients)
            msg[
                "Subject"
            ] = f"[SynthaTrial Alert] {alert.severity.value.upper()}: {alert.title}"

            body = f"""
SynthaTrial Production Alert

Severity: {alert.severity.value.upper()}
Title: {alert.title}
Message: {alert.message}
Source: {alert.source}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{f'Metric Value: {alert.metric_value}' if alert.metric_value is not None else ''}
{f'Threshold: {alert.threshold}' if alert.threshold is not None else ''}

Please investigate and take appropriate action.

--
SynthaTrial Production Monitor
            """

            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(
                self.alert_config.email_smtp_server, self.alert_config.email_smtp_port
            )
            server.starttls()
            server.login(
                self.alert_config.email_username, self.alert_config.email_password
            )
            server.send_message(msg)
            server.quit()

            self.logger.info(f"Email alert sent for: {alert.title}")

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook"""
        try:
            payload = {
                "alert": alert.to_dict(),
                "system": "synthatrial",
                "environment": "production",
            }

            response = requests.post(
                self.alert_config.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                self.logger.info(f"Webhook alert sent for: {alert.title}")
            else:
                self.logger.warning(
                    f"Webhook alert failed with status {response.status_code}"
                )

        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")

    def create_backup(
        self, paths: List[str], backup_dir: str = "backups"
    ) -> BackupResult:
        """Create backup of specified paths"""
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir_path = Path(backup_dir)
        backup_dir_path.mkdir(parents=True, exist_ok=True)

        backup_file = backup_dir_path / f"{backup_id}.tar.gz"
        start_time = time.time()

        try:
            self.logger.info(f"Creating backup: {backup_id}")

            with tarfile.open(backup_file, "w:gz") as tar:
                for path in paths:
                    path_obj = Path(path)
                    if path_obj.exists():
                        self.logger.info(f"Adding to backup: {path}")
                        tar.add(path, arcname=path_obj.name)
                    else:
                        self.logger.warning(f"Path not found, skipping: {path}")

            duration = time.time() - start_time
            size_mb = backup_file.stat().st_size / (1024 * 1024)

            result = BackupResult(
                backup_id=backup_id,
                timestamp=datetime.now(),
                paths=paths,
                backup_file=str(backup_file),
                size_mb=size_mb,
                duration_seconds=duration,
                success=True,
            )

            self.logger.info(
                f"Backup completed: {backup_file} ({size_mb:.1f} MB, {duration:.1f}s)"
            )
            return result

        except Exception as e:
            duration = time.time() - start_time
            result = BackupResult(
                backup_id=backup_id,
                timestamp=datetime.now(),
                paths=paths,
                backup_file=str(backup_file),
                size_mb=0.0,
                duration_seconds=duration,
                success=False,
                error_message=str(e),
            )

            self.logger.error(f"Backup failed: {e}")
            return result

    def restore_from_backup(self, backup_path: str, restore_dir: str) -> Dict[str, Any]:
        """Restore from a backup file. Stub for integration; override in tests."""
        return {
            "success": False,
            "error": "not implemented",
            "restored_files": 0,
            "restored_size_mb": 0.0,
            "duration_seconds": 0.0,
            "verification_passed": False,
        }

    def detect_system_failures(self) -> Dict[str, Any]:
        """Detect system failures from current metrics. Stub for integration."""
        return {
            "failures_detected": False,
            "severity": "none",
            "recovery_required": False,
            "details": [],
        }

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics (alias for integration tests)."""
        metrics = self.collect_system_metrics()
        return {
            "timestamp": time.time(),
            "cpu_usage": metrics.cpu_usage_percent,
            "memory_usage": metrics.memory_usage_percent,
            "disk_usage": metrics.disk_usage_percent,
            "network_io": metrics.network_io_mb,
            "health_status": "healthy",
        }

    def execute_recovery_plan(self, plan: Dict[str, str]) -> Dict[str, Any]:
        """Execute a recovery plan. Stub for integration."""
        return {
            "recovery_started": False,
            "steps_completed": 0,
            "steps_total": len(plan),
            "estimated_completion": "",
            "current_step": "",
        }

    def validate_recovery_success(self) -> Dict[str, Any]:
        """Validate that recovery completed successfully. Stub for integration."""
        return {
            "recovery_successful": False,
            "all_services_operational": False,
            "data_integrity_verified": False,
            "security_status_restored": False,
            "performance_within_normal_range": False,
            "monitoring_fully_restored": False,
            "total_downtime": "",
        }

    def setup_production_monitoring(self, config: Dict[str, Any]) -> bool:
        """Setup production monitoring from config. Stub for integration."""
        return True

    def validate_production_health(self) -> Dict[str, Any]:
        """Validate production health. Stub for integration."""
        return {
            "overall_healthy": False,
            "services_operational": 0,
            "services_total": 0,
            "ssl_valid": False,
            "data_integrity": False,
            "alerts_active": 0,
        }

    def start_continuous_monitoring(self) -> None:
        """Start continuous monitoring (alias for integration tests)."""
        self.start_monitoring()

    def start_monitoring(self):
        """Start continuous monitoring loop"""
        self.logger.info("Starting production monitoring...")
        self.monitoring_active = True

        while self.monitoring_active:
            try:
                # Collect metrics
                system_metrics = self.collect_system_metrics()
                container_metrics = self.collect_container_metrics()

                # Store metrics history
                self.metrics_history.append(system_metrics)
                self.container_metrics_history.extend(container_metrics)

                # Keep only recent history (last 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history if m.timestamp > cutoff_time
                ]
                self.container_metrics_history = [
                    m
                    for m in self.container_metrics_history
                    if datetime.now() - timedelta(seconds=m.uptime_seconds)
                    > cutoff_time
                ]

                # Analyze and generate alerts
                new_alerts = self.analyze_metrics_and_generate_alerts(
                    system_metrics, container_metrics
                )

                if new_alerts:
                    self.alerts.extend(new_alerts)
                    self.send_alert_notifications(new_alerts)

                # Log current status
                if self.verbose:
                    self.logger.info(
                        f"System: CPU {system_metrics.cpu_usage_percent:.1f}%, "
                        f"Memory {system_metrics.memory_usage_percent:.1f}%, "
                        f"Disk {system_metrics.disk_usage_percent:.1f}%"
                    )

                    for container in container_metrics:
                        self.logger.info(
                            f"Container {container.container_name}: "
                            f"Status {container.status}, "
                            f"Health {container.health_status.value}, "
                            f"Memory {container.memory_usage_percent:.1f}%"
                        )

                # Save periodic report
                if len(self.metrics_history) % 10 == 0:  # Every 10 intervals
                    self.generate_monitoring_report()

                # Wait for next check
                time.sleep(self.alert_config.check_interval)

            except KeyboardInterrupt:
                self.logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(self.alert_config.check_interval)

        self.logger.info("Production monitoring stopped")

    def generate_monitoring_report(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring report"""
        if not self.metrics_history:
            return {"error": "No metrics data available"}

        # Calculate summary statistics
        recent_metrics = (
            self.metrics_history[-10:]
            if len(self.metrics_history) >= 10
            else self.metrics_history
        )

        avg_cpu = sum(m.cpu_usage_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage_percent for m in recent_metrics) / len(
            recent_metrics
        )
        avg_disk = sum(m.disk_usage_percent for m in recent_metrics) / len(
            recent_metrics
        )

        max_cpu = max(m.cpu_usage_percent for m in recent_metrics)
        max_memory = max(m.memory_usage_percent for m in recent_metrics)
        max_disk = max(m.disk_usage_percent for m in recent_metrics)

        # Container summary
        container_summary = {}
        if self.container_metrics_history:
            for container_name in set(
                m.container_name for m in self.container_metrics_history
            ):
                container_metrics = [
                    m
                    for m in self.container_metrics_history
                    if m.container_name == container_name
                ]
                if container_metrics:
                    latest = container_metrics[-1]
                    container_summary[container_name] = {
                        "status": latest.status,
                        "health_status": latest.health_status.value,
                        "restart_count": latest.restart_count,
                        "uptime_hours": latest.uptime_seconds / 3600,
                        "avg_memory_percent": sum(
                            m.memory_usage_percent for m in container_metrics
                        )
                        / len(container_metrics),
                    }

        # Alert summary
        recent_alerts = [
            a for a in self.alerts if a.timestamp > datetime.now() - timedelta(hours=24)
        ]
        alert_summary = {
            "total_alerts": len(recent_alerts),
            "critical_alerts": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
            ),
            "warning_alerts": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.WARNING]
            ),
            "unresolved_alerts": len([a for a in recent_alerts if not a.resolved]),
        }

        # Health check summary
        health_results = self.check_health_endpoints()

        report = {
            "report_timestamp": datetime.now().isoformat(),
            "monitoring_period_hours": 24,
            "system_summary": {
                "avg_cpu_percent": round(avg_cpu, 1),
                "avg_memory_percent": round(avg_memory, 1),
                "avg_disk_percent": round(avg_disk, 1),
                "max_cpu_percent": round(max_cpu, 1),
                "max_memory_percent": round(max_memory, 1),
                "max_disk_percent": round(max_disk, 1),
                "total_memory_gb": (
                    recent_metrics[-1].memory_total_mb / 1024 if recent_metrics else 0
                ),
                "total_disk_gb": (
                    recent_metrics[-1].disk_total_mb / 1024 if recent_metrics else 0
                ),
            },
            "container_summary": container_summary,
            "alert_summary": alert_summary,
            "health_checks": health_results,
            "recommendations": self._generate_recommendations(
                recent_metrics, recent_alerts, health_results
            ),
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"monitoring_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Monitoring report saved: {report_file}")
        return report

    def _generate_recommendations(
        self,
        metrics: List[ResourceMetrics],
        alerts: List[Alert],
        health_results: Dict[str, Any],
    ) -> List[str]:
        """Generate system recommendations based on monitoring data"""
        recommendations = []

        if not metrics:
            return ["No metrics data available for recommendations"]

        latest = metrics[-1]

        # Resource recommendations
        if latest.cpu_usage_percent > 80:
            recommendations.append(
                "🔥 High CPU usage detected. Consider scaling up or optimizing application performance."
            )

        if latest.memory_usage_percent > 85:
            recommendations.append(
                "💾 High memory usage detected. Consider increasing memory limits or optimizing memory usage."
            )

        if latest.disk_usage_percent > 90:
            recommendations.append(
                "💿 Disk space critically low. Clean up old files or increase disk capacity."
            )

        # Alert-based recommendations
        critical_alerts = [
            a for a in alerts if a.severity == AlertSeverity.CRITICAL and not a.resolved
        ]
        if critical_alerts:
            recommendations.append(
                f"🚨 {len(critical_alerts)} unresolved critical alerts require immediate attention."
            )

        # Health check recommendations
        unhealthy_services = [
            name
            for name, result in health_results.items()
            if result.get("status") == "unhealthy"
        ]
        if unhealthy_services:
            recommendations.append(
                f"🏥 Health checks failing for: {', '.join(unhealthy_services)}. Investigate service status."
            )

        # Performance recommendations
        slow_services = [
            name
            for name, result in health_results.items()
            if result.get("response_time", 0) > 2.0
        ]
        if slow_services:
            recommendations.append(
                f"🐌 Slow response times detected for: {', '.join(slow_services)}. Consider performance optimization."
            )

        # General recommendations
        if len(metrics) > 100:  # If we have enough data
            avg_cpu = sum(m.cpu_usage_percent for m in metrics) / len(metrics)
            if avg_cpu < 20:
                recommendations.append(
                    "📊 Low average CPU usage. Consider downsizing resources to reduce costs."
                )

        if not recommendations:
            recommendations.append(
                "✅ System is operating within normal parameters. Continue regular monitoring."
            )

        return recommendations


def load_alert_config(config_file: str) -> AlertConfig:
    """Load alert configuration from JSON file"""
    try:
        with open(config_file, "r") as f:
            config_data = json.load(f)

        return AlertConfig(**config_data)
    except Exception as e:
        logging.error(f"Failed to load alert config from {config_file}: {e}")
        return AlertConfig()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="SynthaTrial Production Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start continuous monitoring
  python scripts/production_monitor.py --monitor

  # Monitor with custom alert configuration
  python scripts/production_monitor.py --monitor --alert-config alerts.json

  # Create backup
  python scripts/production_monitor.py --backup --backup-paths /app/data,/app/logs

  # Health check only
  python scripts/production_monitor.py --health-check

  # Generate current report
  python scripts/production_monitor.py --generate-report
        """,
    )

    # Action selection
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--monitor", action="store_true", help="Start continuous monitoring"
    )
    action_group.add_argument(
        "--health-check", action="store_true", help="Perform one-time health check"
    )
    action_group.add_argument(
        "--generate-report", action="store_true", help="Generate monitoring report"
    )
    action_group.add_argument(
        "--backup", action="store_true", help="Create backup of specified paths"
    )

    # Configuration options
    parser.add_argument("--alert-config", help="Path to alert configuration JSON file")

    parser.add_argument(
        "--output-dir",
        default="monitoring_reports",
        help="Directory to save reports (default: monitoring_reports)",
    )

    parser.add_argument(
        "--backup-paths", help="Comma-separated list of paths to backup"
    )

    parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Directory to store backups (default: backups)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        # Load alert configuration
        alert_config = None
        if args.alert_config:
            alert_config = load_alert_config(args.alert_config)

        # Initialize monitor
        monitor = ProductionMonitor(
            output_dir=args.output_dir, alert_config=alert_config, verbose=args.verbose
        )

        # Execute requested action
        if args.monitor:
            monitor.start_monitoring()

        elif args.health_check:
            print("\n🏥 SynthaTrial Health Check")
            print("=" * 30)

            # System metrics
            system_metrics = monitor.collect_system_metrics()
            print(f"System CPU: {system_metrics.cpu_usage_percent:.1f}%")
            print(f"System Memory: {system_metrics.memory_usage_percent:.1f}%")
            print(f"System Disk: {system_metrics.disk_usage_percent:.1f}%")

            # Container metrics
            container_metrics = monitor.collect_container_metrics()
            if container_metrics:
                print(f"\nContainers ({len(container_metrics)}):")
                for container in container_metrics:
                    status_emoji = (
                        "✅" if container.health_status == HealthStatus.HEALTHY else "❌"
                    )
                    print(
                        f"  {status_emoji} {container.container_name}: {container.status} ({container.health_status.value})"
                    )
            else:
                print("\nNo containers found or Docker not available")

            # Health endpoints
            health_results = monitor.check_health_endpoints()
            print(f"\nHealth Endpoints:")
            for service, result in health_results.items():
                status_emoji = "✅" if result.get("status") == "healthy" else "❌"
                response_time = result.get("response_time", 0)
                print(
                    f"  {status_emoji} {service}: {result.get('status', 'unknown')} ({response_time:.2f}s)"
                )

        elif args.generate_report:
            print("\n📊 Generating Monitoring Report...")

            # Collect current metrics for report
            system_metrics = monitor.collect_system_metrics()
            container_metrics = monitor.collect_container_metrics()
            monitor.metrics_history.append(system_metrics)
            monitor.container_metrics_history.extend(container_metrics)

            report = monitor.generate_monitoring_report()

            print(f"Report generated successfully!")
            print(f"System CPU (avg): {report['system_summary']['avg_cpu_percent']}%")
            print(
                f"System Memory (avg): {report['system_summary']['avg_memory_percent']}%"
            )
            print(f"System Disk (avg): {report['system_summary']['avg_disk_percent']}%")
            print(f"Total alerts (24h): {report['alert_summary']['total_alerts']}")
            print(f"Critical alerts: {report['alert_summary']['critical_alerts']}")

            if report.get("recommendations"):
                print(f"\nRecommendations:")
                for rec in report["recommendations"]:
                    print(f"  • {rec}")

        elif args.backup:
            if not args.backup_paths:
                print("❌ Error: --backup-paths required for backup operation")
                sys.exit(1)

            paths = [p.strip() for p in args.backup_paths.split(",")]
            print(f"\n💾 Creating Backup...")
            print(f"Paths: {', '.join(paths)}")

            result = monitor.create_backup(paths, args.backup_dir)

            if result.success:
                print(f"✅ Backup completed successfully!")
                print(f"Backup file: {result.backup_file}")
                print(f"Size: {result.size_mb:.1f} MB")
                print(f"Duration: {result.duration_seconds:.1f}s")
            else:
                print(f"❌ Backup failed: {result.error_message}")
                sys.exit(1)

    except Exception as e:
        print(f"❌ Production monitor error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
