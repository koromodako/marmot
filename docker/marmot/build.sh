#!/usr/bin/env bash
set -e
echo "copying wheel package to packages directory..."
rm -f packages/*.whl
cp ../../dist/*.whl packages/
echo "invoking docker build..."
sudo DOCKER_BUILDKIT=1 docker build -t marmot:latest .
