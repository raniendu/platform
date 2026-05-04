# syntax=docker/dockerfile:1.20

ARG PAPERCLIP_VERSION=v2026.428.0

FROM node:lts-trixie-slim AS base

ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gosu curl gh git wget ripgrep python3 \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable

RUN usermod -u "$USER_UID" --non-unique node \
    && groupmod -g "$USER_GID" --non-unique node \
    && usermod -g "$USER_GID" -d /paperclip node

FROM base AS source

ARG PAPERCLIP_VERSION
WORKDIR /app

RUN curl -fsSL "https://github.com/paperclipai/paperclip/archive/refs/tags/${PAPERCLIP_VERSION}.tar.gz" \
    | tar -xz --strip-components=1

FROM base AS build

WORKDIR /app

COPY --from=source /app /app

RUN pnpm install --frozen-lockfile
RUN pnpm --filter @paperclipai/ui build
RUN pnpm --filter @paperclipai/plugin-sdk build
RUN pnpm --filter @paperclipai/server build
RUN test -f server/dist/index.js || (echo "ERROR: server build output missing" && exit 1)

FROM base AS production

ARG USER_UID=1000
ARG USER_GID=1000

WORKDIR /app

COPY --chown=node:node --from=build /app /app

RUN npm install --global --omit=dev @anthropic-ai/claude-code@latest @openai/codex@latest opencode-ai \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssh-client jq \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /paperclip \
    && chown node:node /paperclip

COPY --from=source /app/scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV NODE_ENV=production \
    HOME=/paperclip \
    HOST=0.0.0.0 \
    PORT=3100 \
    SERVE_UI=true \
    PAPERCLIP_HOME=/paperclip \
    PAPERCLIP_INSTANCE_ID=default \
    USER_UID=${USER_UID} \
    USER_GID=${USER_GID} \
    PAPERCLIP_CONFIG=/paperclip/instances/default/config.json \
    PAPERCLIP_DEPLOYMENT_MODE=authenticated \
    PAPERCLIP_DEPLOYMENT_EXPOSURE=private \
    PAPERCLIP_MIGRATION_AUTO_APPLY=true \
    OPENCODE_ALLOW_ALL_MODELS=true

VOLUME ["/paperclip"]

EXPOSE 3100

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["node", "--import", "./server/node_modules/tsx/dist/loader.mjs", "server/dist/index.js"]
