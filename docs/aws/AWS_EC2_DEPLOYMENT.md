# AWS EC2 Deployment Guide - Complete Setup with VCF Files

## Anukriti AI - Production Deployment on AWS EC2

This guide provides step-by-step instructions for deploying SynthaTrial on AWS EC2 with full VCF support and Docker containerization.

## 🎯 Deployment Overview

**What You'll Get:**

- Live URL: `http://<EC2_PUBLIC_IP>:8501`
- Full pharmacogenomics analysis with VCF support
- Big 3 enzymes: CYP2D6, CYP2C19, CYP2C9
- Warfarin PGx with VKORC1 support
- Docker containerized for reliability
- Auto-restart on reboot

**Cost Estimate:**

- t2.micro (Free tier): ₹0/month (first year)
- t3.micro (After free tier): ₹400-₹600/month
- Storage (20GB): ~₹150/month
- **Total: ₹400-₹750/month**

---

## 📋 Prerequisites

- AWS Account with EC2 access
- Google Gemini API key ([Get it here](https://makersuite.google.com/app/apikey))
- SSH client (Terminal on Mac/Linux, PuTTY on Windows)
- GitHub repository with SynthaTrial code

---

## 🚀 Step 1: Launch EC2 Instance

### 1.1 Create EC2 Instance

1. Go to **AWS Console** → **EC2** → **Launch Instance**

2. **Configure Instance:**
   - **Name:** `synthatrial-production`
   - **AMI:** Ubuntu 22.04 LTS (Free tier eligible)
   - **Instance Type:**
     - `t2.micro` (Free tier - 1GB RAM)
     - `t3.micro` (Recommended - 1GB RAM, better performance)
     - `t3.small` (If you need more power - 2GB RAM)

3. **Key Pair:**
   - Create new key pair: `synthatrial-key`
   - Type: RSA
   - Format: `.pem` (for Mac/Linux) or `.ppk` (for Windows/PuTTY)
   - **Download and save securely**

4. **Network Settings (CRITICAL):**
   - Create security group: `synthatrial-sg`
   - Add the following rules:

   | Type | Protocol | Port | Source | Description |
   |------|----------|------|--------|-------------|
   | SSH | TCP | 22 | My IP | SSH access |
   | Custom TCP | TCP | 8501 | 0.0.0.0/0 | Streamlit UI |
   | HTTP | TCP | 80 | 0.0.0.0/0 | Optional |

5. **Storage:**
   - **Size:** 30 GB (recommended for VCF files)
   - **Type:** gp3 (General Purpose SSD)
   - **Delete on termination:** Uncheck if you want to preserve data

6. **Launch Instance**

### 1.2 Connect to EC2

**On Mac/Linux:**

```bash
# Set correct permissions
chmod 400 synthatrial-key.pem

# Connect to EC2
ssh -i synthatrial-key.pem ubuntu@<EC2_PUBLIC_IP>
```

**On Windows (PuTTY):**
1. Convert `.pem` to `.ppk` using PuTTYgen
2. Use PuTTY with the `.ppk` key to connect

**Example:**

```bash
ssh -i synthatrial-key.pem ubuntu@13.233.45.67
```

---

## 🐳 Step 2: Install Docker

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install Docker
sudo apt install docker.io -y

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu
newgrp docker

# Verify installation
docker --version
```

**Expected output:**

```text
Docker version 24.0.x, build xxxxx
```

---

## 📦 Step 3: Clone Repository

```bash
# Install git
sudo apt install git -y

# Clone your repository
git clone https://github.com/<your-username>/SynthaTrial.git
cd SynthaTrial

# Verify files
ls -la
```

---

## 🧬 Step 4: Download VCF Files

### 4.1 Create Data Directory

```bash
# Create directory structure
mkdir -p data/genomes
cd data/genomes
```

### 4.2 Download VCF Files

**Download all required chromosomes:**

```bash
# Chromosome 22 (CYP2D6) - ~200 MB
echo "Downloading chr22 (CYP2D6)..."
curl -L -o chr22.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz

# Chromosome 10 (CYP2C19, CYP2C9) - ~700 MB
echo "Downloading chr10 (CYP2C19, CYP2C9)..."
curl -L -o chr10.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz

# Chromosome 12 (SLCO1B1) - ~700 MB
echo "Downloading chr12 (SLCO1B1)..."
curl -L -o chr12.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr12.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz

# Chromosome 16 (VKORC1) - ~330 MB
echo "Downloading chr16 (VKORC1 - Warfarin)..."
curl -L -o chr16.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr16.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz

# Chromosome 2 (UGT1A1) - ~1.2 GB (Optional)
echo "Downloading chr2 (UGT1A1)..."
curl -L -o chr2.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr2.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz
```

**Note:** Downloads will take 15-30 minutes depending on connection speed.

### 4.3 Verify Downloads

```bash
# Check file sizes
ls -lh

# Expected output:
# -rw-r--r-- 1 ubuntu ubuntu 200M chr22.vcf.gz
# -rw-r--r-- 1 ubuntu ubuntu 700M chr10.vcf.gz
# -rw-r--r-- 1 ubuntu ubuntu 700M chr12.vcf.gz
# -rw-r--r-- 1 ubuntu ubuntu 330M chr16.vcf.gz
# -rw-r--r-- 1 ubuntu ubuntu 1.2G chr2.vcf.gz

# Return to project root
cd ../..
```

---

## 🔐 Step 5: Configure Environment

```bash
# Create .env file
nano .env
```

**Add the following configuration:**

```bash
# Required: Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: Vector DB for drug similarity search
# Recommended: OpenSearch Serverless
VECTOR_DB_BACKEND=opensearch
OPENSEARCH_HOST=your-collection-id.us-east-1.aoss.amazonaws.com
OPENSEARCH_INDEX=drug-index
OPENSEARCH_REGION=us-east-1
OPENSEARCH_SERVICE=aoss

# Alternative: Pinecone
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_INDEX=drug-index

# Optional: Environment settings
ENVIRONMENT=production
DEBUG=false
PORT=8501

# Model configuration
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.7
```

**Save:** `CTRL+X` → `Y` → `Enter`

---

## 🚀 Step 6 (Recommended): Run with Docker Compose (Backend + Frontend)

This uses the `docker-compose.yml` in the repository to run:

- `backend` (FastAPI) on port `8000`
- `frontend` (Streamlit) on port `8501`

The frontend talks to the backend via `API_URL=http://backend:8000` inside the Docker network.

```bash
cd ~/SynthaTrial

# First time (or after code changes)
docker-compose up -d --build

# Check status
docker-compose ps
```

Example output:

```text
NAME                   IMAGE                  COMMAND                  SERVICE    CREATED          STATUS                             PORTS
synthatrial-backend    synthatrial-backend    "conda run -n syntha…"   backend    1 minute ago     Up 1 minute (healthy)              0.0.0.0:8000->8000/tcp
synthatrial-frontend   synthatrial-frontend   "conda run -n syntha…"   frontend   1 minute ago     Up 1 minute (healthy)              0.0.0.0:8501->8501/tcp
```

To see logs:

```bash
docker-compose logs -f
```

To stop everything:

```bash
docker-compose down
```

If you previously used the single-container setup and see name conflicts, use:

```bash
docker-compose down --remove-orphans
docker rm -f synthatrial-app || true
docker-compose up -d --build
```

---

## 🐋 Step 6: Build Docker Image

### 6.1 Verify Dockerfile

```bash
# Check if Dockerfile exists
cat Dockerfile
```

**If Dockerfile doesn't exist or needs updating, create it:**

```bash
nano Dockerfile
```

**Dockerfile content:**

```dockerfile
FROM continuumio/miniconda3

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install RDKit via conda (required)
RUN conda install -c conda-forge rdkit python=3.10 pandas scipy scikit-learn -y

# Install other dependencies via pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data/genomes

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

### 6.2 Build Image

```bash
# Build Docker image (takes 5-10 minutes first time)
docker build -t synthatrial:latest .

# Verify image
docker images | grep synthatrial
```

---

## 🚀 Step 7: Run Container

### 7.1 Start Container with VCF Volume Mount

```bash
# Run container with volume mount for VCF files
docker run -d \
  --name synthatrial-app \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  synthatrial:latest

# Check if container is running
docker ps
```

**Expected output:**

```text
CONTAINER ID   IMAGE                COMMAND                  STATUS         PORTS
abc123def456   synthatrial:latest   "streamlit run app.p…"   Up 10 seconds  0.0.0.0:8501->8501/tcp
```

### 7.2 Check Logs

```bash
# View container logs
docker logs synthatrial-app

# Follow logs in real-time
docker logs -f synthatrial-app
```

**Look for:**

```text
You can now view your Streamlit app in your browser.
Network URL: http://0.0.0.0:8501
```

---

## 🧪 Step 8: Verify VCF Files in Container

```bash
# Enter container
docker exec -it synthatrial-app bash

# Check VCF files
ls -lh /app/data/genomes/

# Expected output:
# chr10.vcf.gz
# chr12.vcf.gz
# chr16.vcf.gz
# chr22.vcf.gz
# chr2.vcf.gz

# Test VCF processing
python main.py --vcf data/genomes/chr22.vcf.gz --sample-id HG00096 --drug-name Codeine

# Exit container
exit
```

---

## 🌐 Step 9: Access Application

### 9.1 Get Public IP

```bash
# Get EC2 public IP
curl http://checkip.amazonaws.com
```

### 9.2 Open in Browser

Navigate to:

```text
http://<EC2_PUBLIC_IP>:8501
```

**Example:**

```text
http://13.233.45.67:8501
```

### 9.3 Test Full Pipeline

1. **Select Drug:** Warfarin
2. **Patient Profile:**
   - CYP2C9: Poor Metabolizer
   - VKORC1: Variant carrier
3. **Run Analysis**
4. **Verify Results:** Should show Warfarin PGx with VKORC1 analysis

---

## 🔄 Step 10: Container Management

### 10.1 Basic Commands

```bash
# Stop container
docker stop synthatrial-app

# Start container
docker start synthatrial-app

# Restart container
docker restart synthatrial-app

# View logs
docker logs synthatrial-app

# View resource usage
docker stats synthatrial-app
```

### 10.2 Update Application

```bash
# Pull latest code
cd ~/SynthaTrial
git pull origin main

# Rebuild image
docker build -t synthatrial:latest .

# Stop and remove old container
docker stop synthatrial-app
docker rm synthatrial-app

# Start new container
docker run -d \
  --name synthatrial-app \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  synthatrial:latest
```

---

## 🛡️ Step 11: Security Hardening

### 11.1 Update Security Group

**Restrict SSH access to your IP only:**

1. Go to **EC2** → **Security Groups** → `synthatrial-sg`
2. Edit inbound rules for SSH (port 22)
3. Change source from `0.0.0.0/0` to `My IP`

### 11.2 Enable Firewall

```bash
# Install and configure UFW
sudo apt install ufw -y

# Allow SSH
sudo ufw allow 22/tcp

# Allow Streamlit
sudo ufw allow 8501/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 11.3 Set Up Automatic Updates

```bash
# Install unattended-upgrades
sudo apt install unattended-upgrades -y

# Enable automatic security updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 📊 Step 12: Monitoring and Maintenance

### 12.1 Set Up CloudWatch (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
```

### 12.2 Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check VCF directory size
du -sh data/genomes/

# Clean up Docker
docker system prune -a
```

### 12.3 Create Backup Script

```bash
# Create backup script
nano ~/backup.sh
```

**Backup script content:**

```bash
#!/bin/bash
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup .env file
cp ~/SynthaTrial/.env $BACKUP_DIR/.env_$DATE

# Backup analysis history (if any)
if [ -d ~/SynthaTrial/analysis_history ]; then
    tar -czf $BACKUP_DIR/analysis_history_$DATE.tar.gz ~/SynthaTrial/analysis_history
fi

# Keep only last 7 backups
ls -t $BACKUP_DIR/*.tar.gz | tail -n +8 | xargs rm -f

echo "Backup completed: $DATE"
```

```bash
# Make executable
chmod +x ~/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add line: 0 2 * * * /home/ubuntu/backup.sh
```

---

## 🚨 Troubleshooting

### Issue 1: Container Won't Start

```bash
# Check logs
docker logs synthatrial-app

# Common fixes:
# 1. Check .env file exists
ls -la .env

# 2. Verify port is not in use
sudo netstat -tulpn | grep 8501

# 3. Check Docker service
sudo systemctl status docker
```

### Issue 2: VCF Files Not Found

```bash
# Verify volume mount
docker inspect synthatrial-app | grep -A 10 Mounts

# Check files in container
docker exec synthatrial-app ls -la /app/data/genomes/

# Recreate container with correct mount
docker stop synthatrial-app
docker rm synthatrial-app
docker run -d \
  --name synthatrial-app \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  synthatrial:latest
```

### Issue 3: Out of Memory

```bash
# Check memory usage
free -h

# Check Docker stats
docker stats synthatrial-app

# Solution: Upgrade to t3.small (2GB RAM)
```

### Issue 4: Slow VCF Processing

```bash
# Check if VCF files are corrupted
gunzip -t data/genomes/chr22.vcf.gz

# Re-download if needed
cd data/genomes
rm chr22.vcf.gz
curl -L -o chr22.vcf.gz <URL>
```

---

## 🎯 Performance Optimization

### 1. Use Elastic IP (Recommended)

**Why:** Prevents IP change on instance restart

```text
# In AWS Console:
# 1. Go to EC2 → Elastic IPs
# 2. Allocate new Elastic IP
# 3. Associate with your instance
```

### 2. Enable Swap (For t2.micro)

```bash
# Create 2GB swap file
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. Optimize Docker

```bash
# Limit container resources
docker update --memory="800m" --cpus="0.8" synthatrial-app
```

---

## 💰 Cost Optimization

### Monthly Cost Breakdown

| Item | Cost (INR) |
|------|------------|
| t3.micro instance | ₹400-600 |
| 30GB EBS storage | ₹200 |
| Data transfer (minimal) | ₹50 |
| **Total** | **₹650-850/month** |

### Cost Saving Tips

1. **Use Reserved Instances:** Save 30-40% with 1-year commitment
2. **Stop instance when not in use:** Pay only for storage
3. **Use Spot Instances:** Save up to 70% (for non-critical workloads)
4. **Optimize storage:** Delete old Docker images regularly

---

## 🔄 Next Steps

### Optional Enhancements

1. **Add Domain Name:**
   - Register domain on Route 53
   - Point to Elastic IP
   - Access via `https://synthatrial.yourdomain.com`

2. **Enable HTTPS:**
   - Install Nginx reverse proxy
   - Get free SSL from Let's Encrypt
   - Configure automatic renewal

3. **Add S3 Integration:**
   - Store VCF files in S3
   - Download on-demand
   - Share across multiple instances

4. **Set Up Load Balancer:**
   - Handle multiple users
   - Auto-scaling
   - High availability

---

## 📝 Quick Reference Commands

```bash
# SSH to EC2
ssh -i synthatrial-key.pem ubuntu@<EC2_IP>

# Check container status
docker ps

# View logs
docker logs -f synthatrial-app

# Restart container
docker restart synthatrial-app

# Update application
cd ~/SynthaTrial && git pull && docker build -t synthatrial:latest . && docker restart synthatrial-app

# Check disk space
df -h

# Monitor resources
docker stats synthatrial-app
```

---

## ✅ Deployment Checklist

- [ ] EC2 instance launched with correct security group
- [ ] SSH access working
- [ ] Docker installed and running
- [ ] Repository cloned
- [ ] VCF files downloaded (chr10, chr12, chr16, chr22)
- [ ] .env file configured with API keys
- [ ] Docker image built successfully
- [ ] Container running with volume mount
- [ ] VCF files accessible in container
- [ ] Application accessible via browser
- [ ] Warfarin PGx test successful
- [ ] Auto-restart enabled
- [ ] Security hardening completed
- [ ] Backup script configured

---

## 🆘 Support

**Common Issues:**

- Check logs: `docker logs synthatrial-app`
- Verify VCF files: `docker exec synthatrial-app ls /app/data/genomes/`
- Test API key: Check .env file
- Memory issues: Upgrade to t3.small

**Resources:**

- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [Docker Documentation](https://docs.docker.com/)
- [SynthaTrial GitHub](https://github.com/your-repo/SynthaTrial)

---

## Deployment Complete

Your SynthaTrial platform is now live on AWS EC2 with full VCF support and production-ready configuration. 🎉
