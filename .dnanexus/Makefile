.PHONY: help docker
.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys
for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

docker: ## Builds AIxPORT Docker image
	@cd .. ;\
	cv=`grep 'version' .dnanexus/conf.yml | sed "s/^.*: *\"//" | sed "s/\".*//"`; \
	docker buildx build --platform linux/amd64 \
		-t digitaltumors/aixport:$$cv \
		-f .dnanexus/docker/Dockerfile .;
