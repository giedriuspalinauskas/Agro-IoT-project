#!/bin/bash
set -e

RPI_USER="admin"
RPI_HOST="192.168.0.177"
RPI_PATH="/home/admin/Agro-IoT-project"
LOCAL_PATH="$(dirname "$0")"

echo ">>> Sinchronizuojama su RPI..."
tar -C "$LOCAL_PATH" --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' -czf - . \
  | ssh "$RPI_USER@$RPI_HOST" "tar -xzf - -C $RPI_PATH"

echo ">>> Paleidžiami Docker konteineriai..."
ssh "$RPI_USER@$RPI_HOST" "cd $RPI_PATH && docker compose up -d --build"

echo ">>> Deploy baigtas!"
