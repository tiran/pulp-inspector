# syntax=docker/dockerfile:1
# Expects pre-built artifacts in dist/:
#   - dist/*.whl (the project wheel)
#   - dist/requirements.txt (locked dependencies)
# Build with: make build
FROM registry.access.redhat.com/ubi10/ubi-minimal:latest

# Layer 1: system packages and application user (rarely changes)
RUN bash -euo pipefail <<EOF
microdnf install -y --disableplugin=subscription-manager --nodocs \
    python3.12 shadow-utils
useradd -u 1001 -g 0 -d /opt/app-root/src -M -s /bin/bash \
    -c "Default Application User" default
mkdir -p -m 770 /opt/app-root/src/.cache
chown -R 1001:0 /opt/app-root/src
microdnf remove -y shadow-utils
microdnf clean all
EOF

# Layer 2: install uv and create virtual environment (changes on uv version bumps)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv venv --python python3.12 --allow-existing /opt/app-root

ENV VIRTUAL_ENV=/opt/app-root \
    PATH="/opt/app-root/bin:$PATH" \
    HOME=/opt/app-root/src

# Layer 3: install locked dependencies (changes on dependency updates)
COPY dist/requirements.txt /tmp/requirements.txt
RUN bash -euo pipefail <<EOF
uv pip install --no-cache -r /tmp/requirements.txt
rm /tmp/requirements.txt
EOF

# Layer 4: install the project wheel (changes on every release)
COPY dist/*.whl /tmp/dist/
RUN bash -euo pipefail <<EOF
uv pip install --no-cache --no-deps /tmp/dist/*.whl
rm -rf /tmp/dist
EOF

WORKDIR ${HOME}
USER 1001

VOLUME /opt/app-root/src/.cache
EXPOSE 9090

ENTRYPOINT ["pulp-inspector"]
CMD ["--host", "0.0.0.0", "--port", "9090"]
