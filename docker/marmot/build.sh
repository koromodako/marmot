#!/usr/bin/env bash
set -e
echo "building marmot package..."
rm -f ../../dist/* packages/*
../../venv/bin/python -m build ../../
cp ../../dist/*.whl packages/
echo "invoking docker build..."
sudo DOCKER_BUILDKIT=1 docker build -t marmot:latest .
