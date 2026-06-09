# Hermes WebUI + Agent 从 git.superic.com 构建（见 docker-compose.yml）

ARG HERMES_WEBUI_REPO=http://git.superic.com/aiplatform/hermes-webui.git
ARG HERMES_WEBUI_REF=master

# ── Stage 1: clone hermes-webui ──────────────────────────────────────────────
FROM python:3.12-slim AS webui-clone
ARG HERMES_WEBUI_REPO
ARG HERMES_WEBUI_REF

ARG USE_CN_MIRRORS=1
ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG NPM_REGISTRY=https://registry.npmmirror.com

ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV NPM_CONFIG_REGISTRY=${NPM_REGISTRY}
ENV UV_DEFAULT_INDEX=${PIP_INDEX_URL}

RUN apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && git clone --depth=1 --branch "${HERMES_WEBUI_REF}" "${HERMES_WEBUI_REPO}" /src

# ── Stage 2: hermes-webui 基础镜像（对齐官方 Dockerfile 结构）────────────────
FROM python:3.12-slim AS hermes-webui-base

LABEL maintainer="superic"
LABEL description="Hermes WebUI — built from Git source"

ENV DEBIAN_FRONTEND=noninteractive

ARG BUILD_APT_PROXY=
RUN if [ "A${BUILD_APT_PROXY:-}" != "A" ]; then \
      printf 'Acquire::http::Proxy "%s";\n' "$BUILD_APT_PROXY" > /etc/apt/apt.conf.d/01proxy; \
    fi \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates wget gnupg \
    apt-utils locales sudo curl rsync openssh-client \
    build-essential python3-dev libffi-dev \
    git jq \
    nodejs npm ripgrep ffmpeg procps xz-utils unzip \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

RUN localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG=en_US.utf8
ENV LC_ALL=C

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /apptoo

RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
  && groupadd -g 1000 hermeswebui \
  && groupadd -g 1001 hermeswebuitoo \
  && useradd -u 1000 -d /home/hermeswebui -g hermeswebui -s /bin/bash -m hermeswebui \
  && usermod -G users hermeswebui \
  && adduser hermeswebui sudo \
  && useradd -u 1001 -d /home/hermeswebuitoo -g hermeswebuitoo -s /bin/bash -m hermeswebuitoo \
  && usermod -G users hermeswebuitoo \
  && adduser hermeswebuitoo sudo \
  && chown -R hermeswebuitoo:hermeswebuitoo /apptoo

COPY --from=webui-clone /src/docker_init.bash /hermeswebui_init.bash
RUN chmod 555 /hermeswebui_init.bash

RUN touch /.within_container \
  && rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/01proxy \
  && apt-get clean

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

USER hermeswebuitoo

COPY --from=webui-clone --chown=hermeswebuitoo:hermeswebuitoo /src /apptoo

ARG HERMES_VERSION=git-build
RUN echo "__version__ = '${HERMES_VERSION}'" > /apptoo/api/_version.py

ENV HERMES_WEBUI_HOST=0.0.0.0
ENV HERMES_WEBUI_PORT=8787

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8787/health || exit 1

# ── Stage 3: 扩展层（hermes-agent + 运行工具，与原 Dockerfile 一致）──────────
# 系统依赖已在 Stage 2 一次性安装，此处不再 apt-get update。
FROM hermes-webui-base

USER root
ENV DEBIAN_FRONTEND=noninteractive

ARG HERMES_AGENT_REPO=http://git.superic.com/aiplatform/hermes-agent.git
ARG HERMES_AGENT_REF=master
#RUN git clone --depth=1 --branch "${HERMES_AGENT_REF}" "${HERMES_AGENT_REPO}" /opt/hermes-agent \
#  && chmod -R a+rX /opt/hermes-agent

RUN git clone --depth=1 --branch "${HERMES_AGENT_REF}" "${HERMES_AGENT_REPO}" /opt/hermes-agent \
  && mkdir -p /home/hermeswebui/.hermes \
  && ln -sfn /opt/hermes-agent /home/hermeswebui/.hermes/hermes-agent \
  && ln -sfn /opt/hermes-agent /opt/hermes \
  && chmod -R a+rX /opt/hermes-agent \
  && chown -R hermeswebui:hermeswebui /home/hermeswebui/.hermes \
  && chown -R hermeswebui:hermeswebui /opt/hermes-agent

# Install hermes-agent into the same Python venv used by hermes-webui.
# WebUI uses /app/venv/bin/python; adding /opt/hermes-agent to sys.path is not enough
# because AIAgent is imported from the installed/editable project metadata.
RUN python3 -m venv /app/venv \
  && /app/venv/bin/python -m pip install --upgrade pip setuptools wheel \
  && cd /opt/hermes-agent \
  && (/app/venv/bin/python -m pip install -e ".[all]" || /app/venv/bin/python -m pip install -e .) \
  && /app/venv/bin/python - <<'PY'
from run_agent import AIAgent
print("OK: hermes-agent AIAgent importable from /app/venv")
PY

# Optional GBrain and MCP runtime tooling. Use internal mirrors in production.
ARG INSTALL_GBRAIN=1
ARG GBRAIN_REPO=http://git.superic.com/aiplatform/gbrain.git
RUN if [ "${INSTALL_GBRAIN}" = "1" ]; then \
      (curl -fsSL https://bun.sh/install | bash -s -- bun-v1.2.15 \
        && ln -sf /root/.bun/bin/bun /usr/local/bin/bun \
        && ln -sf /root/.bun/bin/bunx /usr/local/bin/bunx \
        && bun install -g "${GBRAIN_REPO}" \
        && echo "OK: gbrain installed") \
      || echo "WARN: gbrain install failed; init-brain-runtime.sh will skip gbrain."; \
    fi

ARG INSTALL_FILESYSTEM_MCP=1
RUN if [ "${INSTALL_FILESYSTEM_MCP}" = "1" ]; then \
      npm install -g @modelcontextprotocol/server-filesystem \
      || echo "WARN: filesystem MCP global install failed; npx fallback may still work."; \
    fi

ARG INSTALL_CLAWSEC=0
ARG CLAWSEC_REPO=http://git.superic.com/aiplatform/clawsec.git
RUN if [ "${INSTALL_CLAWSEC}" = "1" ]; then \
      git clone --depth=1 "${CLAWSEC_REPO}" /opt/clawsec \
      || echo "WARN: clawsec clone failed; install-security-skills.sh will install fallback local security skills."; \
    fi

ENV HERMES_WEBUI_AGENT_DIR=/opt/hermes-agent
ENV HERMES_WEBUI_AUTO_INSTALL=1
ENV HERMES_HOME=/data/hermes
ENV HERMES_CONFIG_PATH=/data/hermes/config.yaml
ENV HERMES_WEBUI_DEFAULT_WORKSPACE=/data/hermes/workspace
ENV HERMES_WEBUI_STATE_DIR=/data/hermes/webui
ENV GBRAIN_HOME=/data/hermes/gbrain
ENV GBRAIN_VAULT=/data/hermes/obsidian-vault

RUN mkdir -p /data/hermes /workspace /uv_cache /app \
  && touch /app/venv/.deps_installed \
  && chown -R hermeswebui:hermeswebui \
      /data /workspace /uv_cache /app /app/venv /home/hermeswebui/.hermes /opt/hermes-agent \
  && chmod -R u+rwX,g+rwX /data /workspace /uv_cache /app /app/venv /home/hermeswebui/.hermes


USER hermeswebui

EXPOSE 8787

CMD ["/hermeswebui_init.bash"]
