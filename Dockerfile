# Use lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (important for torch + faiss)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install numpy==1.26.4
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Streamlit runs on 8501
EXPOSE 8501

# Required for Azure Container Apps
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
