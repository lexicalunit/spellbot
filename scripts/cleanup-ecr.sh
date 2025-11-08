#!/bin/bash
#
# Cleanup old ECR images while preserving prod, stage, and latest tags
#
# This script deletes tagged images older than a specified number of days,
# but always preserves images tagged with 'prod', 'stage', or 'latest'.
#
# Usage:
#   ./scripts/cleanup-ecr.sh [days] [repository-name]
#
# Examples:
#   ./scripts/cleanup-ecr.sh 180 spellbot-app  # Delete images older than 180 days
#   ./scripts/cleanup-ecr.sh 90                # Delete images older than 90 days (default repo)
#

set -euo pipefail

# Configuration
DEFAULT_DAYS=180
DEFAULT_REPOSITORY="spellbot-app"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Parse arguments
DAYS="${1:-$DEFAULT_DAYS}"
REPOSITORY="${2:-$DEFAULT_REPOSITORY}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

# Validate inputs
if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
    error "Days must be a positive integer"
    exit 1
fi

log "ECR Image Cleanup Configuration:"
log "  Repository: $REPOSITORY"
log "  Region: $AWS_REGION"
log "  Delete images older than: $DAYS days"
log "  Protected tags: prod, stage, latest"
echo ""

# Calculate cutoff timestamp (seconds since epoch)
CUTOFF_TIMESTAMP=$(date -u -v-"${DAYS}"d +%s 2>/dev/null || date -u -d "$DAYS days ago" +%s)
CUTOFF_DATE=$(date -u -r "$CUTOFF_TIMESTAMP" +%Y-%m-%d 2>/dev/null || date -u -d "@$CUTOFF_TIMESTAMP" +%Y-%m-%d)

log "Cutoff date: $CUTOFF_DATE"
echo ""

# Check if repository exists
if ! aws ecr describe-repositories \
    --repository-names "$REPOSITORY" \
    --region "$AWS_REGION" \
    --output json > /dev/null 2>&1; then
    error "Repository '$REPOSITORY' not found in region '$AWS_REGION'"
    exit 1
fi

# Get all images
log "Fetching images from repository..."
IMAGES=$(aws ecr describe-images \
    --repository-name "$REPOSITORY" \
    --region "$AWS_REGION" \
    --output json)

if [[ -z "$IMAGES" || "$IMAGES" == "null" ]]; then
    error "Failed to fetch images from repository"
    exit 1
fi

# Find images to delete
log "Analyzing images..."
IMAGES_TO_DELETE=$(echo "$IMAGES" | jq -r --arg cutoff "$CUTOFF_TIMESTAMP" '
    .imageDetails[] |
    select(.imageTags != null) |
    select(
        (.imageTags | any(. == "prod" or . == "stage" or . == "latest")) | not
    ) |
    select(.imagePushedAt < ($cutoff | tonumber)) |
    {
        digest: .imageDigest,
        tags: (.imageTags | join(", ")),
        pushedAt: .imagePushedAt
    }
')

if [[ -z "$IMAGES_TO_DELETE" ]]; then
    success "No images found matching deletion criteria"
    exit 0
fi

# Count images to delete
IMAGE_COUNT=$(echo "$IMAGES_TO_DELETE" | jq -s 'length')

warn "Found $IMAGE_COUNT image(s) to delete:"
echo ""
echo "$IMAGES_TO_DELETE" | jq -r '"  Tags: \(.tags)\n  Pushed: \(.pushedAt)\n  Digest: \(.digest)\n"'

# Confirm deletion
read -p "Do you want to delete these images? (yes/no): " -r
echo ""
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    log "Deletion cancelled"
    exit 0
fi

# Delete images
log "Deleting images..."
DELETED_COUNT=0
FAILED_COUNT=0

while IFS= read -r digest; do
    if aws ecr batch-delete-image \
        --repository-name "$REPOSITORY" \
        --region "$AWS_REGION" \
        --image-ids "imageDigest=$digest" \
        --output json > /dev/null 2>&1; then
        ((DELETED_COUNT++))
        log "Deleted image: $digest"
    else
        ((FAILED_COUNT++))
        error "Failed to delete image: $digest"
    fi
done < <(echo "$IMAGES_TO_DELETE" | jq -r '.digest')

echo ""
success "Cleanup complete!"
log "  Deleted: $DELETED_COUNT image(s)"
if [[ $FAILED_COUNT -gt 0 ]]; then
    warn "  Failed: $FAILED_COUNT image(s)"
fi
