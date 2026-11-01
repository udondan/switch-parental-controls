FROM python:3.14-alpine AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.14-alpine

LABEL com.docker.desktop.mcp="true"
LABEL com.docker.desktop.mcp.name="switch-parental-controls"

COPY --from=builder /install /usr/local

# pip isn't needed at runtime, and its vendored copies of urllib3, msgpack
# and setuptools show up in vulnerability scans. apk upgrade pulls fixes for
# Alpine packages released after the base image.
# /data is owned by the unprivileged user, so a volume mounted there is
# writable.
RUN apk upgrade --no-cache \
    && python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.*/ensurepip \
    && adduser -D -H -u 10001 switch && mkdir /data && chown switch:switch /data
USER switch

# The credentials file written by `login` and the caches live under
# XDG_CONFIG_HOME. A volume on /data keeps them between runs.
ENV XDG_CONFIG_HOME=/data

# `docker run udondan/switch-parental-controls <command>` runs the CLI; without
# a command the image starts the MCP server, which is what the Docker MCP
# Toolkit expects.
ENTRYPOINT ["switch-parental-controls"]
CMD ["mcp"]
