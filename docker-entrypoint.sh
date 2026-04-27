#!/bin/bash
set -e

# SynthaTrial Docker Entrypoint Script
# Handles initialization, data validation, and different run modes
#
# Enhanced with comprehensive data integrity validation:
# - Validates VCF file integrity and format
# - Validates ChEMBL database integrity
# - Provides detailed validation reporting
# - Handles missing and corrupted files gracefully
# - Supports automated data initialization

echo "🧬 Starting SynthaTrial - In Silico Pharmacogenomics Platform"
echo "============================================================"

# Function to show usage help
show_help() {
    echo "SynthaTrial Docker Container - Available Commands:"
    echo ""
    echo "Web Interface:"
    echo "  streamlit, web, (default)  Start Streamlit web interface"
    echo ""
    echo "Command Line:"
    echo "  cli [args]                 Start CLI mode with optional arguments"
    echo ""
    echo "Development Mode (Enhanced Image Only):"
    echo "  dev                        Start enhanced development environment"
    echo "  hot-reload                 Start with hot reloading enabled"
    echo "  jupyter                    Start Jupyter Lab server"
    echo "  quality-check              Run code quality checks"
    echo "  validate-env               Validate development environment"
    echo "  profile [type] [target]    Run performance profiling"
    echo ""
    echo "Testing & Validation:"
    echo "  test                       Run comprehensive test suite"
    echo "  test-dev                   Run tests with development reporting"
    echo "  validate                   Run comprehensive data validation"
    echo "  validate-legacy, check     Run legacy data file checks"
    echo "  benchmark                  Run performance benchmarks"
    echo ""
    echo "Setup & Maintenance:"
    echo "  setup                      Run basic setup tasks"
    echo "  setup --data               Run setup with data initialization"
    echo "  setup --all                Run complete setup with all data"
    echo "  setup-dev                  Setup development environment"
    echo ""
    echo "Utilities:"
    echo "  bash, shell                Start interactive shell"
    echo "  help                       Show this help message"
    echo ""
    echo "Data Management:"
    echo "  To download missing data files:"
    echo "    docker exec <container> python scripts/data_initializer.py --all"
    echo ""
    echo "  To check data status:"
    echo "    docker exec <container> python scripts/data_initializer.py --status"
    echo ""
}

# Activate conda environment (if available)
if [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source /opt/conda/etc/profile.d/conda.sh
    conda activate synthatrial
else
    echo "⚠️  Conda environment not available (running outside Docker container)"
fi

# Check if required directories exist (create if in Docker container)
if [ -w "/app" ] 2>/dev/null || [ "$PWD" = "/app" ]; then
    mkdir -p /app/data/genomes /app/data/chembl /app/logs
else
    # Running outside Docker container, use relative paths
    mkdir -p data/genomes data/chembl logs
fi

# Function to check API keys
check_api_keys() {
    echo "🔑 Checking API keys..."

    if [ -z "$GOOGLE_API_KEY" ]; then
        echo "⚠️  GOOGLE_API_KEY not set. LLM simulation will fail."
        echo "   Set GOOGLE_API_KEY environment variable or add to .env file"
    else
        echo "✅ GOOGLE_API_KEY is set"
    fi

    if [ -z "$PINECONE_API_KEY" ]; then
        echo "⚠️  PINECONE_API_KEY not set. Using mock data for vector search."
        echo "   Set PINECONE_API_KEY environment variable for real drug data"
    else
        echo "✅ PINECONE_API_KEY is set"
    fi
}

# Function to perform comprehensive data validation
validate_data_integrity() {
    echo "🔍 Performing comprehensive data integrity checks..."

    # Determine base path (Docker container vs local)
    if [ -w "/app" ] 2>/dev/null || [ "$PWD" = "/app" ]; then
        BASE_PATH="/app"
    else
        BASE_PATH="."
    fi

    # Use the data initializer for comprehensive validation
    if python -c "
import sys
sys.path.append('$BASE_PATH')
from scripts.data_initializer import DataInitializer

# Initialize validator with appropriate base path
initializer = DataInitializer('$BASE_PATH', verbose=False)

# Check data completeness
status = initializer.check_data_completeness()

# Print detailed validation report
print('📊 Data Validation Report')
print('=' * 50)
print(f'Overall Status: {status.valid_files}/{status.total_files} files ready')
print()

# VCF Files validation
print('VCF Files:')
for chromosome, exists in status.vcf_files.items():
    if exists:
        # Validate file integrity
        vcf_path = f'$BASE_PATH/data/genomes/{chromosome}.vcf.gz'
        validation = initializer.validate_file_integrity(vcf_path)
        if validation.is_valid:
            size_mb = validation.size_bytes / (1024 * 1024)
            print(f'  ✅ {chromosome}.vcf.gz ({size_mb:.1f} MB) - Valid')
        else:
            print(f'  ❌ {chromosome}.vcf.gz - Corrupted')
            for error in validation.errors:
                print(f'     Error: {error}')
    else:
        print(f'  ❌ {chromosome}.vcf.gz - Missing')

print()

# ChEMBL Database validation
print('ChEMBL Database:')
if status.chembl_database:
    # Find and validate ChEMBL database
    chembl_paths = [
        f'$BASE_PATH/data/chembl/chembl_34_sqlite/chembl_34.db',
        f'$BASE_PATH/data/chembl/chembl_34.db'
    ]

    for db_path in chembl_paths:
        import os
        if os.path.exists(db_path):
            validation = initializer.validate_file_integrity(db_path)
            if validation.is_valid:
                size_mb = validation.size_bytes / (1024 * 1024)
                print(f'  ✅ ChEMBL database ({size_mb:.1f} MB) - Valid')
                print(f'     Path: {db_path}')
            else:
                print(f'  ❌ ChEMBL database - Corrupted')
                for error in validation.errors:
                    print(f'     Error: {error}')
            break
else:
    print('  ❌ ChEMBL database - Missing')

print()

# Summary and recommendations
if status.missing_files:
    print(f'Missing Files ({len(status.missing_files)}):')
    for file_path in status.missing_files:
        print(f'  - {file_path}')
    print()
    print('💡 To download missing files:')
    if '$BASE_PATH' == '/app':
        print('   docker exec <container> python scripts/data_initializer.py --all')
    else:
        print('   python scripts/data_initializer.py --all')
    print('   # or mount existing files as volumes')
    print()

if status.corrupted_files:
    print(f'Corrupted Files ({len(status.corrupted_files)}):')
    for file_path in status.corrupted_files:
        print(f'  - {file_path}')
    print()
    print('💡 To fix corrupted files:')
    if '$BASE_PATH' == '/app':
        print('   docker exec <container> python scripts/data_initializer.py --all')
    else:
        print('   python scripts/data_initializer.py --all')
    print()

# Set exit code based on validation results
if status.valid_files == status.total_files:
    print('✅ All data files are valid and ready!')
    sys.exit(0)
elif status.valid_files > 0:
    print('⚠️  Some data files are missing or corrupted')
    print('   SynthaTrial will run with reduced functionality')
    sys.exit(0)  # Continue with warnings
else:
    print('❌ No valid data files found')
    print('   SynthaTrial may not function properly')
    sys.exit(1)  # Exit with error for critical failures
"; then
        echo "✅ Data validation completed successfully"
        return 0
    else
        validation_exit_code=$?
        if [ $validation_exit_code -eq 1 ]; then
            echo "❌ Critical data validation failures detected"
            echo "   Container startup will continue but functionality may be limited"
            if [ "$BASE_PATH" = "/app" ]; then
                echo "   Run 'python scripts/data_initializer.py --all' to download required files"
            else
                echo "   Run 'python scripts/data_initializer.py --all' to download required files"
            fi
            return 1
        else
            echo "⚠️  Data validation completed with warnings"
            return 0
        fi
    fi
}

# Function to check data files (legacy compatibility)
check_data_files() {
    echo "📁 Checking data files..."

    # Determine base path (Docker container vs local)
    if [ -w "/app" ] 2>/dev/null || [ "$PWD" = "/app" ]; then
        BASE_PATH="/app"
    else
        BASE_PATH="."
    fi

    # Use comprehensive validation but with simpler output for backward compatibility
    python -c "
import sys
sys.path.append('$BASE_PATH')
from scripts.data_initializer import DataInitializer

initializer = DataInitializer('$BASE_PATH', verbose=False)
status = initializer.check_data_completeness()

# Check VCF files (chr22 required for VCF mode; chr10/chr2/chr12 optional)
for chromosome in ['chr22', 'chr10', 'chr2', 'chr12']:
    if status.vcf_files.get(chromosome, False):
        if chromosome == 'chr22':
            print('✅ Chromosome 22 VCF file found (CYP2D6)')
        elif chromosome == 'chr10':
            print('✅ Chromosome 10 VCF file found (CYP2C19, CYP2C9)')
        elif chromosome == 'chr2':
            print('✅ Chromosome 2 VCF file found (UGT1A1)')
        else:
            print('✅ Chromosome 12 VCF file found (SLCO1B1)')
    else:
        if chromosome == 'chr22':
            print('⚠️  Chromosome 22 VCF file not found at $BASE_PATH/data/genomes/chr22.vcf.gz')
            print('   Mount VCF files as volumes or run: python scripts/data_initializer.py --vcf chr22 chr10')
            print('   See root README for deployment options.')
        elif chromosome == 'chr10':
            print('⚠️  Chromosome 10 VCF file not found; only CYP2D6 will be used.')
        # chr2/chr12 are optional; no need to warn for every missing optional chr

# Check ChEMBL database
if status.chembl_database:
    print('✅ ChEMBL database found')
else:
    print('⚠️  ChEMBL database not found at $BASE_PATH/data/chembl/chembl_34_sqlite/chembl_34.db')
    print('   Vector search will use mock data. See root README for setup.')
"
}

# Function to run quick tests
run_quick_tests() {
    echo "🧪 Running quick integration tests..."

    if python tests/quick_test.py; then
        echo "✅ Quick tests passed"
    else
        echo "❌ Quick tests failed - check configuration"
        return 1
    fi
}

# Parse command line arguments
case "$1" in
    "streamlit"|"web"|"")
        echo "🌐 Starting Streamlit web interface..."
        check_api_keys
        validate_data_integrity
        exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
        ;;

    "dev")
        echo "🚀 Starting enhanced development environment..."
        check_api_keys
        validate_data_integrity

        # Check if development tools are available
        if command -v validate-env.sh >/dev/null 2>&1; then
            echo "🔧 Validating development environment..."
            validate-env.sh

            echo "🌐 Starting development server with hot reload..."
            echo "   Streamlit: http://localhost:8501"
            echo "   Jupyter Lab: http://localhost:8888"
            echo ""
            echo "Available development commands:"
            echo "  docker exec <container> hot-reload.sh    # Hot reload server"
            echo "  docker exec <container> run-tests.sh     # Run tests with reporting"
            echo "  docker exec <container> quality-check.sh # Code quality checks"
            echo "  docker exec <container> profile.sh       # Performance profiling"
            echo ""

            # Start Streamlit with hot reload in background
            hot-reload.sh &

            # Start Jupyter Lab
            exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''
        else
            echo "❌ Development tools not available in this image"
            echo "   Use docker/Dockerfile.dev-enhanced for development features"
            exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
        fi
        ;;

    "hot-reload")
        echo "🔥 Starting hot reload development server..."
        check_api_keys
        validate_data_integrity
        exec hot-reload.sh
        ;;

    "jupyter")
        echo "📓 Starting Jupyter Lab server..."
        check_api_keys
        validate_data_integrity
        exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''
        ;;

    "quality-check")
        echo "🔍 Running code quality checks..."
        exec quality-check.sh
        ;;

    "validate-env")
        echo "🔧 Validating development environment..."
        exec validate-env.sh
        ;;

    "profile")
        echo "📊 Running performance profiling..."
        shift  # Remove 'profile' from arguments
        exec profile.sh "$@"
        ;;

    "setup-dev")
        echo "🔧 Setting up development environment..."
        check_api_keys

        # Install pre-commit hooks if available
        if [ -f ".pre-commit-config.yaml" ] && command -v pre-commit >/dev/null 2>&1; then
            echo "Installing pre-commit hooks..."
            pre-commit install
        fi

        # Setup development configuration
        if command -v validate-env.sh >/dev/null 2>&1; then
            validate-env.sh
        fi

        # Initialize data if requested
        if [ "$2" = "--data" ] || [ "$2" = "--all" ]; then
            echo "📥 Initializing data files..."
            python scripts/data_initializer.py --all
        fi

        echo "✅ Development environment setup complete"
        ;;

    "cli")
        echo "💻 Starting CLI mode..."
        check_api_keys
        validate_data_integrity
        shift  # Remove 'cli' from arguments
        exec python main.py "$@"
        ;;

    "test")
        echo "🧪 Running tests..."
        check_api_keys
        validate_data_integrity
        run_quick_tests
        echo "Running validation tests..."
        exec python tests/validation_tests.py
        ;;

    "test-dev")
        echo "🧪 Running tests with development reporting..."
        check_api_keys
        validate_data_integrity
        if command -v run-tests.sh >/dev/null 2>&1; then
            exec run-tests.sh
        else
            echo "❌ Development test runner not available in this image"
            echo "   Use docker/Dockerfile.dev-enhanced for enhanced testing"
            exec python tests/validation_tests.py
        fi
        ;;

    "validate")
        echo "🔍 Running comprehensive data validation..."
        check_api_keys
        validate_data_integrity
        validation_exit_code=$?
        if [ $validation_exit_code -eq 0 ]; then
            echo "✅ All validation checks passed"
            exit 0
        else
            echo "❌ Validation checks failed"
            echo "💡 To fix issues, run:"
            echo "   docker exec <container> python scripts/data_initializer.py --all"
            exit $validation_exit_code
        fi
        ;;

    "setup")
        echo "⚙️  Running setup tasks..."
        check_api_keys

        # Run data initialization if requested
        if [ "$2" = "--data" ] || [ "$2" = "--all" ]; then
            echo "📥 Initializing data files..."
            python scripts/data_initializer.py --all
        fi

        if [ -n "$PINECONE_API_KEY" ]; then
            echo "Setting up Pinecone index..."
            python scripts/setup_pinecone_index.py
        fi

        if [ -f "/app/data/chembl/chembl_34_sqlite/chembl_34.db" ] && [ -n "$PINECONE_API_KEY" ]; then
            echo "Ingesting ChEMBL data to Pinecone..."
            python scripts/ingest_chembl_to_pinecone.py
        fi

        # Validate setup
        echo "🔍 Validating setup..."
        validate_data_integrity

        echo "✅ Setup complete"
        ;;

    "benchmark")
        echo "📊 Running performance benchmarks..."
        check_api_keys
        validate_data_integrity
        exec python scripts/benchmark_performance.py
        ;;

    "validate-legacy"|"check")
        echo "📁 Running legacy data checks..."
        check_api_keys
        check_data_files
        echo "💡 For comprehensive validation, use: docker exec <container> validate"
        ;;

    "bash"|"shell")
        echo "🐚 Starting interactive shell..."
        exec /bin/bash
        ;;

    "help"|"-h"|"--help")
        show_help
        ;;

    *)
        echo "🚀 Custom command: $*"
        exec "$@"
        ;;
esac
