# Steering Documentation Update - AWS EC2 Deployment

**Date:** 2026-02-17
**Update Type:** New Deployment Option Added
**Status:** ✅ Complete

## Summary

Updated steering documentation files to reflect the new AWS EC2 deployment option with comprehensive VCF file support and Docker containerization.

---

## Changes Made

### 1. New Documentation File Created

**File:** `AWS_EC2_DEPLOYMENT.md`

**Content:**

- Complete step-by-step AWS EC2 deployment guide
- Docker containerization with volume mounting for VCF files
- VCF file download instructions for all chromosomes (chr10, chr12, chr16, chr22, chr2)
- Security hardening and firewall configuration
- Cost optimization strategies (₹400-850/month)
- Monitoring and maintenance procedures
- Troubleshooting guide
- Performance optimization tips

**Key Features:**

- VCF files stored on EC2 local disk (no S3 required initially)
- Docker volume mount: `-v $(pwd)/data:/app/data`
- Auto-restart configuration: `--restart unless-stopped`
- Full production deployment with ~2GB VCF data
- Cost-effective alternative to S3 for single-instance deployments

---

### 2. Updated: `.kiro/steering/tech.md`

#### Changes

**Cloud Deployment Commands Section:**

```bash
# Added AWS EC2 deployment instructions
# AWS EC2 deployment (production with VCF support)
# See AWS_EC2_DEPLOYMENT.md for complete guide
# 1. Launch EC2 instance (t3.micro recommended)
# 2. Install Docker
# 3. Clone repository
# 4. Download VCF files to data/genomes/
# 5. Build and run Docker container with volume mount
# Access: http://<EC2_PUBLIC_IP>:8501
```

**Architecture Notes:**

- Added: "AWS EC2 deployment: Complete production deployment with Docker and VCF files stored on EC2 local storage for cost-effective full-featured deployment"
- Updated cloud platform list to include AWS EC2 explicitly

**Development Guidelines:**

- Added: "AWS EC2 Deployment: Use `AWS_EC2_DEPLOYMENT.md` for complete production deployment with VCF support"
- Updated cloud deployment references to include AWS EC2

---

### 3. Updated: `.kiro/steering/product.md`

#### Changes

**Core Functionality:**

- Updated: "Cloud Deployment Ready: Optimized for deployment to Render, Vercel, Heroku, AWS EC2, and other cloud platforms"

**Key Use Cases:**

- Updated: "Cloud-based Deployment: Scalable API deployment for production use in healthcare and pharmaceutical applications with competition-ready configurations on Render, Vercel, Heroku, and AWS EC2"
- Updated: "RESTful API deployment with FastAPI for cloud platforms (Render, Vercel, Heroku, AWS EC2)"

---

### 4. Updated: `.kiro/steering/structure.md`

#### Changes

**Directory Organization:**

```text
├── AWS_EC2_DEPLOYMENT.md     # Complete AWS EC2 deployment guide with VCF support
```

**Competition and Demo Files Section:**

- Added: `AWS_EC2_DEPLOYMENT.md` with description: "Complete AWS EC2 deployment guide with Docker containerization and VCF file storage"

---

## Deployment Options Summary

The platform now supports **four primary deployment options**:

### 1. Render.com (Competition/Demo)

- **Best for:** Quick demos, competitions
- **Cost:** Free tier available
- **Setup Time:** 5-10 minutes
- **VCF Support:** Limited (no VCF files)
- **Guide:** `RENDER_DEPLOYMENT.md`, `QUICK_DEPLOY.md`

### 2. Vercel (Serverless)

- **Best for:** Serverless deployments
- **Cost:** Free tier available
- **Setup Time:** 5-10 minutes
- **VCF Support:** Limited
- **Guide:** `vercel.json`

### 3. Heroku (Alternative)

- **Best for:** Simple deployments
- **Cost:** Paid plans
- **Setup Time:** 10-15 minutes
- **VCF Support:** Limited
- **Guide:** `Procfile`

### 4. AWS EC2 (Production) ⭐ NEW

- **Best for:** Full production with VCF support
- **Cost:** ₹400-850/month (t3.micro)
- **Setup Time:** 30-45 minutes
- **VCF Support:** ✅ Full support (all chromosomes)
- **Guide:** `AWS_EC2_DEPLOYMENT.md`
- **Features:**
  - Docker containerization
  - VCF files on local disk (2GB+)
  - Big 3 enzymes + VKORC1 + UGT1A1
  - Auto-restart on reboot
  - Production-ready monitoring

---

## Technical Details

### VCF File Storage Strategy

**AWS EC2 Approach:**

- Store VCF files directly on EC2 EBS volume
- No S3 required for single-instance deployments
- Cost-effective: ~₹200/month for 30GB storage
- Simple volume mount: `-v $(pwd)/data:/app/data`

**Chromosomes Supported:**

| Chromosome | Size | Genes | Use Case |
|------------|------|-------|----------|
| chr22 | 200MB | CYP2D6 | Codeine, Tramadol, Antidepressants |
| chr10 | 700MB | CYP2C19, CYP2C9 | Clopidogrel, Warfarin, NSAIDs |
| chr12 | 700MB | SLCO1B1 | Statin myopathy |
| chr16 | 330MB | VKORC1 | Warfarin dosing |
| chr2 | 1.2GB | UGT1A1 | Irinotecan toxicity |
| **Total** | **~3GB** | **Big 3 + extras** | **60-70% drug coverage** |

### Docker Volume Mount

**Critical Configuration:**

```bash
docker run -d \
  --name synthatrial-app \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \  # ← Volume mount for VCF files
  --restart unless-stopped \
  synthatrial:latest
```

**Why Volume Mount:**

- Container can access host filesystem
- VCF files persist across container restarts
- No need to rebuild image when updating VCF files
- Efficient storage management

---

## Cost Comparison

| Platform | Monthly Cost | VCF Support | Best For |
|----------|--------------|-------------|----------|
| Render.com | Free - ₹500 | ❌ No | Demos, API only |
| Vercel | Free - ₹1000 | ❌ No | Serverless, API |
| Heroku | ₹500 - ₹2000 | ⚠️ Limited | Simple apps |
| **AWS EC2** | **₹400 - ₹850** | **✅ Full** | **Production** |

**AWS EC2 Breakdown:**
- t3.micro instance: ₹400-600/month
- 30GB EBS storage: ₹200/month
- Data transfer: ₹50/month
- **Total: ₹650-850/month**

---

## Migration Path

### From Render/Vercel to AWS EC2

**When to migrate:**
- Need VCF file support
- Want full pharmacogenomics analysis
- Require Big 3 enzymes + VKORC1
- Need production-grade deployment

**Migration steps:**
1. Launch EC2 instance (30 minutes)
2. Download VCF files (15-30 minutes)
3. Deploy Docker container (10 minutes)
4. Test full pipeline (5 minutes)
5. Update DNS/documentation (5 minutes)

**Total migration time:** ~1-2 hours

---

## Future Enhancements

### Optional S3 Integration

**When to add S3:**
- Multiple EC2 instances
- Auto-scaling requirements
- Shared VCF storage across regions
- Backup and disaster recovery

**Benefits:**
- Centralized VCF storage
- No duplication across instances
- Easier updates and versioning
- Better for multi-region deployments

**Implementation:**
```bash
# Download VCF from S3 on container start
aws s3 sync s3://synthatrial-vcf/genomes/ /app/data/genomes/
```

---

## Documentation Consistency

All steering documentation files now consistently reference:

✅ **Four deployment options:** Render, Vercel, Heroku, AWS EC2
✅ **AWS EC2 as production option** with VCF support
✅ **Complete deployment guide** in `AWS_EC2_DEPLOYMENT.md`
✅ **Cost-effective strategy** for full-featured deployment
✅ **Volume mounting** for VCF file access

---

## Validation Checklist

- [x] Created comprehensive AWS EC2 deployment guide
- [x] Updated tech.md with AWS EC2 deployment commands
- [x] Updated tech.md architecture notes
- [x] Updated tech.md development guidelines
- [x] Updated product.md cloud deployment references
- [x] Updated product.md use cases
- [x] Updated structure.md directory listing
- [x] Updated structure.md competition files section
- [x] Verified consistency across all steering docs
- [x] Documented VCF storage strategy
- [x] Included cost analysis
- [x] Added troubleshooting guidance

---

## Impact Assessment

### Benefits

1. **Complete Production Deployment:** Full VCF support with all chromosomes
2. **Cost-Effective:** ₹650-850/month vs enterprise cloud solutions
3. **Simple Architecture:** No S3 complexity for single-instance deployments
4. **Docker Best Practices:** Volume mounting for data persistence
5. **Comprehensive Documentation:** Step-by-step guide with troubleshooting

### Considerations

1. **Setup Time:** Longer than Render/Vercel (30-45 minutes vs 5-10 minutes)
2. **Maintenance:** Requires EC2 instance management
3. **Scaling:** Single instance initially (can add load balancer later)
4. **Storage:** Limited to EC2 disk size (expandable as needed)

---

## Conclusion

The steering documentation has been successfully updated to reflect the new AWS EC2 deployment option. This provides users with a production-ready deployment path that includes full VCF support while maintaining cost-effectiveness and simplicity.

**Key Achievement:** Platform now supports both quick demo deployments (Render/Vercel) and full production deployments (AWS EC2) with comprehensive documentation for each approach.

---

**Documentation Status:** ✅ Complete and Consistent
**Next Steps:** Users can now choose deployment option based on their needs (demo vs production)
