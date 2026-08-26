# CashGuard AI — backend container
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts
COPY run.py .

EXPOSE 8000

# Generate data + train on first boot, then serve.
CMD ["python", "run.py", "--demo"]