FROM python:3.11-slim
WORKDIR /app

# fair_agent_core.py sits one level above api/ — copy it into /app
COPY fair_agent_core.py .

# API source
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ .

ENV DATABASE_URL=sqlite:///./data/fair_studio.db
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
