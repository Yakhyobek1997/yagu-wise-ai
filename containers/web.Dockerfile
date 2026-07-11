# Auralynq web UI image (Next.js). Build context is ./web.
FROM docker.io/library/node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM docker.io/library/node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* vars are inlined into the client bundle at build time, so the
# API base must be known here. Override per-deployment, e.g. for a remote server:
#   --build-arg NEXT_PUBLIC_API_BASE=http://<server-ip>:8000
ARG NEXT_PUBLIC_API_BASE=/api
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM docker.io/library/node:20-alpine AS runner
WORKDIR /app
LABEL org.opencontainers.image.title="auralynq-web" \
      org.opencontainers.image.description="Auralynq web UI (Next.js) — chat, voice, trace, evidence" \
      org.opencontainers.image.source="https://github.com/MHHamdan/Auralynq" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 10001 web && adduser -u 10001 -G web -S web
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
USER web
EXPOSE 3000
CMD ["npm", "start"]
