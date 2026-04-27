# AWS Services Recommendations for SynthaTrial

## Executive Summary

This document provides a comprehensive guide to AWS services that can enhance the SynthaTrial pharmacogenomics platform. The recommendations are organized by priority, cost, and use case to help you make informed decisions about cloud infrastructure.

**Current Status**: v0.4 Beta
**Current AWS Integration**: Bedrock (LLM), EC2 (deployment)
**Date**: 2026-03-04

---

## Currently Integrated AWS Services

### 1. AWS Bedrock ✅ (Implemented)
- **Purpose**: Alternative LLM backend
- **Components**:
  - Claude 3 Haiku for pharmacogenomics analysis
  - Titan Embeddings for vector similarity search
- **Status**: Fully integrated with per-request backend selection
- **Cost**: Pay per token (~₹100-500/month depending on usage)
- **Configuration**: Set `LLM_BACKEND=bedrock` in `.env`

### 2. AWS EC2 ✅ (Documented)
- **Purpose**: Cost-effective application hosting
- **Instance Types**:
  - t2.micro (FREE for 12 months)
  - t3.micro (₹400-750/month)
- **Features**:
  - Full VCF file support with local storage
  - Docker containerization
  - Complete deployment guide in `AWS_EC2_DEPLOYMENT.md`
- **Status**: Production-ready
- **Cost**: ₹0-750/month (most economical option)

---

## Recommended AWS Services by Priority

### 🔥 High Priority (Immediate Value)

#### 3. Amazon S3 - Object Storage
**Use Case**: Store large VCF files and genomic data

**Benefits**:
- Scalable storage for multi-chromosome VCF files (currently 8 chromosomes)
- Versioning for data integrity
- Lifecycle policies to automatically move old data to cheaper storage
- Durability: 99.999999999% (11 9's)
- Integration with other AWS services

**Implementation**:
```python
# Replace local file storage
import boto3

s3 = boto3.client('s3')
s3.download_file('synthatrial-vcf', 'chr22.vcf.gz', 'data/genomes/chr22.vcf.gz')
```

**Cost Estimate**: ₹200-400/month
- Storage: ~100GB VCF files @ ₹2/GB/month = ₹200
- Data transfer: ~50GB/month @ ₹4/GB = ₹200
- Total: ~₹400/month

**Priority**: High - Enables scalability and better data management

---

#### 4. Amazon RDS (PostgreSQL) - Managed Database
**Use Case**: Replace SQLite for ChEMBL database

**Benefits**:
- Better performance for concurrent queries
- Automated backups (point-in-time recovery)
- Multi-AZ deployment for high availability
- Read replicas for scaling
- Managed updates and patches

**Implementation**:
```python
# Update database connection
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('RDS_HOST'),
    database='chembl',
    user=os.getenv('RDS_USER'),
    password=os.getenv('RDS_PASSWORD')
)
```

**Cost Estimate**: ₹800-1500/month
- db.t3.micro: ₹800/month
- Storage: 100GB @ ₹5/GB = ₹500
- Backups: ₹200/month
- Total: ~₹1500/month

**Priority**: High - Essential for production scalability

---

#### 5. AWS Lambda + API Gateway - Serverless API
**Use Case**: Serverless deployment alternative to EC2

**Benefits**:
- Pay per request (cost-effective for low traffic)
- Auto-scaling (0 to thousands of requests)
- No server management
- Built-in high availability
- Integration with other AWS services

**Implementation**:
```python
# Lambda handler for FastAPI
from mangum import Mangum
from api import app

handler = Mangum(app)
```

**Cost Estimate**: ₹100-500/month
- Lambda: 1M requests @ ₹0.20/1M = ₹0.20
- Compute: 100GB-seconds @ ₹0.0000166667/GB-second = ₹100
- API Gateway: 1M requests @ ₹3.50/1M = ₹350
- Total: ~₹450/month

**Priority**: Medium-High - Good for variable traffic

---

#### 6. Amazon CloudFront - CDN
**Use Case**: Serve Streamlit UI and static assets globally

**Benefits**:
- Faster global access (edge locations worldwide)
- Reduced latency for 3D molecular visualization
- HTTPS by default (free SSL certificates)
- DDoS protection
- Reduced load on origin server

**Implementation**:
```yaml
# CloudFront distribution
Origins:
  - DomainName: synthatrial.example.com
    CustomOriginConfig:
      HTTPPort: 8501
      OriginProtocolPolicy: http-only
```

**Cost Estimate**: ₹50-200/month
- Data transfer: 50GB @ ₹3/GB = ₹150
- Requests: 1M @ ₹0.01/10K = ₹100
- Total: ~₹250/month (first 50GB free)

**Priority**: Medium - Improves user experience

---

### 💡 Medium Priority (Enhanced Features)

#### 7. Amazon SageMaker - Machine Learning
**Use Case**: Train custom ML models for drug response prediction

**Benefits**:
- Jupyter notebooks for research
- Model training and deployment
- Feature engineering for pharmacogenomics
- AutoML capabilities
- Model monitoring and drift detection

**Implementation**:
```python
# Train custom model
import sagemaker
from sagemaker.sklearn import SKLearn

estimator = SKLearn(
    entry_point='train.py',
    instance_type='ml.m5.large',
    framework_version='1.0-1'
)
estimator.fit({'training': 's3://synthatrial/training-data'})
```

**Cost Estimate**: ₹1000-3000/month
- Training: ml.m5.large @ ₹50/hour × 20 hours = ₹1000
- Inference: ml.t3.medium @ ₹30/hour × 24×30 = ₹21,600 (use serverless inference instead)
- Serverless inference: ₹500-1000/month
- Total: ~₹1500-2000/month

**Priority**: Medium - Enhances AI capabilities

---

#### 8. AWS Batch - Batch Processing
**Use Case**: Process large patient cohorts in batch mode

**Benefits**:
- Parallel VCF processing across multiple chromosomes
- Cost-effective for batch jobs (spot instances)
- Automatic scaling based on queue depth
- Job scheduling and dependencies
- Integration with S3 and Lambda

**Implementation**:
```python
# Submit batch job
import boto3

batch = boto3.client('batch')
response = batch.submit_job(
    jobName='vcf-processing',
    jobQueue='synthatrial-queue',
    jobDefinition='vcf-processor',
    parameters={
        'vcf_file': 's3://synthatrial-vcf/chr22.vcf.gz',
        'sample_id': 'HG00096'
    }
)
```

**Cost Estimate**: ₹500-1500/month
- Compute: Spot instances @ 70% discount
- 100 hours/month @ ₹5/hour = ₹500
- Total: ~₹500-1000/month

**Priority**: Medium - Enhances batch processing feature

---

#### 9. Amazon ElastiCache (Redis) - Caching
**Use Case**: Cache drug fingerprints and similarity search results

**Benefits**:
- Faster response times (sub-millisecond latency)
- Reduce Pinecone API calls (cost savings)
- Session management for Streamlit
- Pub/sub for real-time updates
- Automatic failover

**Implementation**:
```python
# Cache drug fingerprints
import redis

cache = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=6379,
    decode_responses=True
)

# Cache fingerprint
cache.setex(f'fp:{smiles}', 3600, json.dumps(fingerprint))
```

**Cost Estimate**: ₹500-1000/month
- cache.t3.micro: ₹500/month
- Data transfer: ₹200/month
- Total: ~₹700/month

**Priority**: Medium - Improves performance

---

#### 10. Amazon DynamoDB - NoSQL Database
**Use Case**: Store patient profiles and analysis history

**Benefits**:
- Serverless NoSQL database
- Fast key-value lookups (single-digit millisecond)
- Auto-scaling (pay per request)
- Global tables for multi-region
- Point-in-time recovery

**Implementation**:
```python
# Store analysis results
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('synthatrial-analyses')

table.put_item(
    Item={
        'patient_id': 'PT-12345',
        'timestamp': '2026-03-04T10:00:00Z',
        'drug_name': 'Warfarin',
        'risk_level': 'Medium',
        'analysis_result': {...}
    }
)
```

**Cost Estimate**: ₹200-600/month
- On-demand: 1M writes @ ₹1.25/1M = ₹125
- 10M reads @ ₹0.25/1M = ₹250
- Storage: 10GB @ ₹25/GB = ₹250
- Total: ~₹625/month

**Priority**: Medium - Enables user history

---

### 🚀 Advanced (Production Scale)

#### 11. Amazon ECS/Fargate - Container Orchestration
**Use Case**: Managed container service (alternative to EC2)

**Benefits**:
- Managed container orchestration
- Auto-scaling based on metrics
- Load balancing
- Service discovery
- Integration with CloudWatch

**Cost Estimate**: ₹1500-3000/month
- Fargate: 0.5 vCPU, 1GB RAM @ ₹2/hour × 24×30 = ₹1440
- Load balancer: ₹750/month
- Total: ~₹2190/month

**Priority**: Low - More expensive than EC2

**Note**: Only use if you need advanced orchestration features

---

#### 12. AWS Step Functions - Workflow Orchestration
**Use Case**: Orchestrate multi-step analysis workflows

**Benefits**:
- Visual workflow designer
- Error handling and retries
- Coordinate VCF → Analysis → Report generation
- Integration with Lambda, Batch, SageMaker
- Audit trail

**Implementation**:
```json
{
  "StartAt": "ProcessVCF",
  "States": {
    "ProcessVCF": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:process-vcf",
      "Next": "RunAnalysis"
    },
    "RunAnalysis": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:run-analysis",
      "Next": "GenerateReport"
    },
    "GenerateReport": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:generate-report",
      "End": true
    }
  }
}
```

**Cost Estimate**: ₹50-200/month
- State transitions: 10K/month @ ₹25/1M = ₹0.25
- Total: ~₹50-100/month

**Priority**: Low - Nice to have for complex workflows

---

#### 13. Amazon Comprehend Medical - Medical NLP
**Use Case**: Extract medical insights from clinical text

**Benefits**:
- NLP for medical documents
- Extract drug names, conditions, dosages
- HIPAA compliant
- Pre-trained medical models
- Entity recognition

**Cost Estimate**: Pay per request
- ₹0.01 per 100 characters
- 1M characters/month = ₹100

**Priority**: Low - Optional enhancement

---

### 📊 Monitoring & Security

#### 14. Amazon CloudWatch - Monitoring
**Use Case**: Application monitoring and logging

**Benefits**:
- Application metrics (CPU, memory, custom)
- Log aggregation from all services
- Alarms and notifications
- Dashboards
- Integration with all AWS services

**Implementation**:
```python
# Custom metrics
import boto3

cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='SynthaTrial',
    MetricData=[{
        'MetricName': 'AnalysisTime',
        'Value': 1.5,
        'Unit': 'Seconds'
    }]
)
```

**Cost Estimate**: ₹100-300/month
- Metrics: 10 custom metrics @ ₹30/metric = ₹300
- Logs: 10GB @ ₹5/GB = ₹50
- Alarms: 10 alarms @ ₹10/alarm = ₹100
- Total: ~₹450/month (first 10 metrics free)

**Priority**: High - Essential for production

---

#### 15. AWS Secrets Manager - Secrets Management
**Use Case**: Secure API key storage

**Benefits**:
- Encrypted secrets (KMS)
- Automatic rotation
- Audit trail (CloudTrail)
- Fine-grained access control
- Integration with RDS, Lambda, etc.

**Implementation**:
```python
# Retrieve secrets
import boto3
import json

secrets = boto3.client('secretsmanager')
response = secrets.get_secret_value(SecretId='synthatrial/api-keys')
api_keys = json.loads(response['SecretString'])
```

**Cost Estimate**: ₹40-120/month
- Secrets: 3 secrets @ ₹40/secret = ₹120
- API calls: 10K @ ₹0.05/10K = ₹5
- Total: ~₹125/month

**Priority**: High - Security best practice

---

#### 16. AWS Certificate Manager (ACM) - SSL Certificates
**Use Case**: Free SSL/TLS certificates

**Benefits**:
- FREE SSL certificates
- Automatic renewal
- Easy integration with CloudFront, ALB, API Gateway
- Wildcard certificates
- No management overhead

**Cost**: **FREE** ✅

**Priority**: High - Essential for HTTPS

---

#### 17. AWS WAF - Web Application Firewall
**Use Case**: Protect API from attacks

**Benefits**:
- DDoS protection
- Rate limiting
- IP filtering
- SQL injection protection
- Bot detection

**Cost Estimate**: ₹500-1000/month
- Web ACL: ₹500/month
- Rules: 5 rules @ ₹100/rule = ₹500
- Requests: 10M @ ₹0.60/1M = ₹600
- Total: ~₹1600/month

**Priority**: Medium - Important for public APIs

---

### 🧬 Specialized for Genomics

#### 18. AWS HealthOmics - Genomics Platform
**Use Case**: Purpose-built genomics data storage and analysis

**Benefits**:
- Optimized for VCF files
- Variant calling pipelines
- Annotation workflows
- HIPAA and GDPR compliant
- Integration with S3 and Batch

**Cost**: Variable (new service, pricing evolving)

**Priority**: Low - Evaluate when mature

---

#### 19. Amazon Neptune - Graph Database
**Use Case**: Model drug-gene interaction networks

**Benefits**:
- Graph database for complex relationships
- Query drug interaction networks
- Visualize pathways
- SPARQL and Gremlin support
- High availability

**Cost Estimate**: ₹1500-2500/month
- db.t3.medium: ₹1500/month
- Storage: 100GB @ ₹10/GB = ₹1000
- Total: ~₹2500/month

**Priority**: Low - Advanced feature

---

## Cost-Optimized Architecture Recommendations

### Tier 1: Minimal (₹1000-2000/month)

**Target**: Small-scale deployment, low traffic

```
✅ EC2 t3.micro (₹400-750/month) - Application
✅ S3 (₹200-400/month) - VCF storage
✅ CloudWatch (₹100-300/month) - Monitoring
✅ ACM (FREE) - SSL certificates
✅ Secrets Manager (₹120/month) - API keys

Total: ~₹820-1570/month
```

**Best For**: Development, testing, small user base

---

### Tier 2: Standard (₹3000-5000/month)

**Target**: Production deployment, moderate traffic

```
✅ EC2 t3.small (₹800-1500/month) - Application
✅ S3 (₹200-400/month) - VCF storage
✅ RDS PostgreSQL (₹800-1500/month) - Database
✅ ElastiCache Redis (₹500-1000/month) - Caching
✅ CloudFront (₹50-200/month) - CDN
✅ CloudWatch (₹100-300/month) - Monitoring
✅ ACM (FREE) - SSL
✅ Secrets Manager (₹120/month) - Secrets

Total: ~₹3570-5020/month
```

**Best For**: Production, growing user base, better performance

---

### Tier 3: Advanced (₹8000-12000/month)

**Target**: High traffic, advanced features

```
✅ ECS Fargate (₹1500-3000/month) - Containers
✅ S3 (₹400-800/month) - Storage
✅ RDS PostgreSQL (₹1500-2500/month) - Database (Multi-AZ)
✅ ElastiCache Redis (₹1000-2000/month) - Caching (cluster)
✅ CloudFront (₹200-500/month) - CDN
✅ Lambda (₹500-1000/month) - Serverless functions
✅ DynamoDB (₹200-600/month) - User data
✅ SageMaker (₹1000-2000/month) - ML models
✅ CloudWatch (₹300-500/month) - Monitoring
✅ WAF (₹500-1000/month) - Security
✅ ACM (FREE) - SSL
✅ Secrets Manager (₹120/month) - Secrets

Total: ~₹7220-14920/month
```

**Best For**: Enterprise, high traffic, advanced AI features

---

## Implementation Roadmap

### Phase 1: Foundation (Month 1-2)
**Budget**: ₹1000-2000/month

1. ✅ AWS Bedrock (already done)
2. ✅ EC2 deployment (already done)
3. Set up ACM for SSL certificates
4. Configure CloudWatch for basic monitoring
5. Migrate API keys to Secrets Manager

**Deliverables**:
- Secure HTTPS deployment
- Basic monitoring
- Secure secrets management

---

### Phase 2: Storage & Performance (Month 3-4)
**Budget**: ₹3000-4000/month

6. Migrate VCF files to S3
7. Set up CloudFront CDN
8. Implement ElastiCache for caching
9. Enhanced CloudWatch dashboards

**Deliverables**:
- Scalable storage
- Faster global access
- Improved response times

---

### Phase 3: Database & Scaling (Month 5-6)
**Budget**: ₹5000-6000/month

10. Migrate ChEMBL to RDS PostgreSQL
11. Set up DynamoDB for user data
12. Implement auto-scaling
13. Add WAF for security

**Deliverables**:
- Production-grade database
- User history and sessions
- Enhanced security

---

### Phase 4: Advanced Features (Month 7-12)
**Budget**: ₹8000-12000/month

14. Implement SageMaker for custom models
15. Set up AWS Batch for cohort processing
16. Add Step Functions for workflows
17. Evaluate Lambda for serverless API

**Deliverables**:
- Custom ML models
- Batch processing at scale
- Automated workflows

---

## Cost Optimization Strategies

### 1. Use AWS Free Tier
- EC2 t2.micro: 750 hours/month free (12 months)
- S3: 5GB storage free (12 months)
- RDS: 750 hours db.t2.micro free (12 months)
- Lambda: 1M requests free (always)
- CloudWatch: 10 metrics free (always)

**Savings**: ~₹2000-3000/month for first year

---

### 2. Reserved Instances
- 1-year commitment: 30-40% discount
- 3-year commitment: 50-60% discount
- Applies to: EC2, RDS, ElastiCache

**Savings**: ~₹500-1500/month after free tier

---

### 3. Spot Instances
- Use for AWS Batch jobs
- 70-90% discount vs on-demand
- Good for interruptible workloads

**Savings**: ~₹300-800/month on batch processing

---

### 4. S3 Lifecycle Policies
- Move old VCF files to S3 Glacier
- 90% cost reduction for archival
- Automatic transitions

**Savings**: ~₹150-300/month on storage

---

### 5. CloudFront Caching
- Reduce origin requests
- Lower EC2/Lambda costs
- Better performance

**Savings**: ~₹200-500/month on compute

---

## Security Best Practices

### 1. IAM Roles & Policies
- Use least privilege principle
- Separate roles for each service
- Enable MFA for console access
- Regular access reviews

### 2. VPC Configuration
- Private subnets for databases
- Public subnets for load balancers
- Security groups for firewall rules
- Network ACLs for additional security

### 3. Encryption
- Enable encryption at rest (S3, RDS, DynamoDB)
- Use KMS for key management
- Enable encryption in transit (TLS/SSL)
- Rotate encryption keys regularly

### 4. Monitoring & Auditing
- Enable CloudTrail for audit logs
- Set up CloudWatch alarms
- Monitor for unusual activity
- Regular security assessments

### 5. Backup & Disaster Recovery
- Automated RDS backups
- S3 versioning for VCF files
- Cross-region replication
- Regular restore testing

---

## Next Steps

### Immediate Actions (This Week)
1. ✅ Review this document
2. Set up AWS Certificate Manager for free SSL
3. Configure CloudWatch for basic monitoring
4. Migrate API keys to Secrets Manager

### Short Term (This Month)
5. Evaluate S3 for VCF storage
6. Test CloudFront for CDN
7. Plan RDS migration from SQLite
8. Set up cost alerts in AWS Billing

### Medium Term (Next 3 Months)
9. Implement ElastiCache for caching
10. Migrate to RDS PostgreSQL
11. Set up DynamoDB for user data
12. Implement auto-scaling

### Long Term (6-12 Months)
13. Evaluate SageMaker for custom models
14. Implement AWS Batch for cohorts
15. Add Step Functions for workflows
16. Consider Lambda for serverless API

---

## Conclusion

This document provides a comprehensive roadmap for integrating AWS services into SynthaTrial. The recommendations are prioritized by value, cost, and implementation complexity.

**Key Takeaways**:
- Start with free/low-cost services (ACM, CloudWatch, Secrets Manager)
- Gradually add storage and performance improvements (S3, CloudFront, ElastiCache)
- Scale to production-grade infrastructure (RDS, DynamoDB, WAF)
- Add advanced features when needed (SageMaker, Batch, Step Functions)

**Estimated Costs**:
- Minimal: ₹1000-2000/month
- Standard: ₹3000-5000/month
- Advanced: ₹8000-12000/month

**Current Status**: Using AWS Bedrock and EC2 (₹500-1000/month)

---

**Document Version**: 1.0
**Last Updated**: 2026-03-04
**Author**: Kiro AI Assistant
**Status**: Ready for Implementation
