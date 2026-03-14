.PHONY: help container dev run

CONTAINER_IMAGE ?= stage0_launch:latest

help:
	@echo "Available commands:"
	@echo "  make dev              - Run the launch script in Dev mode (SPECIFICATIONS=./Specifications, LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$)"
	@echo "  make container        - Build container for deployment"
	@echo "  make run              - Run the launch container (mounts SPECIFICATIONS and LAUNCHPAD_DIR)"
	@echo "  make push             - Push the launch container to the registry"

container:
	@echo "Building container image: $(CONTAINER_IMAGE)"
	@docker build -f Dockerfile -t $(CONTAINER_IMAGE) .
	@echo "Built: $(CONTAINER_IMAGE)"

dev:
	@mkdir -p /tmp/stage0_launchpad_$$; \
	echo "Running launch script in Dev mode (LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$)..."; \
	SPECIFICATIONS=$$(pwd)/Specifications LAUNCHPAD_DIR=/tmp/stage0_launchpad_$$ ./launch.sh

run:
	@echo "Running launch container..."
	@HOST_SPECIFICATIONS="$(CURDIR)/Specifications" docker compose up

push:
	@echo "Pushing launch container to the registry..."
	@docker push $(CONTAINER_IMAGE)
