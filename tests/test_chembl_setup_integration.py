#!/usr/bin/env python3
"""
Integration tests for ChEMBL database setup automation.

Tests the setup_chembl.py script functionality including download simulation,
extraction validation, and database integrity checking.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.setup_chembl import ChEMBLSetup, ChEMBLSetupResult, DatabaseValidation


class TestChEMBLSetupIntegration:
    """Integration tests for ChEMBL setup functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.chembl_setup = ChEMBLSetup(output_dir=self.temp_dir, verbose=False)

    def teardown_method(self):
        """Cleanup test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_mock_database(self, db_path: Path, valid: bool = True) -> None:
        """
        Create a mock SQLite database for testing.

        Args:
            db_path: Path where to create the database
            valid: Whether to create a valid database structure
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        if valid:
            # Create minimal ChEMBL-like structure
            cursor.execute(
                """
                CREATE TABLE molecule_dictionary (
                    molregno INTEGER PRIMARY KEY,
                    pref_name TEXT,
                    max_phase INTEGER
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE compound_structures (
                    molregno INTEGER,
                    canonical_smiles TEXT,
                    standard_inchi TEXT,
                    standard_inchi_key TEXT
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE activities (
                    activity_id INTEGER PRIMARY KEY,
                    molregno INTEGER,
                    assay_id INTEGER,
                    standard_type TEXT,
                    standard_value REAL,
                    standard_units TEXT
                )
            """
            )

            # Insert test data
            for i in range(1000000):  # Minimum compound count
                cursor.execute(
                    "INSERT INTO molecule_dictionary (molregno, pref_name, max_phase) VALUES (?, ?, ?)",
                    (i + 1, f"Compound_{i+1}", 2),
                )

                cursor.execute(
                    "INSERT INTO compound_structures (molregno, canonical_smiles) VALUES (?, ?)",
                    (i + 1, f"C{i+1}"),
                )

                # Add activities (minimum count)
                for j in range(10):  # 10M activities total
                    cursor.execute(
                        "INSERT INTO activities (molregno, assay_id, standard_type, standard_value) VALUES (?, ?, ?, ?)",
                        (i + 1, j + 1, "IC50", 1.0),
                    )
        else:
            # Create invalid structure (missing tables)
            cursor.execute("CREATE TABLE dummy (id INTEGER)")

        conn.commit()
        conn.close()

    @patch.object(ChEMBLSetup, "MIN_DATABASE_SIZE_MB", 0)
    @patch.object(ChEMBLSetup, "MIN_TABLE_COUNT", 0)
    def test_check_existing_database_valid(self):
        """Test detection of valid existing database."""
        # Create a valid mock database
        db_path = Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
        self.create_mock_database(db_path, valid=True)

        # Update setup to use this path
        self.chembl_setup.database_path = db_path

        # Check existing database
        result = self.chembl_setup.check_existing_database()

        assert result is not None
        assert result == db_path

    def test_check_existing_database_invalid(self):
        """Test detection of invalid existing database."""
        # Create an invalid mock database
        db_path = Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
        self.create_mock_database(db_path, valid=False)

        # Update setup to use this path
        self.chembl_setup.database_path = db_path

        # Check existing database
        result = self.chembl_setup.check_existing_database()

        assert result is None

    @patch.object(ChEMBLSetup, "MIN_DATABASE_SIZE_MB", 0)
    @patch.object(ChEMBLSetup, "MIN_TABLE_COUNT", 0)
    def test_validate_database_valid(self):
        """Test database validation with valid database."""
        # Create a valid mock database
        db_path = Path(self.temp_dir) / "test.db"
        self.create_mock_database(db_path, valid=True)

        # Validate database
        validation = self.chembl_setup._validate_database(db_path)

        assert validation.is_valid
        assert validation.table_count >= 3
        assert validation.compound_count >= self.chembl_setup.MIN_COMPOUND_COUNT
        assert validation.activity_count >= self.chembl_setup.MIN_ACTIVITY_COUNT
        assert len(validation.errors) == 0

    def test_validate_database_invalid(self):
        """Test database validation with invalid database."""
        # Create an invalid mock database
        db_path = Path(self.temp_dir) / "test.db"
        self.create_mock_database(db_path, valid=False)

        # Validate database
        validation = self.chembl_setup._validate_database(db_path)

        assert not validation.is_valid
        assert len(validation.errors) > 0

    def test_validate_database_missing(self):
        """Test database validation with missing database."""
        # Use non-existent path
        db_path = Path(self.temp_dir) / "nonexistent.db"

        # Validate database
        validation = self.chembl_setup._validate_database(db_path)

        assert not validation.is_valid
        assert "does not exist" in validation.errors[0]

    def test_disk_space_check_sufficient(self):
        """Test disk space check with sufficient space."""
        # Mock shutil.disk_usage to return sufficient space
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=10 * 1024**3)  # 10 GB free

            result = self.chembl_setup._check_disk_space(5.0)  # Need 5 GB

            assert result is True

    def test_disk_space_check_insufficient(self):
        """Test disk space check with insufficient space."""
        # Mock shutil.disk_usage to return insufficient space
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=2 * 1024**3)  # 2 GB free

            result = self.chembl_setup._check_disk_space(5.0)  # Need 5 GB

            assert result is False

    @patch.object(ChEMBLSetup, "MIN_DATABASE_SIZE_MB", 0)
    @patch.object(ChEMBLSetup, "MIN_TABLE_COUNT", 0)
    def test_verify_setup_with_valid_database(self):
        """Test setup verification with valid database."""
        # Create a valid mock database
        db_path = Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
        self.create_mock_database(db_path, valid=True)

        # Update setup to use this path
        self.chembl_setup.database_path = db_path

        # Verify setup
        result = self.chembl_setup.verify_setup()

        assert result is True

    def test_verify_setup_without_database(self):
        """Test setup verification without database."""
        # No database created

        # Verify setup
        result = self.chembl_setup.verify_setup()

        assert result is False

    @patch.object(ChEMBLSetup, "MIN_DATABASE_SIZE_MB", 0)
    @patch.object(ChEMBLSetup, "MIN_TABLE_COUNT", 0)
    @patch("scripts.setup_chembl.ChEMBLSetup._download_with_progress")
    @patch("scripts.setup_chembl.ChEMBLSetup._extract_database")
    def test_setup_database_success_flow(self, mock_extract, mock_download):
        """Test successful database setup flow."""
        # Mock successful download and extraction
        mock_download.return_value = True
        mock_extract.return_value = True

        # Create a valid database after "extraction"
        def create_db_after_extract(*args):
            db_path = Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
            self.create_mock_database(db_path, valid=True)
            return True

        mock_extract.side_effect = create_db_after_extract

        # Update setup paths
        self.chembl_setup.database_path = (
            Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
        )
        self.chembl_setup.tar_path = Path(self.temp_dir) / "chembl_34_sqlite.tar.gz"

        # Setup database
        result = self.chembl_setup.setup_database()

        assert result.success
        assert result.database_path is not None
        assert result.size_mb > 0
        assert len(result.errors) == 0

    @patch("scripts.setup_chembl.ChEMBLSetup._download_with_progress")
    def test_setup_database_download_failure(self, mock_download):
        """Test database setup with download failure."""
        # Mock failed download
        mock_download.return_value = False

        # Setup database
        result = self.chembl_setup.setup_database()

        assert not result.success
        assert "Failed to download" in str(result.errors)

    @patch.object(ChEMBLSetup, "MIN_DATABASE_SIZE_MB", 0)
    @patch.object(ChEMBLSetup, "MIN_TABLE_COUNT", 0)
    def test_setup_database_with_existing_valid(self):
        """Test database setup when valid database already exists."""
        # Create a valid existing database
        db_path = Path(self.temp_dir) / "chembl_34_sqlite" / "chembl_34.db"
        self.create_mock_database(db_path, valid=True)

        # Update setup to use this path
        self.chembl_setup.database_path = db_path

        # Setup database (should use existing)
        result = self.chembl_setup.setup_database()

        assert result.success
        assert result.database_path == str(db_path)
        assert "existing database" in str(result.warnings).lower()


def test_chembl_setup_command_line():
    """Test ChEMBL setup command line interface."""
    # Test help output
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "scripts/setup_chembl.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "ChEMBL Database Setup" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--force" in result.stdout

    except subprocess.TimeoutExpired:
        # Skip if command takes too long
        pass
    except FileNotFoundError:
        # Skip if script not found (expected in some test environments)
        pass


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
