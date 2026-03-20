.PHONY: help container dev run

CONTAINER_IMAGE ?= stage0_launch:latest

help:
	@echo "Available commands:"
	@echo "  make run              	         - Run container (using ./Specifications and ../ as the launchpad)"
	@echo "  make dev SPECIFICATIONS=<path>  - Run launch.sh (using /tmp/stage0_launchpad_<pid> as the launchpad)"
	@echo "  make container                  - Build container for deployment"

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
	SPECIFICATIONS="$(SPECIFICATIONS)" LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$$$ ./launch.sh

run:
	@echo "Running launch container..."
	@HOST_SPECIFICATIONS="$(CURDIR)/Specifications" HOST_LAUNCHPAD="$(CURDIR)/.." docker compose up
