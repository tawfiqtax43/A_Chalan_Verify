FROM python:3.10-slim

# প্রয়োজনীয় সিস্টেম প্যাকেজ ও Google Chrome ইনস্টল
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
