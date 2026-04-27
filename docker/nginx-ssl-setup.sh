#!/bin/bash
# Nginx SSL Certificate Setup Script
# This script configures Nginx to use available SSL certificates
# Supports multiple certificate naming conventions

set -e

SSL_DIR="/etc/nginx/ssl"
NGINX_CONF="/etc/nginx/nginx.conf"
NGINX_CONF_TEMPLATE="/etc/nginx/nginx.conf.template"

echo "Starting Nginx SSL certificate setup..."

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"

# Function to check if certificate files exist and are valid
check_certificate() {
    local cert_file="$1"
    local key_file="$2"

    if [[ -f "$cert_file" && -f "$key_file" ]]; then
        # Check if certificate is valid
        if openssl x509 -in "$cert_file" -noout -checkend 0 >/dev/null 2>&1; then
            # Check if private key matches certificate
            cert_modulus=$(openssl x509 -noout -modulus -in "$cert_file" 2>/dev/null | openssl md5)
            key_modulus=$(openssl rsa -noout -modulus -in "$key_file" 2>/dev/null | openssl md5)

            if [[ "$cert_modulus" == "$key_modulus" ]]; then
                echo "Valid certificate found: $cert_file"
                return 0
            else
                echo "Warning: Certificate and key do not match: $cert_file, $key_file"
            fi
        else
            echo "Warning: Invalid or expired certificate: $cert_file"
        fi
    fi
    return 1
}

# Function to generate self-signed certificate if none exists
generate_self_signed() {
    local domain="$1"
    local cert_file="$SSL_DIR/${domain}.crt"
    local key_file="$SSL_DIR/${domain}.key"

    echo "Generating self-signed certificate for domain: $domain"

    # Create OpenSSL configuration
    cat > "$SSL_DIR/openssl.conf" << EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Development
L = Local
O = SynthaTrial
OU = Development
CN = $domain

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $domain
DNS.2 = localhost
DNS.3 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

    # Generate private key
    openssl genrsa -out "$key_file" 2048

    # Generate certificate
    openssl req -new -x509 -key "$key_file" -out "$cert_file" -days 365 -config "$SSL_DIR/openssl.conf"

    # Set appropriate permissions
    chmod 600 "$key_file"
    chmod 644 "$cert_file"

    echo "Self-signed certificate generated: $cert_file"
}

# Function to update Nginx configuration with certificate paths
update_nginx_config() {
    local cert_file="$1"
    local key_file="$2"

    echo "Updating Nginx configuration with certificate: $cert_file"

    # Update the SSL certificate paths in the Nginx configuration
    sed -i "s|ssl_certificate .*;|ssl_certificate $cert_file;|g" "$NGINX_CONF"
    sed -i "s|ssl_certificate_key .*;|ssl_certificate_key $key_file;|g" "$NGINX_CONF"

    echo "Nginx configuration updated successfully"
}

# Main certificate detection and setup logic
CERT_FILE=""
KEY_FILE=""

# Priority order for certificate detection:
# 1. localhost.crt/localhost.key (SSL Manager default)
# 2. cert.pem/key.pem (original configuration)
# 3. cert.crt/cert.key (alternative naming)
# 4. server.crt/server.key (common naming)

CERT_PATTERNS=(
    "localhost.crt:localhost.key"
    "cert.pem:key.pem"
    "cert.crt:cert.key"
    "server.crt:server.key"
)

echo "Searching for existing SSL certificates..."

for pattern in "${CERT_PATTERNS[@]}"; do
    IFS=':' read -r cert_name key_name <<< "$pattern"
    cert_path="$SSL_DIR/$cert_name"
    key_path="$SSL_DIR/$key_name"

    if check_certificate "$cert_path" "$key_path"; then
        CERT_FILE="$cert_path"
        KEY_FILE="$key_path"
        break
    fi
done

# If no valid certificate found, generate self-signed certificate
if [[ -z "$CERT_FILE" ]]; then
    echo "No valid SSL certificate found. Generating self-signed certificate..."
    generate_self_signed "localhost"
    CERT_FILE="$SSL_DIR/localhost.crt"
    KEY_FILE="$SSL_DIR/localhost.key"
fi

# Update Nginx configuration with the selected certificate
update_nginx_config "$CERT_FILE" "$KEY_FILE"

# Validate Nginx configuration
echo "Validating Nginx configuration..."
if nginx -t; then
    echo "Nginx configuration is valid"
else
    echo "ERROR: Nginx configuration validation failed"
    exit 1
fi

# Display certificate information
echo "SSL Certificate Setup Complete:"
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"

# Show certificate details
if command -v openssl >/dev/null 2>&1; then
    echo "Certificate Details:"
    openssl x509 -in "$CERT_FILE" -noout -subject -dates -issuer 2>/dev/null || echo "  Could not read certificate details"
fi

echo "Nginx is ready to start with SSL support"
