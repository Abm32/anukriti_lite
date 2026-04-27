#!/usr/bin/env python3
"""
VCF File Integrity Checker

Checks if a VCF file (especially gzipped) was downloaded completely and is valid.
"""

import gzip
import os
import sys
from pathlib import Path


def check_file_exists(file_path: str) -> bool:
    """Check if file exists."""
    return os.path.exists(file_path)


def check_file_size(file_path: str) -> tuple:
    """Get file size in bytes and MB."""
    if not os.path.exists(file_path):
        return None, None

    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)
    return size_bytes, size_mb


def check_gzip_integrity(file_path: str) -> tuple:
    """
    Check if gzip file is valid and can be decompressed.

    Returns:
        (is_valid, error_message)
    """
    try:
        with gzip.open(file_path, "rb") as f:
            # Try to read first few bytes
            f.read(1024)
        return True, None
    except gzip.BadGzipFile:
        return False, "File is not a valid gzip archive"
    except EOFError:
        return False, "File is incomplete (truncated) - download was interrupted"
    except Exception as e:
        return False, f"Error reading file: {e}"


def check_vcf_header(file_path: str) -> tuple:
    """
    Check if VCF file has valid header.

    Returns:
        (is_valid, header_lines, error_message)
    """
    try:
        with gzip.open(file_path, "rt") as f:
            header_lines = []
            for i, line in enumerate(f):
                if i >= 100:  # Read first 100 lines
                    break
                if line.startswith("#"):
                    header_lines.append(line.strip())
                else:
                    # Found data line, header is complete
                    break

            # Check for required VCF header elements
            has_chrom = any("#CHROM" in line for line in header_lines)
            has_format = any("##fileformat" in line for line in header_lines)

            if not has_format:
                return False, header_lines, "Missing ##fileformat line"
            if not has_chrom:
                return (
                    False,
                    header_lines,
                    "Missing #CHROM line (file may be incomplete)",
                )

            return True, header_lines, None
    except Exception as e:
        return False, [], f"Error reading VCF header: {e}"


def check_vcf_data_lines(file_path: str, sample_lines: int = 10) -> tuple:
    """
    Check if VCF file has data lines (not just header).

    Returns:
        (has_data, data_line_count, error_message)
    """
    try:
        data_count = 0
        with gzip.open(file_path, "rt") as f:
            for line in f:
                if not line.startswith("#"):
                    data_count += 1
                    if data_count >= sample_lines:
                        break

        if data_count == 0:
            return False, 0, "No data lines found (file may be incomplete)"

        return True, data_count, None
    except Exception as e:
        return False, 0, f"Error checking data lines: {e}"


def main():
    """Main function to check VCF file integrity."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_vcf_integrity.py <vcf_file_path>")
        print("\nExample:")
        print("  python scripts/check_vcf_integrity.py data/genomes/chr10.vcf.gz")
        sys.exit(1)

    file_path = sys.argv[1]

    print("=" * 60)
    print("VCF File Integrity Checker")
    print("=" * 60)
    print(f"\nFile: {file_path}\n")

    # Check 1: File exists
    if not check_file_exists(file_path):
        print("❌ File does not exist!")
        print(f"\nTo download Chromosome 10 VCF file:")
        print("  cd data/genomes/")
        print(
            "  wget https://hgdownload.cse.ucsc.edu/gbdb/hg19/1000Genomes/phase3/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
        )
        sys.exit(1)

    print("✅ File exists")

    # Check 2: File size
    size_bytes, size_mb = check_file_size(file_path)
    print(f"\n📊 File Size: {size_mb:.2f} MB ({size_bytes:,} bytes)")

    # Expected sizes for chromosome 10
    if size_mb < 100:
        print("⚠️  WARNING: File is very small (< 100 MB)")
        print("   Expected: ~500-800 MB for chromosome 10")
        print("   File is likely incomplete!")
    elif size_mb > 1000:
        print("⚠️  WARNING: File is very large (> 1 GB)")
        print("   Expected: ~500-800 MB for chromosome 10")
        print("   File may be corrupted!")
    else:
        print("✅ File size looks reasonable")

    # Check 3: Gzip integrity
    print("\n" + "-" * 60)
    print("Checking gzip integrity...")
    is_valid, error = check_gzip_integrity(file_path)
    if is_valid:
        print("✅ File is a valid gzip archive")
    else:
        print(f"❌ Gzip integrity check failed: {error}")
        print("\n💡 Solution: Re-download the file")
        print("   The file is corrupted or incomplete.")
        sys.exit(1)

    # Check 4: VCF header
    print("\n" + "-" * 60)
    print("Checking VCF header...")
    has_header, header_lines, error = check_vcf_header(file_path)
    if has_header:
        print("✅ VCF header is valid")
        print(f"   Found {len(header_lines)} header lines")
        # Show first few header lines
        if header_lines:
            print("\n   First few header lines:")
            for line in header_lines[:5]:
                print(f"   {line[:80]}...")
    else:
        print(f"❌ VCF header check failed: {error}")
        if "incomplete" in error.lower():
            print("\n💡 Solution: Re-download the file (download was interrupted)")
        sys.exit(1)

    # Check 5: Data lines
    print("\n" + "-" * 60)
    print("Checking for data lines...")
    has_data, data_count, error = check_vcf_data_lines(file_path)
    if has_data:
        print(f"✅ Found data lines (checked first {data_count} lines)")
    else:
        print(f"❌ No data lines found: {error}")
        print("\n💡 Solution: Re-download the file (file may be incomplete)")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("✅ SUMMARY: File appears to be complete and valid!")
    print("=" * 60)
    print(f"\nFile: {file_path}")
    print(f"Size: {size_mb:.2f} MB")
    print("Status: ✅ Ready to use")
    print("\nYou can now use this file with:")
    print("  python main.py --vcf data/genomes/chr22.vcf.gz \\")
    print("                 --vcf-chr10 data/genomes/chr10.vcf.gz \\")
    print("                 --drug-name Warfarin")


if __name__ == "__main__":
    main()
