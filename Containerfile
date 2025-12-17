# Stage 1: Builder stage (includes build dependencies like gcc)
FROM registry.access.redhat.com/ubi9/python-312:latest AS builder

# Switch to root for installing system packages
USER 0

ARG APP_VERSION=0.0.0
ENV APP_VERSION=$APP_VERSION

# Install system dependencies needed for compiling certain Python packages (e.g., python-freeipa)
RUN dnf install -y \
    gcc \
    openldap-devel \
    cyrus-sasl-devel \
    openssl-devel && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/app-root/src

# Set work directory
WORKDIR $APP_HOME

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -f requirements.txt

# Switch back to non-root user for safety
USER 1001

FROM registry.access.redhat.com/ubi9/python-312:latest

# Copy the installed Python site-packages from the builder
COPY --from=builder /opt/app-root /opt/app-root

# Ensure the correct ownership for the app directory
RUN chown -R 1001:0 /opt/app-root && \
    chmod -R g+u /opt/app-root

# Switch to the default non-root user
USER 1001

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/app-root/src

# Set work directory
WORKDIR $APP_HOME

# Copy the application code
COPY app ./app

# Expose port 8443 for secured webhooks
EXPOSE 8443

# Run Uvicorn with SSL enabled
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8443", "--ssl-keyfile", "/var/run/secrets/serving-cert/tls.key", "--ssl-certfile", "/var/run/secrets/serving-cert/tls.crt"]