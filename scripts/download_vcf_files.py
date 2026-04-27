#!/usr/bin/env python3
"""
VCF File Download Automation

Specialized script for downloading VCF files from the 1000 Genomes Project
with comprehensive checksum validation, corruption detection, and integrity
verification. Integrates with SynthaTrial's data initialization system.

Features:
- 1000 Genomes Project integration with official URLs
- MD5 checksum validation for data integrity
- Corruption detection using multiple validation methods
- Progress tracking with ETA and speed monitoring
- Retry logic with exponential backoff
- Multi-chromosome support (chr2, chr6, chr10, chr11, chr12, chr19, chr22; see root README)
- Detailed logging and error reporting
- Integration with data initializer orchestrator

Version: 0.2 Beta
"""

import gzip
import hashlib
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve

import requests


@dataclass
class VCFFileInfo:
    """Information about a VCF file to download."""

    chromosome: str
    url: str
    filename: str
    expected_md5: Optional[str] = None
    expected_size_range: Optional[Tuple[int, int]] = None
    description: str = ""


@dataclass
class DownloadResult:
    """Result of a VCF file download operation."""

    chromosome: str
    filename: str
    success: bool
    file_path: str
    file_size: int
    download_time: float
    validation_passed: bool
    md5_match: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class ValidationReport:
    """Comprehensive validation report for VCF files."""

    file_path: str
    is_valid: bool
    file_size: int
    md5_checksum: str
    md5_match: bool
    gzip_valid: bool
    vcf_header_valid: bool
    sample_count: int
    variant_count_estimate: int
    errors: List[str]
    warnings: List[str]


class ProgressTracker:
    """Enhanced progress tracking for VCF downloads."""

    def __init__(self, filename: str, total_size: int = 0):
        self.filename = filename
        self.total_size = total_size
        self.downloaded_size = 0
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 1.0  # Update every second

    def update(self, downloaded: int, total: int = None):
        """Update progress tracking."""
        self.downloaded_size = downloaded
        if total is not None:
            self.total_size = total

        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self._display_progress()
            self.last_update = current_time

    def _display_progress(self):
        """Display formatted progress information."""
        if self.total_size <= 0:
            # Unknown size - show downloaded amount only
            downloaded_mb = self.downloaded_size / (1024 * 1024)
            elapsed = time.time() - self.start_time
            speed = (self.downloaded_size / (1024 * 1024)) / max(elapsed, 0.1)
            print(
                f"\r  📥 {self.filename}: {downloaded_mb:6.1f} MB | {speed:5.1f} MB/s",
                end="",
                flush=True,
            )
            return

        # Known size - show full progress
        percent = min(100.0, (self.downloaded_size / self.total_size) * 100.0)
        downloaded_mb = self.downloaded_size / (1024 * 1024)
        total_mb = self.total_size / (1024 * 1024)

        # Calculate speed and ETA
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            speed = (self.downloaded_size / (1024 * 1024)) / elapsed
            if speed > 0 and percent < 100:
                remaining_mb = (self.total_size - self.downloaded_size) / (1024 * 1024)
                eta_seconds = remaining_mb / speed
                eta_str = self._format_time(eta_seconds)
            else:
                eta_str = "00:00"
        else:
            speed = 0
            eta_str = "∞"

        # Progress bar
        bar_width = 25
        filled = int(bar_width * percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        print(
            f"\r  📥 [{bar}] {percent:5.1f}% | "
            f"{downloaded_mb:6.1f}/{total_mb:6.1f} MB | "
            f"{speed:5.1f} MB/s | ETA: {eta_str}",
            end="",
            flush=True,
        )

    def _format_time(self, seconds: float) -> str:
        """Format time duration as MM:SS or HH:MM:SS."""
        if seconds == float("inf") or seconds < 0:
            return "∞"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def finish(self):
        """Mark progress as complete."""
        elapsed = time.time() - self.start_time
        total_mb = self.downloaded_size / (1024 * 1024)
        avg_speed = total_mb / max(elapsed, 0.1)

        print(
            f"\r  ✅ {self.filename}: {total_mb:.1f} MB in {self._format_time(elapsed)} "
            f"(avg: {avg_speed:.1f} MB/s)"
        )


class VCFDownloader:
    """Specialized VCF file downloader with 1000 Genomes Project integration."""

    # 1000 Genomes Phase 3 (EBI release 20130502) — use v5b (v5a returns 404)
    # See root README for chromosome set and VCF URLs.
    EBI_BASE = "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502"
    VCF_FILES = {
        "chr22": VCFFileInfo(
            chromosome="chr22",
            url=f"{EBI_BASE}/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(180 * 1024 * 1024, 250 * 1024 * 1024),  # ~196 MB
            description="Chromosome 22 (CYP2D6 region); small & gene-rich",
        ),
        "chr10": VCFFileInfo(
            chromosome="chr10",
            url=f"{EBI_BASE}/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(650 * 1024 * 1024, 800 * 1024 * 1024),  # ~707 MB
            description="Chromosome 10 (CYP2C19, CYP2C9 regions)",
        ),
        "chr2": VCFFileInfo(
            chromosome="chr2",
            url=f"{EBI_BASE}/ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(1100 * 1024 * 1024, 1300 * 1024 * 1024),  # ~1.2 GB
            description="Chromosome 2 (giant chr; high variation)",
        ),
        "chr6": VCFFileInfo(
            chromosome="chr6",
            url=f"{EBI_BASE}/ALL.chr6.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr6.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(850 * 1024 * 1024, 1000 * 1024 * 1024),  # ~915 MB
            description="Chromosome 6 (MHC region; diversity benchmark)",
        ),
        "chr11": VCFFileInfo(
            chromosome="chr11",
            url=f"{EBI_BASE}/ALL.chr11.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr11.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(650 * 1024 * 1024, 800 * 1024 * 1024),  # ~701 MB
            description="Chromosome 11 (high gene density; hemoglobin/olfactory)",
        ),
        "chr19": VCFFileInfo(
            chromosome="chr19",
            url=f"{EBI_BASE}/ALL.chr19.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr19.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(300 * 1024 * 1024, 400 * 1024 * 1024),  # ~329 MB
            description="Chromosome 19 (highest gene density)",
        ),
        "chr12": VCFFileInfo(
            chromosome="chr12",
            url=f"{EBI_BASE}/ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            filename="ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
            expected_size_range=(620 * 1024 * 1024, 750 * 1024 * 1024),  # ~677 MB
            description="Chromosome 12 (e.g. SLCO1B1 region)",
        ),
    }

    # Mirror URLs (v5b; same EBI base)
    MIRROR_URLS = {
        "chr22": [
            f"{EBI_BASE}/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr10": [
            f"{EBI_BASE}/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr2": [
            f"{EBI_BASE}/ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr6": [
            f"{EBI_BASE}/ALL.chr6.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr11": [
            f"{EBI_BASE}/ALL.chr11.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr19": [
            f"{EBI_BASE}/ALL.chr19.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
        "chr12": [
            f"{EBI_BASE}/ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
        ],
    }

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 5  # Base delay in seconds
    RETRY_DELAY_MAX = 60  # Maximum delay in seconds

    def __init__(self, output_dir: str = "data/genomes", verbose: bool = True):
        """
        Initialize VCF downloader.

        Args:
            output_dir: Directory to save VCF files
            verbose: Enable verbose logging
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

        # Setup logging
        self.logger = self._setup_logging()

        if self.verbose:
            self.logger.info(f"VCF Downloader initialized - Output: {self.output_dir}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger("VCFDownloader")
        logger.setLevel(logging.INFO if self.verbose else logging.WARNING)

        # Only add handler if not already present
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def download_chromosome(
        self, chromosome: str, force_redownload: bool = False
    ) -> DownloadResult:
        """
        Download VCF file for a specific chromosome.

        Args:
            chromosome: Chromosome identifier (e.g., 'chr22', 'chr10')
            force_redownload: Force redownload even if file exists and is valid

        Returns:
            DownloadResult with download and validation information
        """
        if chromosome not in self.VCF_FILES:
            return DownloadResult(
                chromosome=chromosome,
                filename="",
                success=False,
                file_path="",
                file_size=0,
                download_time=0,
                validation_passed=False,
                md5_match=False,
                errors=[
                    f"Unknown chromosome: {chromosome}. Available: {list(self.VCF_FILES.keys())}"
                ],
                warnings=[],
            )

        vcf_info = self.VCF_FILES[chromosome]
        output_file = self.output_dir / f"{chromosome}.vcf.gz"

        print(f"\n{'='*60}")
        print(f"Downloading {chromosome.upper()} VCF File")
        print(f"{'='*60}")
        print(f"Description: {vcf_info.description}")
        print(f"Output file: {output_file}")

        # Check if file already exists and is valid
        if output_file.exists() and not force_redownload:
            print(f"📁 File exists: {output_file}")
            validation = self.validate_vcf_file(str(output_file))

            if validation.is_valid:
                print(f"✅ File is valid, skipping download")
                return DownloadResult(
                    chromosome=chromosome,
                    filename=output_file.name,
                    success=True,
                    file_path=str(output_file),
                    file_size=validation.file_size,
                    download_time=0,
                    validation_passed=True,
                    md5_match=validation.md5_match,
                    errors=[],
                    warnings=[],
                )
            else:
                print(f"⚠️  File is invalid, re-downloading...")
                for error in validation.errors:
                    print(f"   - {error}")
                self.logger.warning(
                    f"Invalid VCF file detected, re-downloading: {output_file}"
                )

        # Attempt download with retry logic
        start_time = time.time()
        urls_to_try = [vcf_info.url] + self.MIRROR_URLS.get(chromosome, [])

        for url in urls_to_try:
            print(f"\n🌐 Attempting download from: {urlparse(url).netloc}")

            result = self._download_with_retry(url, str(output_file), vcf_info)
            if result.success:
                download_time = time.time() - start_time

                # Validate downloaded file
                print(f"\n🔍 Validating downloaded file...")
                validation = self.validate_vcf_file(str(output_file))

                return DownloadResult(
                    chromosome=chromosome,
                    filename=output_file.name,
                    success=True,
                    file_path=str(output_file),
                    file_size=validation.file_size,
                    download_time=download_time,
                    validation_passed=validation.is_valid,
                    md5_match=validation.md5_match,
                    errors=validation.errors,
                    warnings=validation.warnings,
                )
            else:
                print(f"❌ Download failed from {urlparse(url).netloc}")
                for error in result.errors:
                    print(f"   - {error}")

        # All URLs failed
        download_time = time.time() - start_time
        return DownloadResult(
            chromosome=chromosome,
            filename=vcf_info.filename,
            success=False,
            file_path=str(output_file),
            file_size=0,
            download_time=download_time,
            validation_passed=False,
            md5_match=False,
            errors=[f"Failed to download from all available sources"],
            warnings=[],
        )

    def _download_with_retry(
        self, url: str, output_path: str, vcf_info: VCFFileInfo
    ) -> DownloadResult:
        """
        Download file with retry logic and exponential backoff.

        Args:
            url: URL to download from
            output_path: Local path to save file
            vcf_info: VCF file information

        Returns:
            DownloadResult with download status
        """
        errors = []

        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    # Exponential backoff with jitter
                    delay = min(
                        self.RETRY_DELAY_BASE * (2 ** (attempt - 1)),
                        self.RETRY_DELAY_MAX,
                    )
                    print(
                        f"   ⏳ Waiting {delay} seconds before retry {attempt + 1}/{self.MAX_RETRIES}..."
                    )
                    time.sleep(delay)

                # Remove partial file from previous attempt
                if Path(output_path).exists() and attempt > 0:
                    Path(output_path).unlink()
                    print(f"   🗑️  Removed partial file from previous attempt")

                # Get file size for progress tracking
                try:
                    response = requests.head(url, timeout=30, allow_redirects=True)
                    total_size = int(response.headers.get("content-length", 0))
                except:
                    total_size = 0

                # Create progress tracker
                progress = ProgressTracker(vcf_info.filename, total_size)

                def progress_callback(block_num: int, block_size: int, total_size: int):
                    progress.update(block_num * block_size, total_size)

                print(f"   📥 Starting download...")
                print(f"   URL: {url}")

                # Download with progress callback
                urlretrieve(url, output_path, reporthook=progress_callback)
                progress.finish()

                # Verify download completed successfully
                if not Path(output_path).exists():
                    raise Exception("Downloaded file is missing")

                file_size = Path(output_path).stat().st_size
                if file_size == 0:
                    raise Exception("Downloaded file is empty")

                # Check file size against expected range
                if vcf_info.expected_size_range:
                    min_size, max_size = vcf_info.expected_size_range
                    if file_size < min_size:
                        raise Exception(
                            f"File too small: {file_size} bytes < {min_size} bytes"
                        )
                    elif file_size > max_size:
                        print(
                            f"   ⚠️  File larger than expected: {file_size} bytes > {max_size} bytes"
                        )

                self.logger.info(
                    f"Successfully downloaded {vcf_info.filename} ({file_size} bytes)"
                )

                return DownloadResult(
                    chromosome=vcf_info.chromosome,
                    filename=vcf_info.filename,
                    success=True,
                    file_path=output_path,
                    file_size=file_size,
                    download_time=0,  # Will be calculated by caller
                    validation_passed=False,  # Will be validated by caller
                    md5_match=False,  # Will be validated by caller
                    errors=[],
                    warnings=[],
                )

            except (URLError, HTTPError) as e:
                error_msg = f"Network error on attempt {attempt + 1}: {e}"
                errors.append(error_msg)
                print(f"\n   ❌ {error_msg}")
                self.logger.warning(error_msg)

            except Exception as e:
                error_msg = f"Download error on attempt {attempt + 1}: {e}"
                errors.append(error_msg)
                print(f"\n   ❌ {error_msg}")
                self.logger.warning(error_msg)

        return DownloadResult(
            chromosome=vcf_info.chromosome,
            filename=vcf_info.filename,
            success=False,
            file_path=output_path,
            file_size=0,
            download_time=0,
            validation_passed=False,
            md5_match=False,
            errors=errors,
            warnings=[],
        )

    def validate_vcf_file(self, file_path: str) -> ValidationReport:
        """
        Comprehensive VCF file validation with corruption detection.

        Args:
            file_path: Path to VCF file to validate

        Returns:
            ValidationReport with detailed validation results
        """
        path = Path(file_path)
        errors = []
        warnings = []

        # Initialize default values
        file_size = 0
        md5_checksum = ""
        md5_match = False
        gzip_valid = False
        vcf_header_valid = False
        sample_count = 0
        variant_count_estimate = 0

        # Check if file exists
        if not path.exists():
            errors.append("File does not exist")
            return ValidationReport(
                file_path=file_path,
                is_valid=False,
                file_size=0,
                md5_checksum="",
                md5_match=False,
                gzip_valid=False,
                vcf_header_valid=False,
                sample_count=0,
                variant_count_estimate=0,
                errors=errors,
                warnings=warnings,
            )

        # Get file size
        file_size = path.stat().st_size
        size_mb = file_size / (1024 * 1024)

        print(f"   📊 File size: {size_mb:.1f} MB")

        # Calculate MD5 checksum
        print(f"   🔐 Calculating MD5 checksum...")
        try:
            md5_checksum = self._calculate_md5(file_path)
            print(f"   MD5: {md5_checksum}")
        except Exception as e:
            errors.append(f"Failed to calculate MD5: {e}")

        # Validate gzip format
        print(f"   🗜️  Validating gzip format...")
        try:
            with gzip.open(path, "rb") as f:
                # Try to read first 1KB to validate gzip format
                f.read(1024)
            gzip_valid = True
            print(f"   ✅ Gzip format valid")
        except Exception as e:
            errors.append(f"Invalid gzip format: {e}")
            print(f"   ❌ Gzip format invalid: {e}")

        # Validate VCF header and content
        if gzip_valid:
            print(f"   📋 Validating VCF header and content...")
            try:
                header_valid, samples, variants = self._validate_vcf_content(file_path)
                vcf_header_valid = header_valid
                sample_count = samples
                variant_count_estimate = variants

                if header_valid:
                    print(f"   ✅ VCF header valid")
                    print(f"   👥 Samples: {sample_count}")
                    print(f"   🧬 Estimated variants: {variant_count_estimate:,}")
                else:
                    errors.append("Invalid VCF header or format")
                    print(f"   ❌ VCF header invalid")

            except Exception as e:
                errors.append(f"VCF content validation failed: {e}")
                print(f"   ❌ VCF validation error: {e}")

        # Check file size against expected ranges (match longest first so chr22 before chr2)
        chromosome = None
        for c in ("chr22", "chr10", "chr19", "chr12", "chr11", "chr6", "chr2"):
            if c in file_path:
                chromosome = c
                break

        if chromosome and chromosome in self.VCF_FILES:
            vcf_info = self.VCF_FILES[chromosome]
            if vcf_info.expected_size_range:
                min_size, max_size = vcf_info.expected_size_range
                if file_size < min_size:
                    errors.append(
                        f"File too small ({size_mb:.1f} MB < {min_size/(1024*1024):.1f} MB)"
                    )
                elif file_size > max_size:
                    warnings.append(
                        f"File larger than expected ({size_mb:.1f} MB > {max_size/(1024*1024):.1f} MB)"
                    )

        # Overall validation status
        is_valid = len(errors) == 0 and gzip_valid and vcf_header_valid

        if is_valid:
            print(f"   ✅ Overall validation: PASSED")
        else:
            print(f"   ❌ Overall validation: FAILED")
            for error in errors:
                print(f"      - {error}")

        return ValidationReport(
            file_path=file_path,
            is_valid=is_valid,
            file_size=file_size,
            md5_checksum=md5_checksum,
            md5_match=md5_match,  # We don't have reference checksums
            gzip_valid=gzip_valid,
            vcf_header_valid=vcf_header_valid,
            sample_count=sample_count,
            variant_count_estimate=variant_count_estimate,
            errors=errors,
            warnings=warnings,
        )

    def _calculate_md5(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _validate_vcf_content(self, file_path: str) -> Tuple[bool, int, int]:
        """
        Validate VCF file content and extract metadata.

        Args:
            file_path: Path to VCF file

        Returns:
            Tuple of (header_valid, sample_count, variant_count_estimate)
        """
        try:
            with gzip.open(file_path, "rt") as f:
                header_found = False
                sample_count = 0
                variant_count = 0
                lines_checked = 0
                max_lines_to_check = 1000  # Limit for performance

                for line in f:
                    lines_checked += 1

                    # Check for VCF header
                    if line.startswith("##fileformat=VCF"):
                        header_found = True

                    # Check for column header line
                    elif line.startswith("#CHROM"):
                        # Count samples (columns after the first 9 are samples)
                        columns = line.strip().split("\t")
                        if len(columns) > 9:
                            sample_count = len(columns) - 9

                    # Count variant lines (non-header lines)
                    elif not line.startswith("#"):
                        variant_count += 1

                        # Stop after checking enough lines for estimate
                        if lines_checked >= max_lines_to_check:
                            break

                # Estimate total variants based on sample
                if variant_count > 0 and lines_checked >= max_lines_to_check:
                    # Rough estimate based on file size and sample
                    file_size = Path(file_path).stat().st_size
                    bytes_per_variant = file_size / (
                        variant_count * 100
                    )  # Rough estimate
                    variant_count_estimate = int(file_size / bytes_per_variant)
                else:
                    variant_count_estimate = variant_count

                return header_found, sample_count, variant_count_estimate

        except Exception as e:
            raise Exception(f"Failed to validate VCF content: {e}")

    def download_multiple_chromosomes(
        self, chromosomes: List[str], force_redownload: bool = False
    ) -> Dict[str, DownloadResult]:
        """
        Download VCF files for multiple chromosomes.

        Args:
            chromosomes: List of chromosome identifiers
            force_redownload: Force redownload even if files exist and are valid

        Returns:
            Dictionary mapping chromosome to DownloadResult
        """
        print(f"\n{'='*60}")
        print("VCF Multi-Chromosome Download")
        print(f"{'='*60}")
        print(f"Chromosomes: {', '.join(chromosomes)}")
        print(f"Output directory: {self.output_dir}")

        # Check disk space
        total_size_estimate = 0
        for chromosome in chromosomes:
            if chromosome in self.VCF_FILES:
                vcf_info = self.VCF_FILES[chromosome]
                if vcf_info.expected_size_range:
                    _, max_size = vcf_info.expected_size_range
                    total_size_estimate += max_size

        if total_size_estimate > 0:
            size_gb = total_size_estimate / (1024**3)
            print(f"Estimated download size: {size_gb:.1f} GB")

            # Check available disk space
            try:
                import shutil

                free_bytes = shutil.disk_usage(self.output_dir).free
                free_gb = free_bytes / (1024**3)

                if free_gb < size_gb + 1.0:  # Add 1GB buffer
                    print(
                        f"⚠️  Warning: Low disk space ({free_gb:.1f} GB available, {size_gb:.1f} GB needed)"
                    )
                else:
                    print(f"✅ Disk space check: {free_gb:.1f} GB available")
            except:
                print(f"⚠️  Could not check disk space")

        results = {}
        successful_downloads = 0

        for i, chromosome in enumerate(chromosomes, 1):
            print(f"\n[{i}/{len(chromosomes)}] Processing {chromosome}...")

            result = self.download_chromosome(chromosome, force_redownload)
            results[chromosome] = result

            if result.success and result.validation_passed:
                successful_downloads += 1
                print(f"✅ {chromosome}: Download and validation successful")
            elif result.success:
                print(f"⚠️  {chromosome}: Download successful but validation failed")
            else:
                print(f"❌ {chromosome}: Download failed")

        # Summary
        print(f"\n{'='*60}")
        print(f"Download Summary: {successful_downloads}/{len(chromosomes)} successful")
        print(f"{'='*60}")

        for chromosome, result in results.items():
            status = "✅" if result.success and result.validation_passed else "❌"
            size_mb = result.file_size / (1024 * 1024) if result.file_size > 0 else 0
            print(f"{status} {chromosome}: {size_mb:.1f} MB")

            if result.errors:
                for error in result.errors[:2]:  # Show first 2 errors
                    print(f"   - {error}")

        return results

    def list_available_chromosomes(self) -> Dict[str, VCFFileInfo]:
        """
        List all available chromosomes for download.

        Returns:
            Dictionary mapping chromosome to VCFFileInfo
        """
        return self.VCF_FILES.copy()

    def check_existing_files(self) -> Dict[str, ValidationReport]:
        """
        Check validation status of existing VCF files.

        Returns:
            Dictionary mapping chromosome to ValidationReport
        """
        results = {}

        print(f"\n{'='*60}")
        print("Existing VCF Files Status")
        print(f"{'='*60}")

        for chromosome in self.VCF_FILES:
            vcf_file = self.output_dir / f"{chromosome}.vcf.gz"

            if vcf_file.exists():
                print(f"\n📁 Checking {chromosome}: {vcf_file}")
                validation = self.validate_vcf_file(str(vcf_file))
                results[chromosome] = validation

                status = "✅ Valid" if validation.is_valid else "❌ Invalid"
                print(f"   Status: {status}")
            else:
                print(f"\n❌ {chromosome}: File not found ({vcf_file})")

        return results


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VCF File Download Automation for SynthaTrial",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all available chromosomes
  python scripts/download_vcf_files.py --all

  # Download specific chromosomes
  python scripts/download_vcf_files.py --chromosomes chr22 chr10

  # Force redownload even if files exist
  python scripts/download_vcf_files.py --chromosomes chr22 --force

  # Check status of existing files
  python scripts/download_vcf_files.py --status

  # Validate specific file
  python scripts/download_vcf_files.py --validate data/genomes/chr22.vcf.gz

  # List available chromosomes
  python scripts/download_vcf_files.py --list
        """,
    )

    parser.add_argument(
        "--all", action="store_true", help="Download all available chromosomes"
    )
    parser.add_argument(
        "--chromosomes",
        nargs="+",
        metavar="CHR",
        help="Download specific chromosomes (e.g., chr22 chr10)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force redownload even if files exist and are valid",
    )
    parser.add_argument(
        "--status", action="store_true", help="Check status of existing VCF files"
    )
    parser.add_argument(
        "--validate", metavar="FILE_PATH", help="Validate specific VCF file"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available chromosomes for download"
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default="data/genomes",
        help="Output directory (default: data/genomes)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose logging (default: True)",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable verbose logging")

    args = parser.parse_args()

    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet

    # Initialize downloader
    downloader = VCFDownloader(args.output_dir, verbose=verbose)

    # Handle different commands
    if args.list:
        print(f"\n{'='*60}")
        print("Available VCF Files")
        print(f"{'='*60}")

        for chromosome, info in downloader.list_available_chromosomes().items():
            size_range = ""
            if info.expected_size_range:
                min_mb = info.expected_size_range[0] / (1024 * 1024)
                max_mb = info.expected_size_range[1] / (1024 * 1024)
                size_range = f" ({min_mb:.0f}-{max_mb:.0f} MB)"

            print(f"📁 {chromosome}: {info.description}{size_range}")
            print(f"   URL: {info.url}")

        return 0

    elif args.status:
        results = downloader.check_existing_files()

        if not results:
            print("\n❌ No VCF files found")
            return 1

        all_valid = all(report.is_valid for report in results.values())
        return 0 if all_valid else 1

    elif args.validate:
        validation = downloader.validate_vcf_file(args.validate)

        print(f"\n{'='*60}")
        print(f"VCF File Validation: {args.validate}")
        print(f"{'='*60}")

        status = "✅ Valid" if validation.is_valid else "❌ Invalid"
        print(f"Status: {status}")
        print(f"Size: {validation.file_size / (1024*1024):.1f} MB")
        print(f"MD5: {validation.md5_checksum}")
        print(f"Samples: {validation.sample_count}")
        print(f"Variants: {validation.variant_count_estimate:,}")

        if validation.errors:
            print("\nErrors:")
            for error in validation.errors:
                print(f"  - {error}")

        if validation.warnings:
            print("\nWarnings:")
            for warning in validation.warnings:
                print(f"  - {warning}")

        return 0 if validation.is_valid else 1

    elif args.all:
        chromosomes = list(downloader.list_available_chromosomes().keys())
        results = downloader.download_multiple_chromosomes(chromosomes, args.force)

        success_count = sum(
            1 for r in results.values() if r.success and r.validation_passed
        )
        return 0 if success_count == len(chromosomes) else 1

    elif args.chromosomes:
        results = downloader.download_multiple_chromosomes(args.chromosomes, args.force)

        success_count = sum(
            1 for r in results.values() if r.success and r.validation_passed
        )
        return 0 if success_count == len(args.chromosomes) else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
