FROM python:3.10-slim

WORKDIR /app

# প্রয়োজনীয় সিস্টেম ডিপেন্ডেন্সি ইনস্টল
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright-এর ব্রাউজার ও সিস্টেম ডিপেন্ডেন্সি ইনস্টল
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
