#!/bin/bash
set -euo pipefail

# Script to build and run the installer smoke tests locally

echo "Building Docker images..."
docker build -t bear-hub-test:ubuntu22 -f docker/test/Dockerfile.ubuntu22 .
docker build -t bear-hub-test:debian12 -f docker/test/Dockerfile.debian12 .

run_test() {
    local image="$1"
    echo "----------------------------------------------------------------"
    echo "Running smoke test on $image"
    echo "----------------------------------------------------------------"

    # We mount:
    # - PWD (repo root) -> /app
    # - /var/run/docker.sock -> /var/run/docker.sock (for docker checks)
    #
    # We use --rm to clean up.
    # We run the harness script.

    docker run --rm \
        -v "$(pwd):/app" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -w /app \
        -e BEAR_NONINTERACTIVE=1 \
        "$image" \
        /bin/bash tests/smoke/install_smoke.sh
}

# Run tests
FAILED=0

if ! run_test "bear-hub-test:ubuntu22"; then
    echo "FAIL: Ubuntu 22 test failed"
    FAILED=1
fi

if ! run_test "bear-hub-test:debian12"; then
    echo "FAIL: Debian 12 test failed"
    FAILED=1
fi

if [ $FAILED -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
