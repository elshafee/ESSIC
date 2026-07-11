# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── Working directory inside the container ────────────────────────────────────
WORKDIR /app

# ── Install dependencies first (cached layer) ─────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY . .

# ── Create data folders (uploads/generated persist via volume) ────────────────
RUN mkdir -p uploads generated static

# ── Expose Flask port ─────────────────────────────────────────────────────────
EXPOSE 5000

# ── Run the app ───────────────────────────────────────────────────────────────
CMD ["python", "app.py"]
