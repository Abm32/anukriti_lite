"""
Step Functions Orchestrator

This module provides AWS Step Functions integration for clinical trial orchestration,
coordinating multi-step workflows for population simulations.

Features:
- Clinical trial simulation workflow
- Workflow execution and monitoring
- Execution history tracking
- Error handling and retry policies
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception  # type: ignore[assignment]
    NoCredentialsError = Exception  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class StepFunctionsOrchestrator:
    """Step Functions integration for clinical trial orchestration"""

    def __init__(self, state_machine_arn: str, region: str = "us-east-1"):
        self.state_machine_arn = state_machine_arn
        self.region = region

        try:
            if boto3 is None:
                raise NoCredentialsError()
            self.stepfunctions_client = boto3.client(
                "stepfunctions", region_name=region
            )

            # Test connection
            self._test_connection()

        except NoCredentialsError:
            logger.warning(
                "AWS credentials not found. Step Functions operations will fail."
            )
            self.stepfunctions_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Step Functions client: {e}")
            self.stepfunctions_client = None

    def _test_connection(self):
        """Test Step Functions connection and state machine access"""
        if not self.stepfunctions_client:
            return False

        try:
            self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.state_machine_arn
            )
            logger.info(f"State machine {self.state_machine_arn} is accessible")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "StateMachineDoesNotExist":
                logger.warning(f"State machine {self.state_machine_arn} does not exist")
            elif error_code == "AccessDeniedException":
                logger.warning(
                    f"Access denied to state machine {self.state_machine_arn}"
                )
            else:
                logger.warning(f"Error accessing state machine: {e}")
            return False

    def start_clinical_trial_simulation(
        self,
        trial_name: str,
        drug: str,
        cohort_size: int,
        population_mix: Dict[str, float],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Start clinical trial simulation workflow"""
        if not self.stepfunctions_client:
            logger.error("Step Functions client not initialized")
            return None

        # Prepare input for state machine
        input_data = {
            "trial_name": trial_name,
            "drug": drug,
            "cohort_size": cohort_size,
            "population_mix": population_mix,
            "parameters": parameters or {},
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "1.0",
        }

        # Generate unique execution name
        execution_name = f"{trial_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            response = self.stepfunctions_client.start_execution(
                stateMachineArn=self.state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data),
            )

            execution_arn = response["executionArn"]
            logger.info(f"Started clinical trial simulation: {execution_arn}")

            return str(execution_arn)

        except ClientError as e:
            logger.error(f"Failed to start execution: {e}")
            return None

    def get_execution_status(self, execution_arn: str) -> Dict[str, Any]:
        """Get execution status and details"""
        if not self.stepfunctions_client:
            return {"error": "Step Functions client not initialized"}

        try:
            response = self.stepfunctions_client.describe_execution(
                executionArn=execution_arn
            )

            return {
                "execution_arn": response["executionArn"],
                "state_machine_arn": response["stateMachineArn"],
                "name": response["name"],
                "status": response["status"],
                "start_date": response["startDate"],
                "stop_date": response.get("stopDate"),
                "input": json.loads(response["input"]),
                "output": json.loads(response.get("output", "{}")),
                "error": response.get("error"),
                "cause": response.get("cause"),
            }

        except ClientError as e:
            logger.error(f"Failed to get execution status: {e}")
            return {"error": str(e)}

    def list_executions(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """List recent executions"""
        if not self.stepfunctions_client:
            return []

        try:
            response = self.stepfunctions_client.list_executions(
                stateMachineArn=self.state_machine_arn, maxResults=max_results
            )

            executions = []
            for execution in response["executions"]:
                execution_info = {
                    "execution_arn": execution["executionArn"],
                    "name": execution["name"],
                    "status": execution["status"],
                    "start_date": execution["startDate"],
                    "stop_date": execution.get("stopDate"),
                }
                executions.append(execution_info)

            logger.info(f"Found {len(executions)} executions")
            return executions

        except ClientError as e:
            logger.error(f"Failed to list executions: {e}")
            return []

    def get_execution_history(self, execution_arn: str) -> List[Dict[str, Any]]:
        """Get detailed execution history"""
        if not self.stepfunctions_client:
            return []

        try:
            response = self.stepfunctions_client.get_execution_history(
                executionArn=execution_arn
            )

            events = []
            for event in response["events"]:
                event_info = {
                    "timestamp": event["timestamp"],
                    "type": event["type"],
                    "id": event["id"],
                    "previous_event_id": event.get("previousEventId"),
                    "details": self._extract_event_details(event),
                }
                events.append(event_info)

            logger.info(f"Retrieved {len(events)} history events")
            return events

        except ClientError as e:
            logger.error(f"Failed to get execution history: {e}")
            return []

    def _extract_event_details(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant details from execution event"""
        details = {}

        # Extract details based on event type
        event_type = event["type"]

        if "stateEntered" in event_type.lower():
            details = event.get("stateEnteredEventDetails", {})
        elif "stateExited" in event_type.lower():
            details = event.get("stateExitedEventDetails", {})
        elif "taskScheduled" in event_type.lower():
            details = event.get("taskScheduledEventDetails", {})
        elif "taskSucceeded" in event_type.lower():
            details = event.get("taskSucceededEventDetails", {})
        elif "taskFailed" in event_type.lower():
            details = event.get("taskFailedEventDetails", {})
        elif "executionStarted" in event_type.lower():
            details = event.get("executionStartedEventDetails", {})
        elif "executionSucceeded" in event_type.lower():
            details = event.get("executionSucceededEventDetails", {})
        elif "executionFailed" in event_type.lower():
            details = event.get("executionFailedEventDetails", {})

        return details

    def stop_execution(
        self,
        execution_arn: str,
        error: str = "Manual stop",
        cause: str = "User requested stop",
    ) -> bool:
        """Stop a running execution"""
        if not self.stepfunctions_client:
            logger.error("Step Functions client not initialized")
            return False

        try:
            self.stepfunctions_client.stop_execution(
                executionArn=execution_arn, error=error, cause=cause
            )

            logger.info(f"Stopped execution: {execution_arn}")
            return True

        except ClientError as e:
            logger.error(f"Failed to stop execution: {e}")
            return False

    def create_state_machine_definition(self) -> Dict[str, Any]:
        """Create state machine definition for clinical trial simulation"""

        definition = {
            "Comment": "Clinical Trial Simulation Workflow",
            "StartAt": "GenerateCohort",
            "States": {
                "GenerateCohort": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:GenerateCohort",
                    "Parameters": {
                        "cohort_size.$": "$.cohort_size",
                        "population_mix.$": "$.population_mix",
                        "trial_name.$": "$.trial_name",
                    },
                    "ResultPath": "$.cohort",
                    "Next": "SimulateDrugResponse",
                    "Retry": [
                        {
                            "ErrorEquals": ["States.TaskFailed"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 3,
                            "BackoffRate": 2.0,
                        }
                    ],
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "HandleError",
                            "ResultPath": "$.error",
                        }
                    ],
                },
                "SimulateDrugResponse": {
                    "Type": "Map",
                    "ItemsPath": "$.cohort.patients",
                    "MaxConcurrency": 10,
                    "Parameters": {
                        "patient.$": "$",
                        "drug.$": "$.drug",
                        "trial_name.$": "$.trial_name",
                    },
                    "Iterator": {
                        "StartAt": "AnalyzePatient",
                        "States": {
                            "AnalyzePatient": {
                                "Type": "Task",
                                "Resource": "arn:aws:lambda:us-east-1:123456789012:function:AnalyzePatient",
                                "End": True,
                                "Retry": [
                                    {
                                        "ErrorEquals": ["States.TaskFailed"],
                                        "IntervalSeconds": 1,
                                        "MaxAttempts": 2,
                                        "BackoffRate": 2.0,
                                    }
                                ],
                            }
                        },
                    },
                    "ResultPath": "$.patient_results",
                    "Next": "AggregateResults",
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "HandleError",
                            "ResultPath": "$.error",
                        }
                    ],
                },
                "AggregateResults": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:AggregateResults",
                    "Parameters": {
                        "patient_results.$": "$.patient_results",
                        "cohort_info.$": "$.cohort",
                        "drug.$": "$.drug",
                        "trial_name.$": "$.trial_name",
                    },
                    "ResultPath": "$.aggregated_results",
                    "Next": "GenerateReport",
                    "Retry": [
                        {
                            "ErrorEquals": ["States.TaskFailed"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 3,
                            "BackoffRate": 2.0,
                        }
                    ],
                },
                "GenerateReport": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:GenerateReport",
                    "Parameters": {
                        "results.$": "$.aggregated_results",
                        "trial_name.$": "$.trial_name",
                        "timestamp.$": "$.timestamp",
                    },
                    "ResultPath": "$.report",
                    "Next": "Success",
                    "Retry": [
                        {
                            "ErrorEquals": ["States.TaskFailed"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 3,
                            "BackoffRate": 2.0,
                        }
                    ],
                },
                "Success": {"Type": "Succeed", "OutputPath": "$"},
                "HandleError": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:HandleError",
                    "Parameters": {
                        "error.$": "$.error",
                        "trial_name.$": "$.trial_name",
                        "timestamp.$": "$.timestamp",
                    },
                    "Next": "Fail",
                },
                "Fail": {"Type": "Fail", "Cause": "Clinical trial simulation failed"},
            },
        }

        return definition

    def create_state_machine_if_not_exists(
        self, state_machine_name: str, role_arn: str
    ) -> Optional[str]:
        """Create state machine if it doesn't exist (development mode)"""
        if not self.stepfunctions_client:
            logger.error("Step Functions client not initialized")
            return None

        # Check if state machine exists
        try:
            response = self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.state_machine_arn
            )
            logger.info(f"State machine {state_machine_name} already exists")
            return str(response["stateMachineArn"])
        except ClientError as e:
            if e.response["Error"]["Code"] != "StateMachineDoesNotExist":
                logger.error(f"Error checking state machine existence: {e}")
                return None

        # Create state machine
        try:
            definition = self.create_state_machine_definition()

            response = self.stepfunctions_client.create_state_machine(
                name=state_machine_name,
                definition=json.dumps(definition),
                roleArn=role_arn,
                type="STANDARD",
            )

            logger.info(f"Created state machine: {response['stateMachineArn']}")
            return str(response["stateMachineArn"])

        except ClientError as e:
            logger.error(f"Failed to create state machine: {e}")
            return None

    def get_state_machine_info(self) -> Dict[str, Any]:
        """Get state machine information"""
        if not self.stepfunctions_client:
            return {"error": "Step Functions client not initialized"}

        try:
            response = self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.state_machine_arn
            )

            return {
                "state_machine_arn": response["stateMachineArn"],
                "name": response["name"],
                "status": response["status"],
                "type": response["type"],
                "creation_date": response["creationDate"],
                "role_arn": response["roleArn"],
                "definition": json.loads(response["definition"]),
            }

        except ClientError as e:
            logger.error(f"Failed to get state machine info: {e}")
            return {"error": str(e)}


def main():
    """Main function for CLI usage"""

    # Example usage
    state_machine_arn = os.getenv(
        "AWS_STEP_FUNCTIONS_STATE_MACHINE",
        "arn:aws:states:us-east-1:123456789012:stateMachine:synthatrial-trial-orchestrator",
    )
    region = os.getenv("AWS_STEP_FUNCTIONS_REGION", "us-east-1")

    orchestrator = StepFunctionsOrchestrator(state_machine_arn, region)

    if orchestrator.stepfunctions_client:
        print("Step Functions Orchestrator initialized successfully")

        # Get state machine info
        info = orchestrator.get_state_machine_info()
        print(f"State machine info: {info}")

        # Example: Start a clinical trial simulation
        population_mix = {"EUR": 0.6, "AFR": 0.2, "EAS": 0.2}

        execution_arn = orchestrator.start_clinical_trial_simulation(
            trial_name="WarfarinTrial_Demo",
            drug="Warfarin",
            cohort_size=100,
            population_mix=population_mix,
        )

        if execution_arn:
            print(f"Started clinical trial simulation: {execution_arn}")

            # Get execution status
            status = orchestrator.get_execution_status(execution_arn)
            print(f"Execution status: {status}")

        # List recent executions
        executions = orchestrator.list_executions()
        print(f"Recent executions: {len(executions)}")

    else:
        print(
            "Step Functions client not initialized. Check AWS credentials and configuration."
        )

        # Show sample state machine definition
        orchestrator_demo = StepFunctionsOrchestrator("dummy-arn")
        definition = orchestrator_demo.create_state_machine_definition()
        print(f"Sample state machine definition:")
        print(json.dumps(definition, indent=2))


if __name__ == "__main__":
    main()
