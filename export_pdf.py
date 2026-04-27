#!/usr/bin/env python3
"""
Export Patent Drawings HTML to PDF

This script uses Chrome/Chromium in headless mode to generate a high-quality PDF
suitable for patent submission.
"""

import os
import subprocess
import sys
from pathlib import Path


def find_chrome():
    """Find Chrome/Chromium executable."""
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows
    ]

    for path in chrome_paths:
        if os.path.exists(path):
            return path

    return None


def export_html_to_pdf(html_path, output_pdf, chrome_path=None):
    """
    Export HTML file to PDF using Chrome headless.

    Args:
        html_path: Path to HTML file
        output_pdf: Path to output PDF file
        chrome_path: Path to Chrome executable (auto-detected if None)
    """
    if chrome_path is None:
        chrome_path = find_chrome()

    if chrome_path is None:
        print("❌ Error: Chrome/Chromium not found.")
        print("\nPlease install Chrome or Chromium, or use manual export:")
        print("  1. Open drawings.html in Chrome")
        print("  2. Press Ctrl+P (or Cmd+P on Mac)")
        print("  3. Select 'Save as PDF'")
        print("  4. Set margins to 'None' and enable 'Background graphics'")
        return False

    html_path = Path(html_path).resolve()
    output_pdf = Path(output_pdf).resolve()

    if not html_path.exists():
        print(f"❌ Error: HTML file not found: {html_path}")
        return False

    print(f"📄 Converting {html_path.name} to PDF...")
    print(f"   Output: {output_pdf}")

    # Chrome headless command for high-quality PDF
    # --print-to-pdf: Generate PDF
    # --print-to-pdf-no-header: Remove header/footer
    # --no-margins: Remove margins (important for patent drawings)
    # --disable-gpu: Disable GPU (sometimes needed in headless)
    # --run-all-compositor-stages-before-draw: Wait for all rendering
    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--print-to-pdf=" + str(output_pdf),
        "--print-to-pdf-no-header",
        "--no-margins",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",  # Wait longer for Mermaid to render
        "file://" + str(html_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # Increased timeout for Mermaid rendering
        )

        if result.returncode == 0 and output_pdf.exists():
            file_size = output_pdf.stat().st_size / 1024  # KB
            print(f"✅ Success! PDF created: {output_pdf}")
            print(f"   File size: {file_size:.1f} KB")
            return True
        else:
            print(f"❌ Error: Chrome returned exit code {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Error: Conversion timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    html_file = script_dir / "drawings.html"
    pdf_file = script_dir / "patent_drawing_final.pdf"

    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])

    if len(sys.argv) > 2:
        pdf_file = Path(sys.argv[2])

    success = export_html_to_pdf(html_file, pdf_file)

    if success:
        print(f"\n📋 Patent drawings PDF ready: {pdf_file}")
        print("\n💡 Tips for patent submission:")
        print("   - Each figure should be on a separate page (already configured)")
        print("   - Check that all diagrams render correctly")
        print("   - Verify text is readable and not cut off")
    else:
        print("\n💡 Alternative: Manual export via browser")
        print("   1. Open drawings.html in Chrome/Chromium")
        print("   2. Press Ctrl+P (or Cmd+P)")
        print("   3. Destination: 'Save as PDF'")
        print("   4. Settings:")
        print("      - Margins: None")
        print("      - Background graphics: ON")
        print("      - Scale: 100%")
        print("   5. Click 'Save'")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
