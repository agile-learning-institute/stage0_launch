.PHONY: help container dev run validate

CONTAINER_IMAGE ?= stage0_launch:latest

help:
	@echo "Available commands:"
	@echo "  make run              	          - docker compose: bootstrap (./Specifications, ../ launchpad, GITHUB_TOKEN)"
	@echo "  make dev SPECIFICATIONS=<path>  - Host: launch.sh bootstrap (tmp launchpad)"
	@echo "  make validate                     - Host: launch.sh validate (tooling check; optional GITHUB_TOKEN for gh)"
	@echo "  make container                   - Build image (tags stage0_launch:latest for compose build)"

container:
	@echo "Building container image: $(CONTAINER_IMAGE)"
	@docker build -f Dockerfile -t $(CONTAINER_IMAGE) .
	@echo "Built: $(CONTAINER_IMAGE)"

dev:
	@if [ -z "$(SPECIFICATIONS)" ]; then \
		echo "Error: SPECIFICATIONS must be set. Example: make dev SPECIFICATIONS=/path/to/specifications"; \
		exit 1; \
	fi
	@mkdir -p /tmp/stage0_launchpad_$$$$; \
	echo "Running launch script in Dev mode (SPECIFICATIONS=$(SPECIFICATIONS) LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$$$)..."; \
	SPECIFICATIONS="$(SPECIFICATIONS)" LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$$$ ./launch.sh bootstrap

validate:
	@./launch.sh validate

run:
	@echo "Running launch container (compose build ensures local image if GHCR is unavailable)..."
	@HOST_LAUNCHPAD="$(CURDIR)/.." docker compose up --build
