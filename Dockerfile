FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]"
EXPOSE 8000
CMD ["python", "-m", "governance"]
