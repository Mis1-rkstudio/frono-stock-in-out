#!/bin/bash

# Exit on error
set -e

# Configuration
PROJECT_ID="round-kit-450201-r9"  # Replace with your GCP project ID
SERVICE_NAME="frono-stock-in-out"
REGION="asia-south1"
TOKEN_FILE=".scheduler_token"

# Function to generate and save token
generate_token() {
    local token=$(openssl rand -hex 16)
    echo "$token" > "$TOKEN_FILE"
    echo "$token"
}

# Get or generate scheduler token
echo "🔑 Checking for existing scheduler token..."
if [ -f "$TOKEN_FILE" ]; then
    SCHEDULER_TOKEN=$(cat "$TOKEN_FILE")
    echo "Using existing token from $TOKEN_FILE"
else
    echo "Generating new secure scheduler token..."
    SCHEDULER_TOKEN=$(generate_token)
    echo "Generated and saved new token to $TOKEN_FILE"
fi

echo "🚀 Starting deployment process..."

# Build and deploy to Cloud Run
echo "📦 Building and deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars="SCHEDULER_TOKEN=$SCHEDULER_TOKEN"

# Get the Cloud Run URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

# Create or update Cloud Scheduler job
echo "⏰ Setting up Cloud Scheduler..."
gcloud scheduler jobs create http stock-process-daily \
  --schedule="0 23 * * *" \
  --uri="$SERVICE_URL/scheduled" \
  --http-method=POST \
  --headers="X-Scheduler-Token=$SCHEDULER_TOKEN" \
  --time-zone="Asia/Kolkata" \
  --location=$REGION \
  --description="Daily stock process at 11 PM IST" \
  || gcloud scheduler jobs update http stock-process-daily \
  --schedule="0 23 * * *" \
  --uri="$SERVICE_URL/scheduled" \
  --http-method=POST \
  --headers="X-Scheduler-Token=$SCHEDULER_TOKEN" \
  --time-zone="Asia/Kolkata" \
  --location=$REGION

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo "📅 Scheduler will run daily at 11:00 PM IST"
echo "🔑 Using scheduler token from $TOKEN_FILE" 