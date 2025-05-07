#!/bin/sh
echo "Container environment:"
ls -la .
echo ""
echo "Environment variables:"
env | grep -E "TOKEN|CREDENTIALS"
echo ""
echo "Content of .env file:"
if [ -f .env ]; then cat .env; else echo ".env file not found"; fi
echo ""
echo "Starting bot..."
exec "$@"