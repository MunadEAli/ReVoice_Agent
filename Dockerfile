FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY services/ ./services/
COPY packages/ ./packages/
COPY data/ ./data/
COPY evals/ ./evals/
COPY conftest.py .

# Build and copy frontend static files
COPY apps/web/dist/ ./services/api/static/

# Environment defaults (override at runtime)
ENV USE_MOCK_QWEN=true
ENV DATABASE_URL=sqlite:///./revoice.db

# Seed the persona on first run
RUN python data/demo_persona/seed.py || true

EXPOSE 8000

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
