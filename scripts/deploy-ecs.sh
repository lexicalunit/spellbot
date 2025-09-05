#!/bin/bash

# AWS ECS Deployment Script
# Usage: ./deploy-ecs.sh <image-uri> <environment>
# Example: ./deploy-ecs.sh 123456789.dkr.ecr.us-east-1.amazonaws.com/spellbot-app:abc123 stage

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if required arguments are provided
if [[ $# -lt 2 ]]; then
    error "Usage: $0 <image-uri> <environment>"
    error "Example: $0 123456789.dkr.ecr.us-east-1.amazonaws.com/spellbot-app:abc123 stage"
    exit 1
fi

IMAGE_URI="$1"
ENVIRONMENT="$2"

# Validate environment
if [[ "$ENVIRONMENT" != "stage" && "$ENVIRONMENT" != "prod" ]]; then
    error "Environment must be 'stage' or 'prod'"
    exit 1
fi

# Set environment-specific variables
if [[ "$ENVIRONMENT" == "stage" ]]; then
    ECS_SERVICE="spellbot-stage"
    ECS_TASK_DEFINITION_FAMILY="spellbot-stage"
    SSM_PARAMETER_NAME="/spellbot/stage/ecr-image-uri"
else
    ECS_SERVICE="spellbot-prod"
    ECS_TASK_DEFINITION_FAMILY="spellbot-prod"
    SSM_PARAMETER_NAME="/spellbot/prod/ecr-image-uri"
fi

# Default values (can be overridden by environment variables)
ECS_CLUSTER="${ECS_CLUSTER:-spellbot-cluster}"
AWS_REGION="${AWS_REGION:-us-east-1}"

log "Starting deployment for $ENVIRONMENT environment"
log "Image URI: $IMAGE_URI"
log "ECS Service: $ECS_SERVICE"
log "ECS Cluster: $ECS_CLUSTER"
log "Task Definition Family: $ECS_TASK_DEFINITION_FAMILY"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    error "AWS CLI is not installed or not in PATH"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    error "jq is not installed or not in PATH"
    exit 1
fi

# Verify AWS credentials
log "Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    error "AWS credentials not configured or invalid"
    exit 1
fi
success "AWS credentials verified"

# Update SSM parameter with new image URI
log "Updating SSM parameter $SSM_PARAMETER_NAME with new image URI..."
aws ssm put-parameter \
    --name "$SSM_PARAMETER_NAME" \
    --value "$IMAGE_URI" \
    --type "String" \
    --overwrite \
    --region "$AWS_REGION" > /dev/null

# shellcheck disable=SC2181
if [[ $? -ne 0 ]]; then
    error "Failed to update SSM parameter $SSM_PARAMETER_NAME"
    exit 1
fi
success "SSM parameter updated successfully"

# Get current task definition
log "Fetching current task definition..."
CURRENT_TASK_DEF=$(aws ecs describe-task-definition \
    --task-definition "$ECS_TASK_DEFINITION_FAMILY" \
    --region "$AWS_REGION" \
    --query 'taskDefinition' \
    --output json)

if [[ -z "$CURRENT_TASK_DEF" || "$CURRENT_TASK_DEF" == "null" ]]; then
    error "Failed to fetch current task definition for $ECS_TASK_DEFINITION_FAMILY"
    exit 1
fi
success "Current task definition retrieved"

# Update task definition with new image
log "Updating task definition with new image..."
UPDATED_TASK_DEF=$(echo "$CURRENT_TASK_DEF" | jq --arg IMAGE "$IMAGE_URI" '
    .containerDefinitions |= map(
        if .name == "spellbot" or .name == "spellbot-gunicorn" then
            .image = $IMAGE
        else
            .
        end
    ) |
    del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .placementConstraints, .compatibilities, .registeredAt, .registeredBy)
')

if [[ -z "$UPDATED_TASK_DEF" || "$UPDATED_TASK_DEF" == "null" ]]; then
    error "Failed to update task definition"
    exit 1
fi

# Register new task definition
log "Registering new task definition..."
# Create temporary file for the task definition JSON
TEMP_TASK_DEF_FILE=$(mktemp)
# shellcheck disable=SC2064
trap "rm -f $TEMP_TASK_DEF_FILE" EXIT

echo "$UPDATED_TASK_DEF" > "$TEMP_TASK_DEF_FILE"

NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
    --region "$AWS_REGION" \
    --cli-input-json "file://$TEMP_TASK_DEF_FILE" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

if [[ -z "$NEW_TASK_DEF_ARN" || "$NEW_TASK_DEF_ARN" == "None" ]]; then
    error "Failed to register new task definition"
    exit 1
fi
success "New task definition registered: $NEW_TASK_DEF_ARN"

# Update ECS service
log "Updating ECS service..."
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --task-definition "$NEW_TASK_DEF_ARN" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --output table > /dev/null

# shellcheck disable=SC2181
if [[ $? -ne 0 ]]; then
    error "Failed to update ECS service"
    exit 1
fi
success "ECS service update initiated"

# Wait for deployment to complete
log "Waiting for deployment to complete (this may take several minutes)..."
if aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE" \
    --region "$AWS_REGION"; then
    success "Deployment completed successfully!"
else
    error "Deployment failed or timed out"
    exit 1
fi

# Get final service status
log "Getting final service status..."
aws ecs describe-services \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE" \
    --region "$AWS_REGION" \
    --query 'services[0].{ServiceName:serviceName,Status:status,TaskDefinition:taskDefinition,DesiredCount:desiredCount,RunningCount:runningCount}' \
    --output table

success "Deployment to $ENVIRONMENT environment completed successfully!"
log "Task Definition: $NEW_TASK_DEF_ARN"
log "Service: $ECS_SERVICE"
log "Cluster: $ECS_CLUSTER"

# Output deployment info for CI/CD systems
cat << EOF

DEPLOYMENT_INFO<<DEPLOYMENT_EOF
{
    "environment": "$ENVIRONMENT",
    "image": "$IMAGE_URI",
    "taskDefinition": "$NEW_TASK_DEF_ARN",
    "service": "$ECS_SERVICE",
    "cluster": "$ECS_CLUSTER",
    "region": "$AWS_REGION",
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
DEPLOYMENT_EOF
EOF
