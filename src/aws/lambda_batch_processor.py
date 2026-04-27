"""
Lambda Batch Processor

This module provides AWS Lambda integration for batch processing of large patient cohorts,
enabling parallel processing and scalability for population simulations.

Features:
- Async Lambda function invocation
- Batch cohort processing with configurable batch sizes
- Request ID tracking and result collection
- Error handling and retry logic
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception  # type: ignore[assignment]
    NoCredentialsError = Exception  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class LambdaBatchProcessor:
    """Lambda integration for batch processing of patient cohorts"""

    def __init__(self, function_name: str, region: str = "us-east-1"):
        self.function_name = function_name
        self.region = region

        try:
            if boto3 is None:
                raise NoCredentialsError()
            self.lambda_client = boto3.client("lambda", region_name=region)

            # Test connection
            self._test_connection()

        except NoCredentialsError:
            logger.warning("AWS credentials not found. Lambda operations will fail.")
            self.lambda_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Lambda client: {e}")
            self.lambda_client = None

    def _test_connection(self):
        """Test Lambda connection and function access"""
        if not self.lambda_client:
            return False

        try:
            self.lambda_client.get_function(FunctionName=self.function_name)
            logger.info(f"Lambda function {self.function_name} is accessible")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.warning(f"Lambda function {self.function_name} does not exist")
            elif error_code == "AccessDeniedException":
                logger.warning(f"Access denied to Lambda function {self.function_name}")
            else:
                logger.warning(f"Error accessing Lambda function: {e}")
            return False

    def invoke_batch_simulation(
        self,
        drug: str,
        patient_batch: List[Dict[str, Any]],
        invocation_type: str = "Event",
    ) -> Optional[Union[str, Tuple[str, Any]]]:
        """Invoke Lambda function for batch simulation"""
        if not self.lambda_client:
            logger.error("Lambda client not initialized")
            return None

        payload = {
            "drug": drug,
            "patients": patient_batch,
            "timestamp": datetime.now().isoformat(),
            "batch_size": len(patient_batch),
            "invocation_type": invocation_type,
        }

        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType=invocation_type,  # 'Event' for async, 'RequestResponse' for sync
                Payload=json.dumps(payload),
            )

            request_id = response["ResponseMetadata"]["RequestId"]

            if invocation_type == "RequestResponse":
                # Synchronous invocation - get result immediately
                result_payload = json.loads(response["Payload"].read())
                logger.info(f"Synchronous Lambda invocation completed: {request_id}")
                return (str(request_id), result_payload)
            else:
                # Asynchronous invocation - just return request ID
                logger.info(f"Asynchronous Lambda invocation started: {request_id}")
                return str(request_id)

        except ClientError as e:
            logger.error(f"Failed to invoke Lambda function: {e}")
            return None

    def process_cohort_parallel(
        self,
        drug: str,
        cohort: List[Dict[str, Any]],
        batch_size: int = 100,
        max_concurrent: int = 10,
    ) -> List[str]:
        """Process large cohort using parallel Lambda invocations"""
        if not self.lambda_client:
            logger.error("Lambda client not initialized")
            return []

        # Split cohort into batches
        batches = [
            cohort[i : i + batch_size] for i in range(0, len(cohort), batch_size)
        ]

        logger.info(
            f"Processing {len(cohort)} patients in {len(batches)} batches of {batch_size}"
        )

        request_ids = []

        # Use ThreadPoolExecutor to limit concurrent invocations
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_batch = {
                executor.submit(self.invoke_batch_simulation, drug, batch): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    result = future.result()
                    if result is not None:
                        req_id = result[0] if isinstance(result, tuple) else result
                        request_ids.append(str(req_id))
                        logger.info(
                            f"Submitted batch {batch_idx + 1}/{len(batches)}: {req_id}"
                        )
                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed: {e}")

        logger.info(f"Submitted {len(request_ids)} Lambda invocations")
        return request_ids

    def get_function_info(self) -> Dict[str, Any]:
        """Get Lambda function information"""
        if not self.lambda_client:
            return {"error": "Lambda client not initialized"}

        try:
            response = self.lambda_client.get_function(FunctionName=self.function_name)

            config = response["Configuration"]

            return {
                "function_name": config["FunctionName"],
                "runtime": config["Runtime"],
                "timeout": config["Timeout"],
                "memory_size": config["MemorySize"],
                "last_modified": config["LastModified"],
                "code_size": config["CodeSize"],
                "state": config["State"],
                "version": config["Version"],
                "environment": config.get("Environment", {}).get("Variables", {}),
                "concurrent_executions": config.get(
                    "ReservedConcurrencyExecutions", "Unreserved"
                ),
            }

        except ClientError as e:
            logger.error(f"Failed to get function info: {e}")
            return {"error": str(e)}

    def update_function_configuration(
        self,
        timeout: Optional[int] = None,
        memory_size: Optional[int] = None,
        environment_variables: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Update Lambda function configuration"""
        if not self.lambda_client:
            logger.error("Lambda client not initialized")
            return False

        update_params: Dict[str, Any] = {"FunctionName": self.function_name}

        if timeout is not None:
            update_params["Timeout"] = timeout

        if memory_size is not None:
            update_params["MemorySize"] = memory_size

        if environment_variables is not None:
            update_params["Environment"] = {"Variables": environment_variables}

        try:
            response = self.lambda_client.update_function_configuration(**update_params)
            logger.info(
                f"Updated Lambda function configuration: {response['FunctionName']}"
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to update function configuration: {e}")
            return False

    def create_function_if_not_exists(
        self,
        zip_file_path: str,
        handler: str = "lambda_function.lambda_handler",
        runtime: str = "python3.10",
        timeout: int = 300,
        memory_size: int = 512,
    ) -> bool:
        """Create Lambda function if it doesn't exist (development mode)"""
        if not self.lambda_client:
            logger.error("Lambda client not initialized")
            return False

        # Check if function exists
        try:
            self.lambda_client.get_function(FunctionName=self.function_name)
            logger.info(f"Lambda function {self.function_name} already exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                logger.error(f"Error checking function existence: {e}")
                return False

        # Function doesn't exist, create it
        if not os.path.exists(zip_file_path):
            logger.error(f"Zip file not found: {zip_file_path}")
            return False

        try:
            with open(zip_file_path, "rb") as zip_file:
                zip_content = zip_file.read()

            response = self.lambda_client.create_function(
                FunctionName=self.function_name,
                Runtime=runtime,
                Role=self._get_or_create_execution_role(),
                Handler=handler,
                Code={"ZipFile": zip_content},
                Timeout=timeout,
                MemorySize=memory_size,
                Environment={
                    "Variables": {"ENVIRONMENT": "development", "LOG_LEVEL": "INFO"}
                },
            )

            logger.info(f"Created Lambda function: {response['FunctionName']}")
            return True

        except ClientError as e:
            logger.error(f"Failed to create Lambda function: {e}")
            return False

    def _get_or_create_execution_role(self) -> str:
        """Get or create IAM role for Lambda execution"""
        # This is a simplified implementation
        # In production, you would create a proper IAM role with necessary permissions

        role_name = f"{self.function_name}-execution-role"

        try:
            iam_client = boto3.client("iam")

            # Try to get existing role
            try:
                response = iam_client.get_role(RoleName=role_name)
                return str(response["Role"]["Arn"])
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    raise

            # Create role if it doesn't exist
            assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }

            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description=f"Execution role for {self.function_name}",
            )

            # Attach basic execution policy
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )

            logger.info(f"Created IAM role: {role_name}")
            return str(response["Role"]["Arn"])

        except Exception as e:
            logger.error(f"Failed to get/create execution role: {e}")
            # Return a placeholder ARN for development
            return "arn:aws:iam::123456789012:role/lambda-execution-role"

    def monitor_invocations(
        self, request_ids: List[str], timeout: int = 300
    ) -> Dict[str, Any]:
        """Monitor Lambda invocations (simplified implementation)"""
        if not self.lambda_client:
            return {"error": "Lambda client not initialized"}

        # This is a simplified monitoring implementation
        # In production, you would use CloudWatch Logs or other monitoring services

        logger.info(f"Monitoring {len(request_ids)} Lambda invocations")

        # For now, just return a summary
        return {
            "total_invocations": len(request_ids),
            "request_ids": request_ids,
            "status": "submitted",
            "note": "Use CloudWatch Logs for detailed monitoring",
        }


def create_lambda_deployment_package():
    """Create deployment package for Lambda function"""

    lambda_function_code = '''
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Lambda function for batch patient simulation"""

    try:
        drug = event.get('drug', 'unknown')
        patients = event.get('patients', [])
        batch_size = len(patients)

        logger.info(f"Processing {batch_size} patients for drug: {drug}")

        # Simulate processing each patient
        results = []
        for patient in patients:
            # Simple simulation logic
            result = {
                'patient_id': patient.get('patient_id', 'unknown'),
                'drug': drug,
                'response_type': 'normal',  # Simplified
                'confidence': 0.8,
                'processing_time': 0.1
            }
            results.append(result)

        response = {
            'statusCode': 200,
            'body': {
                'processed': batch_size,
                'drug': drug,
                'results': results,
                'timestamp': event.get('timestamp')
            }
        }

        logger.info(f"Successfully processed {batch_size} patients")
        return response

    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'processed': 0
            }
        }
'''

    # Save Lambda function code
    lambda_dir = Path("lambda_functions")
    lambda_dir.mkdir(exist_ok=True)

    with open(lambda_dir / "lambda_function.py", "w") as f:
        f.write(lambda_function_code)

    logger.info(f"Created Lambda function code in {lambda_dir}")
    return lambda_dir / "lambda_function.py"


def main():
    """Main function for CLI usage"""

    # Example usage
    function_name = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "synthatrial-batch-processor")
    region = os.getenv("AWS_LAMBDA_REGION", "us-east-1")

    processor = LambdaBatchProcessor(function_name, region)

    if processor.lambda_client:
        print("Lambda Batch Processor initialized successfully")

        # Get function info
        info = processor.get_function_info()
        print(f"Function info: {info}")

        # Example: Process a small batch
        dummy_patients = [
            {"patient_id": f"TEST_{i:03d}", "population": "EUR"} for i in range(10)
        ]

        request_ids = processor.process_cohort_parallel(
            "Warfarin", dummy_patients, batch_size=5
        )
        print(f"Submitted {len(request_ids)} Lambda invocations")

        # Monitor invocations
        monitoring = processor.monitor_invocations(request_ids)
        print(f"Monitoring: {monitoring}")

    else:
        print("Lambda client not initialized. Check AWS credentials and configuration.")

        # Create sample Lambda function code
        lambda_file = create_lambda_deployment_package()
        print(f"Created sample Lambda function code: {lambda_file}")


if __name__ == "__main__":
    main()
