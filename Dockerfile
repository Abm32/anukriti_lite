# Anukriti - In Silico Pharmacogenomics Platform
# Multi-stage Docker build for production deployment

# Stage 1: Base image with conda and system dependencies
FROM continuumio/miniconda3:latest as base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CONDA_ENV_NAME=anukriti

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create conda environment with Python 3.10
RUN conda create -n $CONDA_ENV_NAME python=3.10 -y

# Activate conda environment for subsequent commands
SHELL ["conda", "run", "-n", "anukriti", "/bin/bash", "-c"]

# Install RDKit, htslib (tabix for region-indexed VCF), and scientific packages via conda
RUN conda install -n $CONDA_ENV_NAME -c bioconda -c conda-forge \
    rdkit \
    htslib \
    pandas \
    scipy \
    scikit-learn \
    numpy \
    -y

# Stage 2: Application dependencies
FROM base as dependencies

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies via pip
RUN conda run -n $CONDA_ENV_NAME pip install --no-cache-dir -r requirements.txt

# Stage 3: Application code
FROM dependencies as application

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/genomes data/chembl logs

# Set proper permissions
RUN chmod +x scripts/*.py

# Create non-root user for security
RUN useradd -m -u 1000 anukriti && \
    chown -R anukriti:anukriti /app
USER anukriti

# Stage 4: Production image
FROM application as production

# Expose ports
EXPOSE 8501 8000

# Health check is defined per-service in docker-compose.yml
# (backend uses /health on 8000, frontend uses /_stcore/health on 8501)

# Default command (can be overridden)
CMD ["conda", "run", "-n", "anukriti", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
