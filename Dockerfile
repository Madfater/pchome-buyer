# ---- 前端建置 ----
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 後端執行環境 ----
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Taipei

WORKDIR /app

# 依賴層（pyproject/uv.lock 沒變就不重跑）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Chromium 與系統依賴（版本跟隨 uv.lock 的 playwright）
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && /app/.venv/bin/playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY main.py ./
COPY pchome/ pchome/
COPY --from=frontend /frontend/dist frontend/dist

# 執行期資料（登入 session、商品清單、結帳紀錄）導到 /data volume
RUN mkdir -p /data \
    && ln -s /data/auth_state.json /app/auth_state.json \
    && ln -s /data/products.json /app/products.json \
    && ln -s /data/checkouts.json /app/checkouts.json

EXPOSE 8787
CMD ["/app/.venv/bin/python", "main.py", "--host", "0.0.0.0"]
