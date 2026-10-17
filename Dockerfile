FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/app /app/backend/app
COPY --from=frontend-build /frontend/dist /app/frontend/dist
ENV PYTHONPATH=/app/backend
ENV DATABASE_PATH=/data/request-lens.sqlite3
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]