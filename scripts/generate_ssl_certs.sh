#!/bin/bash
#
# SSL Certificate Generation Script for SynthaTrial Docker Enhancements
#
# This script automates the generation of self-signed SSL certificates for development
# and testing environments. It uses the SSL Manager Python module for certificate
# generation and provides comprehensive error handling and validation.
#
# Author: SynthaTrial Development Team
# Version: 0.2 Beta
#
# Usage:
#   ./scripts/generate_ssl_certs.sh [domain] [output_directory]
#   ./scripts/generate_ssl_certs.sh --help
#
# Examples:
#   ./scripts/generate_ssl_certs.sh localhost
#   ./scripts/generate_ssl_certs.sh synthatrial.local docker/ssl
#   ./scripts/generate_ssl_certs.sh --domain=example.com --output-dir=certs/
#

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_MANAGER_SCRIPT="$SCRIPT_DIR/ssl_manager.py"
DEFAULT_DOMAIN="localhost"
DEFAULT_OUTPUT_DIR="docker/ssl"
VERBOSE=false

# Color codes for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Help function
show_help() {
    cat << EOF
SSL Certificate Generation Script for SynthaTrial

USAGE:
    $0 [OPTIONS] [DOMAIN] [OUTPUT_DIRECTORY]

ARGUMENTS:
    DOMAIN              Domain name for the certificate (default: localhost)
    OUTPUT_DIRECTORY    Directory to store certificates (default: docker/ssl)

OPTIONS:
    -d, --domain DOMAIN         Specify domain name for certificate
    -o, --output-dir DIR        Specify output directory for certificates
    -v, --verbose               Enable verbose output
    -h, --help                  Show this help message
    --validate                  Validate generated certificates after creation
    --force                     Overwrite existing certificates without prompting

EXAMPLES:
    # Generate certificate for localhost (default)
    $0

    # Generate certificate for specific domain
    $0 synthatrial.local

    # Generate certificate with custom output directory
    $0 example.com /path/to/certs

    # Generate with options
    $0 --domain=api.synthatrial.com --output-dir=ssl/ --verbose

    # Generate and validate certificates
    $0 --domain=localhost --validate

NOTES:
    - Certificates are generated as self-signed for development use only
    - For production, replace with certificates from a trusted Certificate Authority
    - The script requires OpenSSL to be installed and available in PATH
    - Generated certificates are valid for 365 days
    - Private keys are created with 600 permissions (owner read/write only)
    - Certificates are created with 644 permissions (owner read/write, others read)

EOF
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if OpenSSL is available
    if ! command -v openssl &> /dev/null; then
        log_error "OpenSSL is not installed or not in PATH"
        log_error "Please install OpenSSL: apt-get install openssl (Ubuntu/Debian) or brew install openssl (macOS)"
        exit 1
    fi

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        log_error "Please install Python 3"
        exit 1
    fi

    # Check if SSL Manager script exists
    if [ ! -f "$SSL_MANAGER_SCRIPT" ]; then
        log_error "SSL Manager script not found: $SSL_MANAGER_SCRIPT"
        log_error "Please ensure the SSL Manager is properly installed"
        exit 1
    fi

    # Check if SSL Manager script is executable
    if [ ! -x "$SSL_MANAGER_SCRIPT" ]; then
        log_debug "Making SSL Manager script executable"
        chmod +x "$SSL_MANAGER_SCRIPT"
    fi

    log_success "Prerequisites check passed"
}

# Function to validate domain name
validate_domain() {
    local domain="$1"

    # Allow localhost specifically
    if [ "$domain" = "localhost" ]; then
        log_debug "Domain validation passed: $domain (localhost)"
        return 0
    fi

    # Allow IP addresses (basic check)
    if [[ "$domain" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        log_debug "Domain validation passed: $domain (IP address)"
        return 0
    fi

    # Basic domain validation (allows valid domain names with dots)
    if [[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$ ]]; then
        log_debug "Domain validation passed: $domain"
        return 0
    fi

    log_error "Invalid domain name: $domain"
    log_error "Domain names should contain only letters, numbers, hyphens, and dots"
    log_error "Examples: localhost, example.com, api.synthatrial.local, 127.0.0.1"
    return 1
}

# Function to setup certificate directory
setup_certificate_directory() {
    local output_dir="$1"

    log_info "Setting up certificate directory: $output_dir"

    # Create output directory if it doesn't exist
    if [ ! -d "$output_dir" ]; then
        log_debug "Creating directory: $output_dir"
        mkdir -p "$output_dir"
    fi

    # Check if directory is writable
    if [ ! -w "$output_dir" ]; then
        log_error "Output directory is not writable: $output_dir"
        log_error "Please check directory permissions"
        exit 1
    fi

    # Set appropriate permissions for SSL directory
    chmod 755 "$output_dir"

    log_success "Certificate directory setup complete"
}

# Function to check for existing certificates
check_existing_certificates() {
    local domain="$1"
    local output_dir="$2"
    local force="$3"

    local cert_file="$output_dir/${domain}.crt"
    local key_file="$output_dir/${domain}.key"

    if [ -f "$cert_file" ] || [ -f "$key_file" ]; then
        if [ "$force" = true ]; then
            log_warning "Existing certificates found, overwriting due to --force flag"
            return 0
        fi

        log_warning "Existing certificates found:"
        [ -f "$cert_file" ] && log_warning "  Certificate: $cert_file"
        [ -f "$key_file" ] && log_warning "  Private key: $key_file"

        echo -n "Do you want to overwrite existing certificates? [y/N]: "
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY])
                log_info "Proceeding with certificate generation"
                return 0
                ;;
            *)
                log_info "Certificate generation cancelled"
                exit 0
                ;;
        esac
    fi

    return 0
}

# Function to generate SSL certificates using SSL Manager
generate_certificates() {
    local domain="$1"
    local output_dir="$2"
    local validate_certs="$3"

    log_info "Generating SSL certificates for domain: $domain"
    log_info "Output directory: $output_dir"

    # Prepare SSL Manager command
    local ssl_manager_cmd=("python3" "$SSL_MANAGER_SCRIPT")
    ssl_manager_cmd+=("--domain" "$domain")
    ssl_manager_cmd+=("--output-dir" "$output_dir")

    if [ "$VERBOSE" = true ]; then
        ssl_manager_cmd+=("--verbose")
    fi

    log_debug "Executing: ${ssl_manager_cmd[*]}"

    # Execute SSL Manager
    if "${ssl_manager_cmd[@]}"; then
        log_success "SSL certificates generated successfully"

        # Display generated files
        local cert_file="$output_dir/${domain}.crt"
        local key_file="$output_dir/${domain}.key"

        if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
            log_info "Generated files:"
            log_info "  Certificate: $cert_file"
            log_info "  Private key: $key_file"

            # Show file permissions
            log_debug "File permissions:"
            log_debug "  $(ls -la "$cert_file")"
            log_debug "  $(ls -la "$key_file")"

            # Validate certificates if requested
            if [ "$validate_certs" = true ]; then
                validate_generated_certificates "$cert_file" "$key_file"
            fi

            # Show certificate information
            show_certificate_info "$cert_file"

        else
            log_error "Expected certificate files were not created"
            return 1
        fi
    else
        log_error "SSL certificate generation failed"
        log_error "Check the SSL Manager output above for details"
        return 1
    fi
}

# Function to validate generated certificates
validate_generated_certificates() {
    local cert_file="$1"
    local key_file="$2"

    log_info "Validating generated certificates..."

    # Use SSL Manager for validation
    local validation_cmd=("python3" "$SSL_MANAGER_SCRIPT")
    validation_cmd+=("--validate" "$cert_file")
    validation_cmd+=("--key" "$key_file")

    if [ "$VERBOSE" = true ]; then
        validation_cmd+=("--verbose")
    fi

    if "${validation_cmd[@]}"; then
        log_success "Certificate validation passed"
    else
        log_error "Certificate validation failed"
        return 1
    fi
}

# Function to show certificate information
show_certificate_info() {
    local cert_file="$1"

    log_info "Certificate Information:"

    # Extract and display certificate details
    if command -v openssl &> /dev/null && [ -f "$cert_file" ]; then
        # Get certificate subject (domain)
        local subject
        subject=$(openssl x509 -in "$cert_file" -noout -subject 2>/dev/null | sed 's/subject=//')
        [ -n "$subject" ] && log_info "  Subject: $subject"

        # Get certificate expiration
        local expiry
        expiry=$(openssl x509 -in "$cert_file" -noout -enddate 2>/dev/null | sed 's/notAfter=//')
        [ -n "$expiry" ] && log_info "  Expires: $expiry"

        # Get certificate fingerprint
        local fingerprint
        fingerprint=$(openssl x509 -in "$cert_file" -noout -fingerprint -sha256 2>/dev/null | sed 's/SHA256 Fingerprint=//')
        [ -n "$fingerprint" ] && log_debug "  SHA256 Fingerprint: $fingerprint"
    fi
}

# Function to provide usage guidance
show_usage_guidance() {
    local domain="$1"
    local output_dir="$2"

    log_info ""
    log_info "Usage Guidance:"
    log_info "==============="
    log_info ""
    log_info "Docker Compose Configuration:"
    log_info "  Add the following to your docker-compose.yml volumes section:"
    log_info "    - ./$output_dir:/app/ssl:ro"
    log_info ""
    log_info "Nginx Configuration:"
    log_info "  ssl_certificate     /app/ssl/${domain}.crt;"
    log_info "  ssl_certificate_key /app/ssl/${domain}.key;"
    log_info ""
    log_info "Environment Variables:"
    log_info "  SSL_CERT_PATH=/app/ssl/${domain}.crt"
    log_info "  SSL_KEY_PATH=/app/ssl/${domain}.key"
    log_info ""
    log_warning "IMPORTANT: These are self-signed certificates for development only!"
    log_warning "For production, use certificates from a trusted Certificate Authority."
    log_info ""
}

# Main function
main() {
    local domain="$DEFAULT_DOMAIN"
    local output_dir="$DEFAULT_OUTPUT_DIR"
    local validate_certs=false
    local force=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--domain)
                domain="$2"
                shift 2
                ;;
            --domain=*)
                domain="${1#*=}"
                shift
                ;;
            -o|--output-dir)
                output_dir="$2"
                shift 2
                ;;
            --output-dir=*)
                output_dir="${1#*=}"
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --validate)
                validate_certs=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                log_error "Use --help for usage information"
                exit 1
                ;;
            *)
                # Positional arguments
                if [ "$domain" = "$DEFAULT_DOMAIN" ]; then
                    domain="$1"
                elif [ "$output_dir" = "$DEFAULT_OUTPUT_DIR" ]; then
                    output_dir="$1"
                else
                    log_error "Too many positional arguments: $1"
                    log_error "Use --help for usage information"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Convert relative paths to absolute paths
    if [[ ! "$output_dir" = /* ]]; then
        output_dir="$PROJECT_ROOT/$output_dir"
    fi

    log_info "SynthaTrial SSL Certificate Generation"
    log_info "====================================="
    log_info "Domain: $domain"
    log_info "Output Directory: $output_dir"
    log_info ""

    # Execute main workflow
    check_prerequisites
    validate_domain "$domain"
    setup_certificate_directory "$output_dir"
    check_existing_certificates "$domain" "$output_dir" "$force"

    if generate_certificates "$domain" "$output_dir" "$validate_certs"; then
        show_usage_guidance "$domain" "$(basename "$output_dir")"
        log_success "SSL certificate generation completed successfully!"
        exit 0
    else
        log_error "SSL certificate generation failed!"
        exit 1
    fi
}

# Trap to handle script interruption
trap 'log_error "Script interrupted"; exit 130' INT TERM

# Execute main function with all arguments
main "$@"
