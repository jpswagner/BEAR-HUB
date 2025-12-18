# Testing Instructions

This document describes how to run the smoke tests for the BEAR-HUB installer.
These tests simulate a "clean PC" environment using Docker to ensure the installer works correctly in the absence of pre-existing dependencies (except for basic system tools).

## Prerequisites

*   Docker installed and running.
*   (Optional) `make` or standard Unix shell (bash).

## Running Tests Locally

You can run the full suite of installer tests (Ubuntu 22.04 and Debian 12) using the provided script:

```bash
./ci/run_installer_tests.sh
```

This script will:
1.  Build the test Docker images (`bear-hub-test:ubuntu22` and `bear-hub-test:debian12`).
2.  Run the installer inside each container.
3.  Mount the local repository code into the container (at `/app`).
4.  Mount the Docker socket (`/var/run/docker.sock`) to allow the installer to verify Docker functionality.
5.  Execute `tests/smoke/install_smoke.sh` which:
    *   Installs Miniforge (Mamba) as a prerequisite (since the base image is clean).
    *   Runs `bear_installer.py` in non-interactive mode.
    *   Verifies that Java (>=17), Nextflow, and Docker are correctly detected/installed.
    *   Checks if Streamlit can load the `BEAR-HUB.py` app (help check).

## Artifacts

Logs from the installation process are saved to the `artifacts/` directory in the repository root if the test runs successfully (or partially runs).

## CI / GitHub Actions

The tests are automatically triggered on Push and Pull Request events via the `.github/workflows/installer-smoke.yml` workflow.
Artifacts (install logs) are uploaded to the workflow run summary.

## Troubleshooting

If the test fails, check the output in the terminal. The script `tests/smoke/install_smoke.sh` prints `PASS` or `FAIL` for each check.

Common issues:
*   **Docker Socket Permissions**: Ensure the user running the script has permission to access `/var/run/docker.sock`.
*   **Network**: The test downloads Miniforge and Nextflow. Ensure internet access is available.

## Cleaning Up

To remove the generated artifacts and the Docker images created by the tests, run:

```bash
./ci/clean_tests.sh
```
