#!/bin/sh

echo "=== MinIO Initialization Script ==="

# Wait for MinIO to be ready - retry connection with timeout
MAX_ATTEMPTS=30  # 30 attempts * 10s = 5 minute timeout
ATTEMPT=0

echo "Waiting for MinIO connection..."
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: Connecting to MinIO..."
  
  if mc alias set myminio http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD 2>/dev/null; then
    echo "✓ MinIO connection successful!"
    break
  fi
  
  if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "✗ Failed to connect to MinIO after $MAX_ATTEMPTS attempts"
    exit 1
  fi
  
  echo "  MinIO not ready yet, retrying in 10 seconds..."
  sleep 10
done

set -e  # Now exit on any error (after connection is established)

# Read bucket names from buckets file (one per line)
BUCKETS=$(cat /config/buckets | tr '\n' ' ')

echo "Creating buckets and setting public access..."
for BUCKET in $BUCKETS; do
  echo "Processing bucket: $BUCKET"
  
  # Create bucket if it doesn't exist (mb = make bucket)
  if mc ls myminio/$BUCKET >/dev/null 2>&1; then
    echo "  ✓ Bucket '$BUCKET' already exists"
  else
    mc mb myminio/$BUCKET
    echo "  ✓ Bucket '$BUCKET' created"
  fi
  
  # Set anonymous (public) read/write policy
  # This allows access without credentials - needed for some Iceberg configurations
  mc anonymous set public myminio/$BUCKET
  echo "  ✓ Public access configured for '$BUCKET'"
done

echo ""
echo "=== Initialization Complete ==="
echo "Created/verified buckets:"
mc ls myminio

echo ""
echo "Bucket policies:"
for BUCKET in $BUCKETS; do
  echo "Policy for $BUCKET:"
  mc anonymous get myminio/$BUCKET || echo "  (could not retrieve policy)"
done
