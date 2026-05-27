ARG HERMES_WEBUI_IMAGE=ghcr.io/nesquena/hermes-webui:latest
ARG HERMES_AGENT_REPO=https://github.com/NousResearch/hermes-agent.git
ARG HERMES_AGENT_REF=main

FROM ${HERMES_WEBUI_IMAGE}

USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential python3-dev libffi-dev \
    git openssh-client curl ca-certificates jq \
    nodejs npm ripgrep ffmpeg procps xz-utils \
  && rm -rf /var/lib/apt/lists/*

ARG HERMES_AGENT_REPO
ARG HERMES_AGENT_REF
RUN git clone --depth=1 --branch "${HERMES_AGENT_REF}" "${HERMES_AGENT_REPO}" /opt/hermes-agent \
  && chmod -R a+rX /opt/hermes-agent

ENV HERMES_WEBUI_HOST=0.0.0.0
ENV HERMES_WEBUI_PORT=8787
ENV HERMES_WEBUI_AGENT_DIR=/opt/hermes-agent
ENV HERMES_WEBUI_AUTO_INSTALL=1
ENV HERMES_HOME=/data/hermes
ENV HERMES_CONFIG_PATH=/data/hermes/config.yaml
ENV HERMES_WEBUI_DEFAULT_WORKSPACE=/data/hermes/workspace
ENV HERMES_WEBUI_STATE_DIR=/data/hermes/webui

RUN mkdir -p /data/hermes /workspace /uv_cache /app \
  && chown -R hermeswebui:hermeswebui /data /workspace /uv_cache /app || true

EXPOSE 8787
