#!/bin/bash

# Forward a local port to the Aurora database through a running SpellBot task.
#
# The database isn't reachable from the internet. This opens an SSM port-forwarding
# session (ECS Exec) to one of the environment's running tasks, which forwards the
# port on to the database from inside the VPC. Leave it running while you work;
# Ctrl-C closes it. A deploy replaces the task, which ends the session.
#
# Usage: scripts/db-tunnel.sh [environment] [local-port]
# Example: scripts/db-tunnel.sh prod 5433
#
# Then, in another terminal:
#   psql "host=localhost port=5433 dbname=spellbot_prod user=... sslmode=require"
#
# Needs the AWS CLI, credentials allowed to start ECS Exec sessions, and the Session
# Manager plugin (`brew install --cask session-manager-plugin`).

set -euo pipefail

ENVIRONMENT="${1:-prod}"
LOCAL_PORT="${2:-5433}"
REGION="us-east-1"
CLUSTER="spellbot-cluster"
SERVICE="spellbot-${ENVIRONMENT}"
CONTAINER="spellbot"
DB_CLUSTER="spellbot-aurora"
DB_PORT="5432"

fail() {
    echo "error: $1" >&2
    exit 1
}

command -v session-manager-plugin >/dev/null ||
    fail "the Session Manager plugin is missing: brew install --cask session-manager-plugin"

TASK_ARN=$(aws ecs list-tasks --region "$REGION" --cluster "$CLUSTER" \
    --service-name "$SERVICE" --desired-status RUNNING \
    --query 'taskArns[0]' --output text)
[[ "$TASK_ARN" != "None" && -n "$TASK_ARN" ]] || fail "no running task for $SERVICE"
TASK_ID="${TASK_ARN##*/}"

# The container's runtime id names the session target, and its exec agent has to be
# running: tasks started before ECS Exec was enabled don't have one.
read -r RUNTIME_ID AGENT_STATUS < <(aws ecs describe-tasks --region "$REGION" \
    --cluster "$CLUSTER" --tasks "$TASK_ARN" \
    --query "tasks[0].containers[?name=='${CONTAINER}'] | [0].[runtimeId, managedAgents[?name=='ExecuteCommandAgent'] | [0].lastStatus]" \
    --output text)
[[ "$AGENT_STATUS" == "RUNNING" ]] ||
    fail "task $TASK_ID has no running ECS Exec agent ($AGENT_STATUS); redeploy $SERVICE"

DB_HOST=$(aws rds describe-db-clusters --region "$REGION" \
    --db-cluster-identifier "$DB_CLUSTER" --query 'DBClusters[0].Endpoint' --output text)

echo "Forwarding localhost:${LOCAL_PORT} to ${DB_HOST}:${DB_PORT} through task ${TASK_ID}"
exec aws ssm start-session --region "$REGION" \
    --target "ecs:${CLUSTER}_${TASK_ID}_${RUNTIME_ID}" \
    --document-name AWS-StartPortForwardingSessionToRemoteHost \
    --parameters "{\"host\":[\"${DB_HOST}\"],\"portNumber\":[\"${DB_PORT}\"],\"localPortNumber\":[\"${LOCAL_PORT}\"]}"
