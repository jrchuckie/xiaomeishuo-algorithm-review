#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
swift "$repo_root/scripts/local_vision_poc.swift" \
  "$repo_root/backend/tests/live_assets/synthetic-night-female.jpg" \
  "$repo_root/backend/tests/live_assets/synthetic-car-male.jpg" \
  "$repo_root/backend/tests/live_assets/synthetic-side-female.jpg"
