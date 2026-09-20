# Deka - Frontend (Vite + React)
# Stage 1: build static assets
FROM node:24.21.0-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build với baseURL rỗng -> axios dùng URL tương đối, nginx proxy /api tới backend.
# Process env ghi đè .env của Vite, nên đặt trống để chắc chắn.
ENV VITE_API_BASE_URL=""
ARG VITE_MAX_UPLOAD_SIZE_BYTES=20971520
ENV VITE_MAX_UPLOAD_SIZE_BYTES=${VITE_MAX_UPLOAD_SIZE_BYTES}
ARG VITE_ENABLE_DEMO_LOGIN=false
ENV VITE_ENABLE_DEMO_LOGIN=${VITE_ENABLE_DEMO_LOGIN}
RUN npm run build

# Stage 2: serve bằng nginx
FROM nginx:1.30.4-alpine
RUN apk upgrade --no-cache \
    && sed -i "s/worker_processes  auto;/worker_processes  2;/" /etc/nginx/nginx.conf

# Copy build output
COPY --from=build /app/dist /usr/share/nginx/html

# Cấu hình nginx (SPA fallback + proxy /api)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
