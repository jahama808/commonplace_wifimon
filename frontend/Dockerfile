# syntax=docker/dockerfile:1.7
#
# Three-stage build:
#   1. deps   — install node_modules
#   2. build  — compile Next standalone bundle
#   3. runner — minimal runtime, copies the standalone output
#
# At runtime, set:
#   API_BASE_URL=http://web:8000   (compose service name for the FastAPI tier)

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --silent --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Run as a non-root user (node image already provides one)
RUN addgroup -S app && adduser -S app -G app

# Standalone output bundles its own minimal node_modules
COPY --from=build --chown=app:app /app/public ./public
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static

USER app
EXPOSE 3000

CMD ["node", "server.js"]
