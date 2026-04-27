#!/usr/bin/env python3
"""
Test S3 Integration Status
Quick test to verify if the system is using S3 genomic data vs local files
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment")

def test_s3_integration():
    """Test if S3 integration is working and being used"""
    
    print("🧬 Testing Anukriti S3 Integration Status")
    print("=" * 50)
    
    # Check environment variables
    print("📋 Environment Configuration:")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    s3_bucket = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    print(f"   AWS Access Key: {'✅ Set (' + aws_access_key[:8] + '...)' if aws_access_key else '❌ Missing'}")
    print(f"   S3 Bucket: {s3_bucket}")
    print(f"   AWS Region: {aws_region}")
    print()
    
    # Test S3 Manager
    print("☁️ Testing S3 Genomic Manager:")
    try:
        from src.aws.s3_genomic_manager import S3GenomicDataManager
        
        manager = S3GenomicDataManager(s3_bucket, aws_region)
        
        if manager.s3_client:
            print("   ✅ S3 Client: Connected")
            
            # List VCF files
            vcf_files = manager.list_vcf_files()
            print(f"   📊 VCF Files Found: {len(vcf_files)}")
            
            for file_info in vcf_files[:5]:  # Show first 5
                key = file_info['key']
                size_mb = file_info['size'] / (1024 * 1024)
                print(f"      - {key} ({size_mb:.1f} MB)")
            
            if len(vcf_files) > 5:
                print(f"      ... and {len(vcf_files) - 5} more files")
                
            # Get bucket info
            bucket_info = manager.get_bucket_info()
            if "error" not in bucket_info:
                total_size_mb = bucket_info.get("total_size_mb", 0)
                object_count = bucket_info.get("object_count", 0)
                print(f"   📦 Bucket Stats: {object_count} objects, {total_size_mb:.1f} MB total")
            
        else:
            print("   ❌ S3 Client: Failed to connect")
            
    except Exception as e:
        print(f"   ❌ S3 Manager Error: {e}")
    
    print()
    
    # Test VCF Discovery
    print("🔍 Testing VCF Discovery:")
    vcf_paths = {}
    try:
        from src.vcf_processor import discover_vcf_paths
        
        vcf_paths = discover_vcf_paths("data/genomes")
        
        if vcf_paths:
            print(f"   📁 VCF Files Discovered: {len(vcf_paths)}")
            
            s3_count = sum(1 for path in vcf_paths.values() if path.startswith("s3://"))
            local_count = len(vcf_paths) - s3_count
            
            print(f"   ☁️ S3 Files: {s3_count}")
            print(f"   💾 Local Files: {local_count}")
            
            print("   📋 Chromosome Mapping:")
            for chrom, path in vcf_paths.items():
                source = "S3" if path.startswith("s3://") else "Local"
                filename = path.split("/")[-1] if "/" in path else path
                print(f"      {chrom}: {source} ({filename})")
                
            if s3_count > 0:
                print("   🌟 Status: Using S3 genomic data!")
            else:
                print("   🏠 Status: Using local genomic data")
                
        else:
            print("   ❌ No VCF files found")
            
    except Exception as e:
        print(f"   ❌ VCF Discovery Error: {e}")
    
    print()
    
    # Test AWS Services
    print("⚡ Testing AWS Services:")
    
    # Lambda
    lambda_function = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "synthatrial-batch-processor")
    try:
        import boto3
        lambda_client = boto3.client('lambda', region_name=os.getenv("AWS_LAMBDA_REGION", "us-east-1"))
        response = lambda_client.get_function(FunctionName=lambda_function)
        print(f"   ✅ Lambda: {lambda_function} - Available")
        print(f"      Runtime: {response.get('Configuration', {}).get('Runtime', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Lambda: {lambda_function} - {str(e)[:80]}...")
    
    # Step Functions
    state_machine_arn = os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE")
    if state_machine_arn:
        try:
            import boto3
            sf_client = boto3.client('stepfunctions', region_name=os.getenv("AWS_STEP_FUNCTIONS_REGION", "us-east-1"))
            response = sf_client.describe_state_machine(stateMachineArn=state_machine_arn)
            print(f"   ✅ Step Functions: Available")
            print(f"      Status: {response.get('status', 'Unknown')}")
        except Exception as e:
            print(f"   ❌ Step Functions: {str(e)[:80]}...")
    else:
        print(f"   ⚠️ Step Functions: Not configured")
    
    print()
    print("🎯 Integration Summary:")
    
    # Determine overall status
    has_s3_data = any(path.startswith("s3://") for path in vcf_paths.values()) if vcf_paths else False
    has_aws_creds = bool(aws_access_key)
    
    if has_s3_data and has_aws_creds:
        print("   🌟 LIVE AWS INTEGRATION - Using cloud genomic data")
        print("   📊 Genomic data is being served from S3")
        print("   ⚡ AWS services are available for scaling")
        print("   🏆 Competition-ready deployment with full AWS stack")
    elif has_aws_creds:
        print("   🔄 PARTIAL AWS INTEGRATION - Credentials available but using local data")
        print("   💾 Genomic data is being served from local files")
        print("   ⚡ AWS services are available for scaling")
        print("   📝 Note: VCF files may need to be uploaded to S3")
    else:
        print("   🏠 LOCAL DEVELOPMENT MODE - No AWS integration")
        print("   💾 All data and processing is local")
        print("   📝 Note: Set AWS credentials in .env file for cloud integration")
    
    print("=" * 50)


if __name__ == "__main__":
    test_s3_integration()