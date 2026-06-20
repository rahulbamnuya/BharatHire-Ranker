# Use a lightweight official Python runtime as a parent image
FROM python:3.9-slim

# Set system environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/user/.local/bin:$PATH"

# Create a non-root user with UID 1000 for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user
USER user

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY --chown=user requirements.txt .

# Install Python packages
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=user . .

# Expose port 7860 (Hugging Face Spaces default port)
EXPOSE 7860

# Add healthcheck to verify Streamlit container is healthy
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/_stcore/health', timeout=5).read()" || exit 1

# Default command launches the Streamlit Dashboard
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
