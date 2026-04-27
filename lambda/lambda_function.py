import json


def lambda_handler(event, context):
    cohort_size = event.get("cohort_size", 100)
    drug = event.get("drug", "Warfarin")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Processed {cohort_size} patients for {drug}"}),
    }
