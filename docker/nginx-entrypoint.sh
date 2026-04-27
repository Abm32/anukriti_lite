#!/bin/bash
# Nginx Docker Entrypoint with SSL Setup
# This script sets up SSL certificates and starts Nginx

set -e

echo "Starting Nginx with SSL setup..."

# Run SSL certificate setup
/etc/nginx/nginx-ssl-setup.sh

# Start Nginx in the foreground
echo "Starting Nginx..."
exec nginx -g "daemon off;"
