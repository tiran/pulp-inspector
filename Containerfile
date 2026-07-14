# Stage 1: build the frontend and export locked requirements
FROM registry.access.redhat.com/ubi9/python-312:latest AS builder

USER 0
RUN pip install --no-cache-dir uv

WORKDIR /build
COPY . .

# Build the project wheel (hatch_build.py runs npm ci + vite build)
# then export locked dependencies with hashes
RUN uv build --no-cache --wheel --out-dir /build/dist
RUN uv export --no-dev --no-editable --no-header --no-emit-project --no-hashes > /build/requirements.txt

# Stage 2: minimal runtime image
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Install Python
RUN microdnf install -y --disableplugin=subscription-manager --nodocs \
        python3.12 python3.12-pip && \
    microdnf clean all

# Install the project wheel and locked dependencies with hash verification
COPY --from=builder /build/requirements.txt /tmp/requirements.txt
COPY --from=builder /build/dist/*.whl /tmp/dist/
RUN python3.12 -m pip install --no-cache-dir \
        -r /tmp/requirements.txt /tmp/dist/*.whl && \
    microdnf remove -y python3.12-pip && \
    microdnf clean all && \
    rm -rf /tmp/requirements.txt /tmp/dist

# Create application user and cache directory
RUN useradd -u 1001 -g 0 -d /opt/app-root/src -M -s /bin/bash -c "Default Application User" default && \
    mkdir -p -m 770 /opt/app-root/src/.cache && \
    chown -R 1001:0 /opt/app-root/src

ENV HOME=/opt/app-root/src

WORKDIR ${HOME}
USER 1001

VOLUME /opt/app-root/src/.cache
EXPOSE 9090

ENTRYPOINT ["pulp-inspector"]
CMD ["--host", "0.0.0.0", "--port", "9090"]
