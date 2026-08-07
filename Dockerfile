FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY data ./data
COPY strategy ./strategy
COPY risk ./risk
COPY execution ./execution
COPY monitoring ./monitoring
COPY main.py ./

RUN pip install --no-cache-dir .

CMD ["python", "main.py"]
