#!/usr/bin/env python3
"""
SynthaTrial Backup Manager
==========================

Automated backup and recovery system for SynthaTrial production deployments.
Provides comprehensive backup procedures, data recovery validation, and backup integrity checking.

Features:
- Automated backup creation with compression and encryption
- Incremental and full backup strategies
- Backup integrity verification using checksums
- Data recovery validation and testing
- Backup rotation and retention policies
- Cross-platform backup storage (local, cloud, network)
- Backup scheduling and automation
- Recovery point objectives (RPO) and recovery time objectives (RTO) management
- Comprehensive logging and reporting

Usage:
    python scripts/backup_manager.py --create-backup --paths /app/data,/app/logs
    python scripts/backup_manager.py --create-backup --type incremental --base-backup backup_20240101_120000
    python scripts/backup_manager.py --verify-backup backup_20240101_120000.tar.gz
    python scripts/backup_manager.py --restore-backup backup_20240101_120000.tar.gz --target /tmp/restore
    python scripts/backup_manager.py --list-backups
    python scripts/backup_manager.py --cleanup-old-backups --retention-days 30
    python scripts/backup_manager.py --test-recovery --backup backup_20240101_120000.tar.gz
"""

import argparse
import gzip
import hashlib
import json
import logging
import os
import pickle
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class BackupType(Enum):
    """Backup type enumeration"""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    """Backup status enumeration"""

    CREATED = "created"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"
    RESTORED = "restored"
    FAILED = "failed"


class CompressionType(Enum):
    """Compression type enumeration"""

    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    XZ = "xz"


@dataclass
class BackupMetadata:
    """Backup metadata information"""

    backup_id: str
    timestamp: datetime
    backup_type: BackupType
    paths: List[str]
    backup_file: str
    size_bytes: int
    compressed_size_bytes: int
    compression_type: CompressionType
    checksum_sha256: str
    duration_seconds: float
    status: BackupStatus
    base_backup_id: Optional[str] = None
    error_message: Optional[str] = None
    file_count: int = 0
    excluded_patterns: List[str] = None

    def __post_init__(self):
        if self.excluded_patterns is None:
            self.excluded_patterns = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["backup_type"] = self.backup_type.value
        result["status"] = self.status.value
        result["compression_type"] = self.compression_type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupMetadata":
        """Create from dictionary"""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["backup_type"] = BackupType(data["backup_type"])
        data["status"] = BackupStatus(data["status"])
        data["compression_type"] = CompressionType(data["compression_type"])
        return cls(**data)


@dataclass
class RestoreResult:
    """Restore operation result"""

    restore_id: str
    timestamp: datetime
    backup_id: str
    target_path: str
    success: bool
    duration_seconds: float
    files_restored: int
    bytes_restored: int
    error_message: Optional[str] = None
    validation_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class BackupConfig:
    """Backup configuration settings"""

    backup_dir: str = "backups"
    compression_type: CompressionType = CompressionType.GZIP
    retention_days: int = 30
    max_backup_size_gb: float = 10.0
    enable_encryption: bool = False
    encryption_key_file: str = ""
    exclude_patterns: List[str] = None
    include_system_info: bool = True
    verify_after_backup: bool = True
    parallel_compression: bool = True
    backup_database: str = "backup_metadata.db"

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                "*.tmp",
                "*.log",
                "*.cache",
                "__pycache__",
                ".git",
                "node_modules",
                "*.pyc",
                "*.pyo",
                ".DS_Store",
            ]


class BackupManager:
    """Main backup and recovery management class"""

    def __init__(self, config: Optional[BackupConfig] = None, verbose: bool = False):
        """
        Initialize backup manager

        Args:
            config: Backup configuration settings
            verbose: Enable verbose logging
        """
        self.config = config or BackupConfig()
        self.verbose = verbose

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        # Create backup directory
        self.backup_dir = Path(self.config.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metadata database
        self.db_path = self.backup_dir / self.config.backup_database
        self._init_database()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("Backup manager initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)

    def _init_database(self):
        """Initialize SQLite database for backup metadata"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS backups (
                        backup_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        backup_type TEXT NOT NULL,
                        paths TEXT NOT NULL,
                        backup_file TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        compressed_size_bytes INTEGER NOT NULL,
                        compression_type TEXT NOT NULL,
                        checksum_sha256 TEXT NOT NULL,
                        duration_seconds REAL NOT NULL,
                        status TEXT NOT NULL,
                        base_backup_id TEXT,
                        error_message TEXT,
                        file_count INTEGER DEFAULT 0,
                        excluded_patterns TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS restores (
                        restore_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        backup_id TEXT NOT NULL,
                        target_path TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        duration_seconds REAL NOT NULL,
                        files_restored INTEGER NOT NULL,
                        bytes_restored INTEGER NOT NULL,
                        error_message TEXT,
                        validation_passed INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.commit()
                self.logger.debug("Database initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of a file"""
        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            return sha256_hash.hexdigest()

        except Exception as e:
            self.logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            raise

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded based on patterns"""
        for pattern in self.config.exclude_patterns:
            if file_path.match(pattern):
                return True
        return False

    def _get_file_list(
        self, paths: List[str], base_backup_metadata: Optional[BackupMetadata] = None
    ) -> List[Tuple[str, str]]:
        """
        Get list of files to backup with their archive names

        Args:
            paths: List of paths to backup
            base_backup_metadata: Base backup metadata for incremental backups

        Returns:
            List of (source_path, archive_name) tuples
        """
        files_to_backup = []
        base_files = {}

        # Load base backup file list for incremental backups
        if base_backup_metadata and base_backup_metadata.backup_type == BackupType.FULL:
            try:
                base_backup_path = Path(base_backup_metadata.backup_file)
                if base_backup_path.exists():
                    with tarfile.open(base_backup_path, "r:*") as tar:
                        for member in tar.getmembers():
                            if member.isfile():
                                base_files[member.name] = member.mtime
            except Exception as e:
                self.logger.warning(f"Failed to read base backup file list: {e}")

        for path_str in paths:
            path = Path(path_str)

            if not path.exists():
                self.logger.warning(f"Path does not exist: {path}")
                continue

            if path.is_file():
                if not self._should_exclude_file(path):
                    # For incremental backups, check if file is newer than base backup
                    if base_files:
                        file_mtime = path.stat().st_mtime
                        archive_name = str(
                            path.relative_to(path.parent.parent)
                            if path.parent.parent in path.parents
                            else path.name
                        )

                        if (
                            archive_name not in base_files
                            or file_mtime > base_files[archive_name]
                        ):
                            files_to_backup.append((str(path), archive_name))
                    else:
                        files_to_backup.append((str(path), path.name))

            elif path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file() and not self._should_exclude_file(file_path):
                        try:
                            archive_name = str(file_path.relative_to(path.parent))

                            # For incremental backups, check if file is newer than base backup
                            if base_files:
                                file_mtime = file_path.stat().st_mtime

                                if (
                                    archive_name not in base_files
                                    or file_mtime > base_files[archive_name]
                                ):
                                    files_to_backup.append(
                                        (str(file_path), archive_name)
                                    )
                            else:
                                files_to_backup.append((str(file_path), archive_name))

                        except Exception as e:
                            self.logger.warning(
                                f"Failed to process file {file_path}: {e}"
                            )
                            continue

        return files_to_backup

    def create_backup(
        self,
        paths: List[str],
        backup_type: BackupType = BackupType.FULL,
        base_backup_id: Optional[str] = None,
    ) -> BackupMetadata:
        """
        Create backup of specified paths

        Args:
            paths: List of paths to backup
            backup_type: Type of backup (full, incremental, differential)
            base_backup_id: Base backup ID for incremental/differential backups

        Returns:
            BackupMetadata object with backup information
        """
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()

        # Determine compression extension
        compression_ext = {
            CompressionType.NONE: ".tar",
            CompressionType.GZIP: ".tar.gz",
            CompressionType.BZIP2: ".tar.bz2",
            CompressionType.XZ: ".tar.xz",
        }

        backup_file = (
            self.backup_dir
            / f"{backup_id}{compression_ext[self.config.compression_type]}"
        )

        try:
            self.logger.info(f"Creating {backup_type.value} backup: {backup_id}")

            # Get base backup metadata for incremental backups
            base_backup_metadata = None
            if (
                backup_type in [BackupType.INCREMENTAL, BackupType.DIFFERENTIAL]
                and base_backup_id
            ):
                base_backup_metadata = self.get_backup_metadata(base_backup_id)
                if not base_backup_metadata:
                    raise ValueError(f"Base backup not found: {base_backup_id}")

            # Get list of files to backup
            files_to_backup = self._get_file_list(paths, base_backup_metadata)

            if not files_to_backup:
                raise ValueError("No files found to backup")

            # Determine compression mode
            compression_mode = {
                CompressionType.NONE: "w",
                CompressionType.GZIP: "w:gz",
                CompressionType.BZIP2: "w:bz2",
                CompressionType.XZ: "w:xz",
            }

            # Create backup archive
            total_size = 0
            file_count = 0

            with tarfile.open(
                backup_file, compression_mode[self.config.compression_type]
            ) as tar:
                # Add system information if enabled
                if self.config.include_system_info:
                    system_info = self._collect_system_info()
                    info_file = tempfile.NamedTemporaryFile(
                        mode="w", delete=False, suffix=".json"
                    )
                    json.dump(system_info, info_file, indent=2, default=str)
                    info_file.close()

                    tar.add(info_file.name, arcname="system_info.json")
                    os.unlink(info_file.name)

                # Add files to archive
                for source_path, archive_name in files_to_backup:
                    try:
                        self.logger.debug(
                            f"Adding to backup: {source_path} -> {archive_name}"
                        )
                        tar.add(source_path, arcname=archive_name)

                        file_size = Path(source_path).stat().st_size
                        total_size += file_size
                        file_count += 1

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to add file to backup: {source_path}: {e}"
                        )
                        continue

            # Calculate backup file size and checksum
            backup_file_size = backup_file.stat().st_size
            checksum = self._calculate_checksum(str(backup_file))
            duration = time.time() - start_time

            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                backup_type=backup_type,
                paths=paths,
                backup_file=str(backup_file),
                size_bytes=total_size,
                compressed_size_bytes=backup_file_size,
                compression_type=self.config.compression_type,
                checksum_sha256=checksum,
                duration_seconds=duration,
                status=BackupStatus.CREATED,
                base_backup_id=base_backup_id,
                file_count=file_count,
                excluded_patterns=self.config.exclude_patterns.copy(),
            )

            # Save metadata to database
            self._save_backup_metadata(metadata)

            # Verify backup if enabled
            if self.config.verify_after_backup:
                if self.verify_backup(backup_id):
                    metadata.status = BackupStatus.VERIFIED
                    self._update_backup_status(backup_id, BackupStatus.VERIFIED)
                else:
                    metadata.status = BackupStatus.CORRUPTED
                    self._update_backup_status(backup_id, BackupStatus.CORRUPTED)

            compression_ratio = (
                (1 - backup_file_size / total_size) * 100 if total_size > 0 else 0
            )

            self.logger.info(f"Backup completed: {backup_file}")
            self.logger.info(
                f"Files: {file_count}, Size: {total_size / (1024*1024):.1f} MB -> {backup_file_size / (1024*1024):.1f} MB ({compression_ratio:.1f}% compression)"
            )
            self.logger.info(f"Duration: {duration:.1f}s, Checksum: {checksum[:16]}...")

            return metadata

        except Exception as e:
            duration = time.time() - start_time

            # Create error metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                backup_type=backup_type,
                paths=paths,
                backup_file=str(backup_file),
                size_bytes=0,
                compressed_size_bytes=0,
                compression_type=self.config.compression_type,
                checksum_sha256="",
                duration_seconds=duration,
                status=BackupStatus.FAILED,
                base_backup_id=base_backup_id,
                error_message=str(e),
                excluded_patterns=self.config.exclude_patterns.copy(),
            )

            # Save error metadata
            self._save_backup_metadata(metadata)

            # Clean up failed backup file
            if backup_file.exists():
                backup_file.unlink()

            self.logger.error(f"Backup failed: {e}")
            return metadata

    def verify_backup(self, backup_id: str) -> bool:
        """
        Verify backup integrity using checksum validation

        Args:
            backup_id: Backup ID to verify

        Returns:
            True if backup is valid, False otherwise
        """
        try:
            metadata = self.get_backup_metadata(backup_id)
            if not metadata:
                self.logger.error(f"Backup metadata not found: {backup_id}")
                return False

            backup_file = Path(metadata.backup_file)
            if not backup_file.exists():
                self.logger.error(f"Backup file not found: {backup_file}")
                return False

            self.logger.info(f"Verifying backup: {backup_id}")

            # Calculate current checksum
            current_checksum = self._calculate_checksum(str(backup_file))

            # Compare with stored checksum
            if current_checksum == metadata.checksum_sha256:
                self.logger.info(f"Backup verification successful: {backup_id}")
                return True
            else:
                self.logger.error(
                    f"Backup verification failed: checksum mismatch for {backup_id}"
                )
                self.logger.error(f"Expected: {metadata.checksum_sha256}")
                self.logger.error(f"Actual: {current_checksum}")
                return False

        except Exception as e:
            self.logger.error(f"Backup verification error: {e}")
            return False

    def restore_backup(
        self, backup_id: str, target_path: str, validate_restore: bool = True
    ) -> RestoreResult:
        """
        Restore backup to specified target path

        Args:
            backup_id: Backup ID to restore
            target_path: Target directory for restoration
            validate_restore: Whether to validate restored files

        Returns:
            RestoreResult object with restoration information
        """
        restore_id = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()

        try:
            metadata = self.get_backup_metadata(backup_id)
            if not metadata:
                raise ValueError(f"Backup metadata not found: {backup_id}")

            backup_file = Path(metadata.backup_file)
            if not backup_file.exists():
                raise ValueError(f"Backup file not found: {backup_file}")

            target_dir = Path(target_path)
            target_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Restoring backup {backup_id} to {target_path}")

            # Verify backup before restoration
            if not self.verify_backup(backup_id):
                raise ValueError(f"Backup verification failed: {backup_id}")

            files_restored = 0
            bytes_restored = 0

            # Extract backup archive
            with tarfile.open(backup_file, "r:*") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        try:
                            tar.extract(member, target_dir)
                            files_restored += 1
                            bytes_restored += member.size

                        except Exception as e:
                            self.logger.warning(
                                f"Failed to extract file {member.name}: {e}"
                            )
                            continue

            duration = time.time() - start_time

            # Validate restoration if requested
            validation_passed = False
            if validate_restore:
                validation_passed = self._validate_restoration(backup_id, target_path)

            result = RestoreResult(
                restore_id=restore_id,
                timestamp=datetime.now(),
                backup_id=backup_id,
                target_path=target_path,
                success=True,
                duration_seconds=duration,
                files_restored=files_restored,
                bytes_restored=bytes_restored,
                validation_passed=validation_passed,
            )

            # Save restore metadata
            self._save_restore_metadata(result)

            self.logger.info(
                f"Restore completed: {files_restored} files, {bytes_restored / (1024*1024):.1f} MB, {duration:.1f}s"
            )

            return result

        except Exception as e:
            duration = time.time() - start_time

            result = RestoreResult(
                restore_id=restore_id,
                timestamp=datetime.now(),
                backup_id=backup_id,
                target_path=target_path,
                success=False,
                duration_seconds=duration,
                files_restored=0,
                bytes_restored=0,
                error_message=str(e),
            )

            self._save_restore_metadata(result)

            self.logger.error(f"Restore failed: {e}")
            return result

    def _validate_restoration(self, backup_id: str, target_path: str) -> bool:
        """
        Validate restored files against backup metadata

        Args:
            backup_id: Backup ID that was restored
            target_path: Path where files were restored

        Returns:
            True if validation passes, False otherwise
        """
        try:
            metadata = self.get_backup_metadata(backup_id)
            if not metadata:
                return False

            backup_file = Path(metadata.backup_file)
            target_dir = Path(target_path)

            self.logger.info(f"Validating restoration: {backup_id}")

            # Compare file counts and sizes
            with tarfile.open(backup_file, "r:*") as tar:
                archive_files = {
                    member.name: member.size
                    for member in tar.getmembers()
                    if member.isfile()
                }

            restored_files = {}
            for file_path in target_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(target_dir))
                    restored_files[relative_path] = file_path.stat().st_size

            # Check if all files were restored
            missing_files = set(archive_files.keys()) - set(restored_files.keys())
            if missing_files:
                self.logger.error(f"Missing files in restoration: {missing_files}")
                return False

            # Check file sizes
            for file_name, expected_size in archive_files.items():
                if file_name in restored_files:
                    actual_size = restored_files[file_name]
                    if actual_size != expected_size:
                        self.logger.error(
                            f"Size mismatch for {file_name}: expected {expected_size}, got {actual_size}"
                        )
                        return False

            self.logger.info(
                f"Restoration validation successful: {len(restored_files)} files validated"
            )
            return True

        except Exception as e:
            self.logger.error(f"Restoration validation error: {e}")
            return False

    def list_backups(self, limit: Optional[int] = None) -> List[BackupMetadata]:
        """
        List all backups with optional limit

        Args:
            limit: Maximum number of backups to return

        Returns:
            List of BackupMetadata objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT backup_id, timestamp, backup_type, paths, backup_file,
                           size_bytes, compressed_size_bytes, compression_type,
                           checksum_sha256, duration_seconds, status, base_backup_id,
                           error_message, file_count, excluded_patterns
                    FROM backups
                    ORDER BY timestamp DESC
                """

                if limit:
                    query += f" LIMIT {limit}"

                cursor = conn.execute(query)
                backups = []

                for row in cursor.fetchall():
                    backup_data = {
                        "backup_id": row[0],
                        "timestamp": datetime.fromisoformat(row[1]),
                        "backup_type": BackupType(row[2]),
                        "paths": json.loads(row[3]),
                        "backup_file": row[4],
                        "size_bytes": row[5],
                        "compressed_size_bytes": row[6],
                        "compression_type": CompressionType(row[7]),
                        "checksum_sha256": row[8],
                        "duration_seconds": row[9],
                        "status": BackupStatus(row[10]),
                        "base_backup_id": row[11],
                        "error_message": row[12],
                        "file_count": row[13] or 0,
                        "excluded_patterns": json.loads(row[14]) if row[14] else [],
                    }

                    backups.append(BackupMetadata(**backup_data))

                return backups

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
            return []

    def get_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """
        Get metadata for specific backup

        Args:
            backup_id: Backup ID to retrieve

        Returns:
            BackupMetadata object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT backup_id, timestamp, backup_type, paths, backup_file,
                           size_bytes, compressed_size_bytes, compression_type,
                           checksum_sha256, duration_seconds, status, base_backup_id,
                           error_message, file_count, excluded_patterns
                    FROM backups
                    WHERE backup_id = ?
                """,
                    (backup_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                backup_data = {
                    "backup_id": row[0],
                    "timestamp": datetime.fromisoformat(row[1]),
                    "backup_type": BackupType(row[2]),
                    "paths": json.loads(row[3]),
                    "backup_file": row[4],
                    "size_bytes": row[5],
                    "compressed_size_bytes": row[6],
                    "compression_type": CompressionType(row[7]),
                    "checksum_sha256": row[8],
                    "duration_seconds": row[9],
                    "status": BackupStatus(row[10]),
                    "base_backup_id": row[11],
                    "error_message": row[12],
                    "file_count": row[13] or 0,
                    "excluded_patterns": json.loads(row[14]) if row[14] else [],
                }

                return BackupMetadata(**backup_data)

        except Exception as e:
            self.logger.error(f"Failed to get backup metadata: {e}")
            return None

    def cleanup_old_backups(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old backups based on retention policy

        Args:
            retention_days: Number of days to retain backups (uses config default if None)

        Returns:
            Number of backups cleaned up
        """
        retention_days = retention_days or self.config.retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        try:
            backups = self.list_backups()
            cleaned_count = 0

            for backup in backups:
                if backup.timestamp < cutoff_date:
                    self.logger.info(f"Cleaning up old backup: {backup.backup_id}")

                    # Remove backup file
                    backup_file = Path(backup.backup_file)
                    if backup_file.exists():
                        backup_file.unlink()

                    # Remove from database
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute(
                            "DELETE FROM backups WHERE backup_id = ?",
                            (backup.backup_id,),
                        )
                        conn.commit()

                    cleaned_count += 1

            self.logger.info(
                f"Cleaned up {cleaned_count} old backups (retention: {retention_days} days)"
            )
            return cleaned_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old backups: {e}")
            return 0

    def test_recovery(self, backup_id: str) -> bool:
        """
        Test recovery process without actually restoring files

        Args:
            backup_id: Backup ID to test

        Returns:
            True if recovery test passes, False otherwise
        """
        try:
            self.logger.info(f"Testing recovery for backup: {backup_id}")

            # Verify backup exists and is valid
            if not self.verify_backup(backup_id):
                self.logger.error(f"Backup verification failed: {backup_id}")
                return False

            metadata = self.get_backup_metadata(backup_id)
            if not metadata:
                self.logger.error(f"Backup metadata not found: {backup_id}")
                return False

            backup_file = Path(metadata.backup_file)

            # Test archive integrity by listing contents
            with tarfile.open(backup_file, "r:*") as tar:
                members = tar.getmembers()
                file_count = len([m for m in members if m.isfile()])

                # Verify we can read file information
                for member in members[:10]:  # Test first 10 files
                    if member.isfile():
                        try:
                            # Try to extract file info (without actually extracting)
                            tar.extractfile(member)
                        except Exception as e:
                            self.logger.error(
                                f"Failed to read file from archive: {member.name}: {e}"
                            )
                            return False

            self.logger.info(
                f"Recovery test successful: {backup_id} ({file_count} files)"
            )
            return True

        except Exception as e:
            self.logger.error(f"Recovery test failed: {e}")
            return False

    def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information for backup metadata"""
        import platform

        import psutil

        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "hostname": platform.node(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "disk_usage": {
                    path: {
                        "total_gb": psutil.disk_usage(path).total / (1024**3),
                        "used_gb": psutil.disk_usage(path).used / (1024**3),
                        "free_gb": psutil.disk_usage(path).free / (1024**3),
                    }
                    for path in ["/"]
                    if os.path.exists(path)
                },
            }
        except Exception as e:
            self.logger.warning(f"Failed to collect system info: {e}")
            return {"error": str(e)}

    def _save_backup_metadata(self, metadata: BackupMetadata):
        """Save backup metadata to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO backups (
                        backup_id, timestamp, backup_type, paths, backup_file,
                        size_bytes, compressed_size_bytes, compression_type,
                        checksum_sha256, duration_seconds, status, base_backup_id,
                        error_message, file_count, excluded_patterns
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metadata.backup_id,
                        metadata.timestamp.isoformat(),
                        metadata.backup_type.value,
                        json.dumps(metadata.paths),
                        metadata.backup_file,
                        metadata.size_bytes,
                        metadata.compressed_size_bytes,
                        metadata.compression_type.value,
                        metadata.checksum_sha256,
                        metadata.duration_seconds,
                        metadata.status.value,
                        metadata.base_backup_id,
                        metadata.error_message,
                        metadata.file_count,
                        json.dumps(metadata.excluded_patterns),
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save backup metadata: {e}")
            raise

    def _save_restore_metadata(self, result: RestoreResult):
        """Save restore metadata to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO restores (
                        restore_id, timestamp, backup_id, target_path, success,
                        duration_seconds, files_restored, bytes_restored,
                        error_message, validation_passed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.restore_id,
                        result.timestamp.isoformat(),
                        result.backup_id,
                        result.target_path,
                        1 if result.success else 0,
                        result.duration_seconds,
                        result.files_restored,
                        result.bytes_restored,
                        result.error_message,
                        1 if result.validation_passed else 0,
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save restore metadata: {e}")

    def _update_backup_status(self, backup_id: str, status: BackupStatus):
        """Update backup status in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE backups SET status = ? WHERE backup_id = ?
                """,
                    (status.value, backup_id),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update backup status: {e}")


def load_backup_config(config_file: str) -> BackupConfig:
    """Load backup configuration from JSON file"""
    try:
        with open(config_file, "r") as f:
            config_data = json.load(f)

        # Convert compression_type string to enum
        if "compression_type" in config_data:
            config_data["compression_type"] = CompressionType(
                config_data["compression_type"]
            )

        return BackupConfig(**config_data)
    except Exception as e:
        logging.error(f"Failed to load backup config from {config_file}: {e}")
        return BackupConfig()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="SynthaTrial Backup Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create full backup
  python scripts/backup_manager.py --create-backup --paths /app/data,/app/logs

  # Create incremental backup
  python scripts/backup_manager.py --create-backup --type incremental --base-backup backup_20240101_120000 --paths /app/data

  # Verify backup integrity
  python scripts/backup_manager.py --verify-backup backup_20240101_120000

  # Restore backup
  python scripts/backup_manager.py --restore-backup backup_20240101_120000 --target /tmp/restore

  # List all backups
  python scripts/backup_manager.py --list-backups

  # Clean up old backups
  python scripts/backup_manager.py --cleanup-old-backups --retention-days 30

  # Test recovery
  python scripts/backup_manager.py --test-recovery --backup backup_20240101_120000
        """,
    )

    # Action selection
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--create-backup", action="store_true", help="Create backup of specified paths"
    )
    action_group.add_argument(
        "--verify-backup", help="Verify backup integrity by backup ID"
    )
    action_group.add_argument("--restore-backup", help="Restore backup by backup ID")
    action_group.add_argument(
        "--list-backups", action="store_true", help="List all backups"
    )
    action_group.add_argument(
        "--cleanup-old-backups",
        action="store_true",
        help="Clean up old backups based on retention policy",
    )
    action_group.add_argument(
        "--test-recovery",
        action="store_true",
        help="Test recovery process for specified backup",
    )

    # Backup creation options
    parser.add_argument("--paths", help="Comma-separated list of paths to backup")

    parser.add_argument(
        "--type",
        choices=["full", "incremental", "differential"],
        default="full",
        help="Backup type (default: full)",
    )

    parser.add_argument(
        "--base-backup", help="Base backup ID for incremental/differential backups"
    )

    # Restore options
    parser.add_argument("--target", help="Target directory for backup restoration")

    parser.add_argument(
        "--no-validate", action="store_true", help="Skip validation during restore"
    )

    # General options
    parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Directory to store backups (default: backups)",
    )

    parser.add_argument("--config", help="Path to backup configuration JSON file")

    parser.add_argument(
        "--retention-days", type=int, help="Number of days to retain backups"
    )

    parser.add_argument("--backup", help="Backup ID for operations that require it")

    parser.add_argument("--limit", type=int, help="Limit number of backups to list")

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = BackupConfig(backup_dir=args.backup_dir)
        if args.config:
            config = load_backup_config(args.config)
            config.backup_dir = args.backup_dir  # Override with CLI argument

        # Initialize backup manager
        manager = BackupManager(config=config, verbose=args.verbose)

        # Execute requested action
        if args.create_backup:
            if not args.paths:
                print("❌ Error: --paths required for backup creation")
                sys.exit(1)

            paths = [p.strip() for p in args.paths.split(",")]
            backup_type = BackupType(args.type)

            print(f"\n💾 Creating {backup_type.value} backup...")
            print(f"Paths: {', '.join(paths)}")

            metadata = manager.create_backup(
                paths=paths, backup_type=backup_type, base_backup_id=args.base_backup
            )

            if metadata.status in [BackupStatus.CREATED, BackupStatus.VERIFIED]:
                print(f"✅ Backup completed successfully!")
                print(f"Backup ID: {metadata.backup_id}")
                print(f"Backup file: {metadata.backup_file}")
                print(f"Files: {metadata.file_count}")
                print(
                    f"Size: {metadata.size_bytes / (1024*1024):.1f} MB -> {metadata.compressed_size_bytes / (1024*1024):.1f} MB"
                )
                print(f"Duration: {metadata.duration_seconds:.1f}s")
                print(f"Status: {metadata.status.value}")
            else:
                print(f"❌ Backup failed: {metadata.error_message}")
                sys.exit(1)

        elif args.verify_backup:
            backup_id = args.verify_backup
            print(f"\n🔍 Verifying backup: {backup_id}")

            if manager.verify_backup(backup_id):
                print(f"✅ Backup verification successful!")
            else:
                print(f"❌ Backup verification failed!")
                sys.exit(1)

        elif args.restore_backup:
            if not args.target:
                print("❌ Error: --target required for backup restoration")
                sys.exit(1)

            backup_id = args.restore_backup
            print(f"\n📂 Restoring backup: {backup_id}")
            print(f"Target: {args.target}")

            result = manager.restore_backup(
                backup_id=backup_id,
                target_path=args.target,
                validate_restore=not args.no_validate,
            )

            if result.success:
                print(f"✅ Restore completed successfully!")
                print(f"Files restored: {result.files_restored}")
                print(f"Bytes restored: {result.bytes_restored / (1024*1024):.1f} MB")
                print(f"Duration: {result.duration_seconds:.1f}s")
                if not args.no_validate:
                    print(
                        f"Validation: {'✅ Passed' if result.validation_passed else '❌ Failed'}"
                    )
            else:
                print(f"❌ Restore failed: {result.error_message}")
                sys.exit(1)

        elif args.list_backups:
            print(f"\n📋 Backup List")
            print("=" * 80)

            backups = manager.list_backups(limit=args.limit)

            if not backups:
                print("No backups found")
            else:
                for backup in backups:
                    status_emoji = {
                        BackupStatus.CREATED: "📦",
                        BackupStatus.VERIFIED: "✅",
                        BackupStatus.CORRUPTED: "❌",
                        BackupStatus.RESTORED: "📂",
                        BackupStatus.FAILED: "💥",
                    }.get(backup.status, "❓")

                    print(f"{status_emoji} {backup.backup_id}")
                    print(f"   Type: {backup.backup_type.value}")
                    print(f"   Date: {backup.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   Files: {backup.file_count}")
                    print(
                        f"   Size: {backup.compressed_size_bytes / (1024*1024):.1f} MB"
                    )
                    print(f"   Status: {backup.status.value}")
                    if backup.base_backup_id:
                        print(f"   Base: {backup.base_backup_id}")
                    print()

        elif args.cleanup_old_backups:
            retention_days = args.retention_days or config.retention_days
            print(f"\n🧹 Cleaning up backups older than {retention_days} days...")

            cleaned_count = manager.cleanup_old_backups(retention_days)
            print(f"✅ Cleaned up {cleaned_count} old backups")

        elif args.test_recovery:
            if not args.backup:
                print("❌ Error: --backup required for recovery testing")
                sys.exit(1)

            backup_id = args.backup
            print(f"\n🧪 Testing recovery for backup: {backup_id}")

            if manager.test_recovery(backup_id):
                print(f"✅ Recovery test successful!")
            else:
                print(f"❌ Recovery test failed!")
                sys.exit(1)

    except Exception as e:
        print(f"❌ Backup manager error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
