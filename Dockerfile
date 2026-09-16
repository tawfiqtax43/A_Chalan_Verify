FROM python:3.10-slim

# প্রয়োজনীয় প্যাকেজ ও Google Chrome ইনস্টল
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    libgconf-2-4 \
    libnss3 \
    libasound2 \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
