# Auralynq TLS reverse proxy image (Caddy + a baked self-signed cert).
#
# We pre-generate a self-signed cert at build time (with the server IP/hostname as
# a SAN, overridable via AURALYNQ_CERT_HOST) and serve it with an explicit
# `tls cert key` directive. This avoids Caddy's on-demand internal-CA issuance,
# which is unreliable for bare-IP sites on this rootless host. For a real domain,
# set AURALYNQ_SITE_ADDRESS=https://your.domain to use Let's Encrypt instead
# (the explicit cert is simply ignored when a public domain is configured).
FROM docker.io/library/caddy:2.8-alpine

LABEL org.opencontainers.image.title="auralynq-caddy" \
      org.opencontainers.image.description="Auralynq TLS reverse proxy (Caddy) — single public HTTPS entrypoint" \
      org.opencontainers.image.source="https://github.com/MHHamdan/Auralynq" \
      org.opencontainers.image.licenses="Apache-2.0"

ARG AURALYNQ_CERT_HOST=localhost
RUN apk add --no-cache openssl \
    && mkdir -p /certs \
    && openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout /certs/site.key -out /certs/site.crt -days 825 \
        -subj "/CN=${AURALYNQ_CERT_HOST}" \
        -addext "subjectAltName=DNS:${AURALYNQ_CERT_HOST},DNS:localhost,IP:${AURALYNQ_CERT_HOST},IP:127.0.0.1" \
        2>/dev/null || \
       openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout /certs/site.key -out /certs/site.crt -days 825 \
        -subj "/CN=${AURALYNQ_CERT_HOST}" \
        -addext "subjectAltName=DNS:${AURALYNQ_CERT_HOST},DNS:localhost,IP:127.0.0.1"
