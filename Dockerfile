FROM python:3.12-slim-bookworm

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY src src

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "civ_api", "--http", "--host", "0.0.0.0", "--port", "8000"]