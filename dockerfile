FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    speedtest-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Ookla Speedtest CLI
RUN curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
    && apt-get install speedtest

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
COPY network_monitor.py .

# Run the script
CMD ["python", "network_monitor.py"]