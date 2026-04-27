# Docker SSL Configuration Summary

## Enhanced Nginx Configuration for SynthaTrial

This directory contains the enhanced Nginx configuration with SSL redirection and security features for SynthaTrial's Docker deployment.

### Key Features Implemented

#### 1. SSL Certificate Management
- **Automatic certificate detection** with priority-based fallback
- **Self-signed certificate generation** for development
- **Production certificate support** with validation
- **Certificate expiration monitoring** and renewal guidance

#### 2. HTTP to HTTPS Redirection
- **Automatic 301 redirects** from HTTP to HTTPS
- **Health check exceptions** for Docker monitoring
- **Flexible server name matching** (`localhost` and `_`)

#### 3. Enhanced Security Headers
- **HSTS (HTTP Strict Transport Security)** with 2-year max-age
- **Content Security Policy (CSP)** for XSS protection
- **X-Frame-Options: DENY** to prevent clickjacking
- **X-Content-Type-Options: nosniff** to prevent MIME sniffing
- **Referrer Policy** for privacy protection

#### 4. Performance Optimizations
- **Rate limiting** (10 requests/second with burst capacity)
- **Static file caching** with 1-year expiration
- **Proxy buffering** for improved performance
- **Keep-alive connections** to upstream servers

#### 5. Streamlit-Specific Features
- **WebSocket support** for real-time features
- **Enhanced proxy headers** for proper forwarding
- **Long timeout values** for data processing operations
- **Health check endpoint** integration

### Files Overview

| File | Purpose |
|------|---------|
| `nginx.conf` | Main Nginx configuration with SSL and security |
| `nginx-ssl-setup.sh` | Automatic SSL certificate detection and setup |
| `nginx-entrypoint.sh` | Docker entrypoint with SSL initialization |
| `ssl/` | Directory for SSL certificates |

### Certificate Detection Priority

The system automatically detects certificates in this order:

1. `localhost.crt/localhost.key` (SSL Manager default)
2. `cert.pem/key.pem` (original configuration)
3. `cert.crt/cert.key` (alternative naming)
4. `server.crt/server.key` (common naming)

If no certificates are found, self-signed certificates are automatically generated.

### Usage Examples

```bash
# Generate SSL certificates
make ssl-setup

# Start development with SSL
make ssl-dev

# Start production with SSL
make run-nginx

# Test SSL configuration
make ssl-test

# View certificate information
make ssl-info
```

### Security Configuration Details

#### SSL/TLS Settings
- **Protocols**: TLSv1.2, TLSv1.3 only
- **Cipher suites**: Modern, secure ciphers with forward secrecy
- **OCSP stapling**: Enabled for certificate validation
- **Session management**: Optimized for performance and security

#### Rate Limiting
- **API rate limit**: 10 requests/second per IP
- **Burst capacity**: 20 requests with no delay
- **Health checks**: Exempt from rate limiting

#### Content Security Policy
```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' wss: ws:;
```

### Integration with Docker Compose

#### Development (docker-compose.dev.yml)
- **Ports**: 8080 (HTTP) → 8443 (HTTPS)
- **Profile**: `nginx-dev`
- **SSL directory**: Read/write mounted for certificate generation

#### Production (docker-compose.prod.yml)
- **Ports**: 80 (HTTP) → 443 (HTTPS)
- **Profile**: `nginx`
- **SSL directory**: Read/write mounted for certificate management
- **Health checks**: HTTPS endpoint monitoring

### Monitoring and Health Checks

- **Container health**: Automated HTTPS health checks
- **Certificate monitoring**: Expiration tracking and alerts
- **Performance metrics**: Built-in Nginx status and logging
- **Security scanning**: Integration with vulnerability assessment

### Troubleshooting

Common issues and solutions:

1. **Certificate not found**: Run `make ssl-setup`
2. **Permission denied**: Check SSL directory permissions
3. **Browser warnings**: Expected for self-signed certificates
4. **Configuration errors**: Validate with `nginx -t`

For detailed troubleshooting, see the root README.

### Production Deployment Notes

1. **Replace self-signed certificates** with trusted CA certificates
2. **Configure DNS** to point to your server
3. **Set up certificate renewal** (Let's Encrypt recommended)
4. **Monitor certificate expiration** with automated alerts
5. **Review security headers** for your specific requirements

This enhanced configuration provides enterprise-grade SSL support while maintaining compatibility with SynthaTrial's existing Docker infrastructure.
