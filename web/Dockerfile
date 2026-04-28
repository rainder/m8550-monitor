# --- deps stage: install Node deps including native compile of better-sqlite3
FROM node:22-alpine AS deps
WORKDIR /app

# Build tools required by better-sqlite3's prebuild + node-gyp fallback.
RUN apk add --no-cache python3 make g++ sqlite-dev

RUN corepack enable

# pnpm 10 needs the workspace file present for onlyBuiltDependencies to apply.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN pnpm install --frozen-lockfile

# --- build stage: produce the .next standalone output
FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# --- runtime stage: minimal Node runtime
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Standalone output bundles only what the server needs, plus a runtime
# node_modules with native bindings already in place.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
