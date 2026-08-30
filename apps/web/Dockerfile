# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- build ----
FROM node:20-alpine AS build

WORKDIR /app

# Copy manifests first so the dependency layer caches across source changes.
COPY package.json package-lock.json* ./
# `npm ci` installs exactly the lockfile — `npm install` would mutate it and
# make the build non-reproducible.
RUN npm ci

COPY . .

# VITE_* values are inlined into the bundle at build time. They are PUBLIC —
# never pass a secret here.
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_ADK_APP_NAME=kaiops
ARG VITE_GRAFANA_URL=
ARG VITE_ARGOCD_URL=
ARG VITE_GITHUB_URL=https://github.com
ARG VITE_ENVIRONMENT=production
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ADK_APP_NAME=$VITE_ADK_APP_NAME \
    VITE_GRAFANA_URL=$VITE_GRAFANA_URL \
    VITE_ARGOCD_URL=$VITE_ARGOCD_URL \
    VITE_GITHUB_URL=$VITE_GITHUB_URL \
    VITE_ENVIRONMENT=$VITE_ENVIRONMENT

RUN npm run build

# --------------------------------------------------------------- runtime ---
# nginx-unprivileged so the container runs as a non-root user. Stock nginx
# needs root to bind :80, which is why the previous build had to set
# runAsNonRoot: false.
FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root
RUN apk add --no-cache gettext \
 && rm -f /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.d/kaiops-entrypoint.sh
RUN chmod +x /docker-entrypoint.d/kaiops-entrypoint.sh \
 && chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d

USER nginx

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider "http://127.0.0.1:${PORT}/" || exit 1

ENTRYPOINT ["/docker-entrypoint.d/kaiops-entrypoint.sh"]
