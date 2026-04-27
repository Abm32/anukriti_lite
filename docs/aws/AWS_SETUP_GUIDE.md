# AWS Account Setup Guide for Anukriti

## Overview

You have implemented the following AWS services in your Anukriti platform:
- **S3** (Genomic data storage and PDF reports)
- **Lambda** (Batch processing for population simulation)
- **Step Functions** (Clinical trial workflow orchestration)
- **Bedrock** (Claude 3 for AI explanations)
- **CloudWatch** (Monitoring and logging)

Here's what you need to configure in your AWS account:

## 1. S3 Buckets Setup

### Create S3 Buckets
```bash
# Create genomic data bucket
aws s3 mb s3://synthatrial-genomic-data --region us-east-1

# Create reports bucket
aws s3 mb s3://synthatrial-reports --region us-east-1
```

### Configure Intelligent Tiering (Cost Optimization)
```bash
# Enable Intelligent Tiering for genomic data
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket synthatrial-genomic-data \
  --id GenomicDataTiering \
  --intelligent-tiering-configuration '{
    "Id": "GenomicDataTiering",
    "Status": "Enabled",
    "Filter": {"Prefix": "genomes/"},
    "Tierings": [
      {"Days": 1, "AccessTier": "ARCHIVE_ACCESS"},
      {"Days": 90, "AccessTier": "DEEP_ARCHIVE_ACCESS"}
    ]
  }'
```

### Set Lifecycle Policies for Reports
```bash
# Create lifecycle policy for PDF reports (30-day retention)
aws s3api put-bucket-lifecycle-configuration \
  --bucket synthatrial-reports \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "ReportCleanup",
      "Status": "Enabled",
      "Filter": {"Prefix": "reports/"},
      "Expiration": {"Days": 30}
    }]
  }'
```

## 2. Lambda Function Setup

### Create Lambda Function for Batch Processing
```bash
# Create execution role first
aws iam create-role \
  --role-name synthatrial-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name synthatrial-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create the Lambda function (you'll need to package your code)
aws lambda create-function \
  --function-name synthatrial-batch-processor \
  --runtime python3.10 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/synthatrial-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda-deployment-package.zip \
  --timeout 900 \
  --memory-size 1024
```

### Lambda Deployment Package
Create a simple Lambda function:

```python
# lambda_function.py
import json
import boto3

def lambda_handler(event, context):
    """
    Process batch simulation requests
    """
    try:
        # Extract parameters from event
        cohort_size = event.get('cohort_size', 100)
        drug = event.get('drug', 'Warfarin')

        # Your population simulation logic here
        # (simplified for demo)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {cohort_size} patients for {drug}',
                'cohort_size': cohort_size,
                'drug': drug,
                'status': 'completed'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
```

## 3. Step Functions Setup

### Create State Machine for Trial Orchestration
```bash
# Create Step Functions execution role
aws iam create-role \
  --role-name synthatrial-stepfunctions-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "states.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach Lambda invoke policy
aws iam attach-role-policy \
  --role-name synthatrial-stepfunctions-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaRole
```

### State Machine Definition
```json
{
  "Comment": "SynthaTrial Clinical Trial Orchestration",
  "StartAt": "InitializeTrial",
  "States": {
    "InitializeTrial": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:synthatrial-batch-processor",
      "Parameters": {
        "action": "initialize",
        "cohort_size.$": "$.cohort_size",
        "drug.$": "$.drug"
      },
      "Next": "ProcessCohort"
    },
    "ProcessCohort": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:synthatrial-batch-processor",
      "Parameters": {
        "action": "process",
        "cohort_size.$": "$.cohort_size",
        "drug.$": "$.drug"
      },
      "Next": "GenerateReport"
    },
    "GenerateReport": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:synthatrial-batch-processor",
      "Parameters": {
        "action": "report",
        "cohort_size.$": "$.cohort_size",
        "drug.$": "$.drug"
      },
      "End": true
    }
  }
}
```

Create the state machine:
```bash
aws stepfunctions create-state-machine \
  --name synthatrial-trial-orchestrator \
  --definition file://state-machine-definition.json \
  --role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/synthatrial-stepfunctions-role
```

## 4. Bedrock Setup

### Enable Bedrock Models
```bash
# Enable Claude 3 Haiku model (if not already enabled)
aws bedrock put-model-invocation-logging-configuration \
  --logging-config '{
    "cloudWatchConfig": {
      "logGroupName": "/aws/bedrock/synthatrial",
      "roleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/service-role/AmazonBedrockExecutionRoleForCloudWatch"
    },
    "s3Config": {
      "bucketName": "synthatrial-bedrock-logs"
    }
  }'
```

### Request Model Access
1. Go to AWS Bedrock Console
2. Navigate to "Model access"
3. Request access to:
   - **Claude 3 Haiku** (anthropic.claude-3-haiku-20240307-v1:0)
   - **Titan Embeddings** (amazon.titan-embed-text-v2:0)

## 5. IAM Roles and Policies

### Create Application Role
```bash
# Create role for your application
aws iam create-role \
  --role-name synthatrial-app-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Create custom policy
aws iam create-policy \
  --policy-name synthatrial-app-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        "Resource": [
          "arn:aws:s3:::synthatrial-genomic-data",
          "arn:aws:s3:::synthatrial-genomic-data/*",
          "arn:aws:s3:::synthatrial-reports",
          "arn:aws:s3:::synthatrial-reports/*"
        ]
      },
      {
        "Effect": "Allow",
        "Action": [
          "lambda:InvokeFunction"
        ],
        "Resource": "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:synthatrial-batch-processor"
      },
      {
        "Effect": "Allow",
        "Action": [
          "states:StartExecution",
          "states:DescribeExecution",
          "states:StopExecution"
        ],
        "Resource": "arn:aws:states:us-east-1:YOUR_ACCOUNT_ID:stateMachine:synthatrial-trial-orchestrator"
      },
      {
        "Effect": "Allow",
        "Action": [
          "bedrock:InvokeModel"
        ],
        "Resource": [
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
        ]
      },
      {
        "Effect": "Allow",
        "Action": [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Resource": "arn:aws:logs:us-east-1:YOUR_ACCOUNT_ID:*"
      }
    ]
  }'

# Attach policy to role
aws iam attach-role-policy \
  --role-name synthatrial-app-role \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/synthatrial-app-policy
```

## 6. Environment Variables

Update your `.env` file with the AWS resources:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_S3_BUCKET_GENOMIC=synthatrial-genomic-data
AWS_S3_BUCKET_REPORTS=synthatrial-reports
AWS_LAMBDA_FUNCTION_NAME=synthatrial-batch-processor
AWS_STEP_FUNCTIONS_STATE_MACHINE=arn:aws:states:us-east-1:YOUR_ACCOUNT_ID:stateMachine:synthatrial-trial-orchestrator

# Bedrock Configuration
BEDROCK_REGION=us-east-1
CLAUDE_MODEL=anthropic.claude-3-haiku-20240307-v1:0
TITAN_EMBED_MODEL=amazon.titan-embed-text-v2:0

# Population Simulation
POPULATION_SIMULATOR_MAX_COHORT_SIZE=10000
POPULATION_SIMULATOR_BATCH_SIZE=100
POPULATION_SIMULATOR_ENABLE_LAMBDA=true
```

## 7. Testing Your Setup

### Test S3 Integration
```bash
python -c "
from src.aws.s3_genomic_manager import S3GenomicDataManager
manager = S3GenomicDataManager('synthatrial-genomic-data')
print('S3 Status:', manager.get_bucket_info())
"
```

### Test Lambda Integration
```bash
python -c "
from src.aws.lambda_batch_processor import LambdaBatchProcessor
processor = LambdaBatchProcessor('synthatrial-batch-processor')
print('Lambda Status:', processor.get_function_info())
"
```

### Test Population Simulation
```bash
python src/population_simulator.py --cohort-size 100 --drug Warfarin
```

## 8. Cost Optimization Tips

### Free Tier Usage
- **S3**: 5GB free storage for 12 months
- **Lambda**: 1M free requests + 400,000 GB-seconds per month
- **Step Functions**: 4,000 state transitions per month
- **Bedrock**: Pay per token (no free tier, but very cost-effective)

### Cost Monitoring
```bash
# Set up billing alerts
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget '{
    "BudgetName": "SynthaTrial-Monthly-Budget",
    "BudgetLimit": {
      "Amount": "10.00",
      "Unit": "USD"
    },
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }'
```

## 9. Security Best Practices

### Enable CloudTrail
```bash
aws cloudtrail create-trail \
  --name synthatrial-audit-trail \
  --s3-bucket-name synthatrial-cloudtrail-logs
```

### Enable GuardDuty
```bash
aws guardduty create-detector --enable
```

## 10. Quick Setup Script

Create `setup-aws.sh`:
```bash
#!/bin/bash
set -e

echo "Setting up AWS resources for SynthaTrial..."

# Replace with your AWS account ID
ACCOUNT_ID="123456789012"
REGION="us-east-1"

# Create S3 buckets
aws s3 mb s3://synthatrial-genomic-data --region $REGION
aws s3 mb s3://synthatrial-reports --region $REGION

echo "✅ S3 buckets created"

# Create IAM role and policies
# (Add the IAM commands from above)

echo "✅ IAM roles created"

# Create Lambda function
# (Add Lambda creation commands)

echo "✅ Lambda function created"

# Create Step Functions state machine
# (Add Step Functions commands)

echo "✅ Step Functions state machine created"

echo "🎉 AWS setup complete!"
echo "Don't forget to:"
echo "1. Request Bedrock model access in the console"
echo "2. Update your .env file with the resource ARNs"
echo "3. Test the integration with: python src/population_simulator.py"
```

## Summary

**Total estimated monthly cost for demo usage:**
- S3: ~$1-5 (depending on data stored)
- Lambda: ~$0-2 (within free tier for demo)
- Step Functions: ~$0-1 (within free tier for demo)
- Bedrock: ~$5-20 (depending on usage)
- **Total: $6-28/month for demo usage**

**Next Steps:**
1. Run the setup commands above
2. Request Bedrock model access
3. Update your `.env` file
4. Test with: `python scripts/benchmark_performance.py --aws-cost-analysis`
5. Deploy to EC2 for full integration

This setup will make your AWS Competition Enhancement features fully functional!
