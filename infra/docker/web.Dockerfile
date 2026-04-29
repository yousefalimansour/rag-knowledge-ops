FROM node:20-alpine AS deps

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /srv

# Copy workspace manifests first for layer cache.
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json

RUN pnpm install --filter @kops/web... --no-frozen-lockfile


FROM node:20-alpine AS dev

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /srv

COPY --from=deps /srv/node_modules ./node_modules
COPY --from=deps /srv/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-workspace.yaml ./
COPY apps/web ./apps/web

WORKDIR /srv/apps/web
EXPOSE 7000
CMD ["pnpm", "dev", "--port", "7000", "--hostname", "0.0.0.0"]
