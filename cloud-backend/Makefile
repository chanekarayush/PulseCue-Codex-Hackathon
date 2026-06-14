.PHONY: build deploy deploy-guided teardown clean release refresh upload_ui outputs validate

export DYLD_LIBRARY_PATH := /opt/homebrew/lib:$(DYLD_LIBRARY_PATH)

ifneq (,$(wildcard ../.env))
include ../.env
export
endif

TEMPLATE_FILE ?= template.yaml
STACK_NAME    ?= codex-project-backend
AWS_REGION    ?= $(shell aws configure get region 2>/dev/null)
AWS_REGION    := $(if $(strip $(AWS_REGION)),$(strip $(AWS_REGION)),us-east-1)

VIDEO_DYNAMO_TABLE       := $(or $(strip $(VIDEO_DYNAMO_TABLE)),$(strip $(DITTO_VIDEOS_TABLE)),codex_project-content)
BOOK_DYNAMO_TABLE        := $(or $(strip $(BOOK_DYNAMO_TABLE)),$(strip $(DITTO_BOOKS_TABLE)),codex_project-books)
VIDEO_QDRANT_COLLECTION  := $(or $(strip $(VIDEO_QDRANT_COLLECTION)),$(strip $(VIDEO_COLLECTION_NAME)),codex_project-videos)
CREATE_DYNAMO_TABLES     ?= true
HF_EMBEDDING_MODEL       := $(or $(strip $(HF_EMBEDDING_MODEL)),BAAI/bge-m3)

FRONTEND_DIR ?= ../frontend
UI_FALLBACK_DIR ?= ui

PARAMETER_OVERRIDES = \
	CreateDynamoTables=$(CREATE_DYNAMO_TABLES) \
	VideoMetadataTableName=$(VIDEO_DYNAMO_TABLE) \
	BooksMetadataTableName=$(BOOK_DYNAMO_TABLE) \
	VideoCollectionName=$(VIDEO_QDRANT_COLLECTION) \
	QdrantUrl=$(QDRANT_URL) \
	QdrantApiKey=$(QDRANT_API_KEY) \
	HfApiKey=$(HF_API_KEY) \
	HfEmbeddingModel=$(HF_EMBEDDING_MODEL)

validate:
	@echo "Validating SAM template..."
	sam validate -t $(TEMPLATE_FILE) --region $(AWS_REGION)

build:
	@echo "Building SAM application..."
	sam build -t $(TEMPLATE_FILE)

deploy: build
	@echo "Deploying SAM application..."
	sam deploy \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--parameter-overrides $(PARAMETER_OVERRIDES)

deploy-guided: build
	@echo "Deploying SAM application in guided mode..."
	sam deploy --guided \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides $(PARAMETER_OVERRIDES)

release: build
	@echo "Releasing $(STACK_NAME) to $(AWS_REGION)..."
	sam deploy \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--parameter-overrides $(PARAMETER_OVERRIDES)
	@$(MAKE) upload_ui
	@$(MAKE) outputs

refresh: build
	@echo "Refreshing backend stack..."
	sam deploy \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--parameter-overrides $(PARAMETER_OVERRIDES)
	@$(MAKE) upload_ui

upload_ui:
	@echo "Uploading UI assets..."
	@UI_BUCKET=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--query "Stacks[0].Outputs[?OutputKey=='UiBucketName'].OutputValue" \
		--output text 2>/dev/null || echo "") ; \
	if [ -z "$$UI_BUCKET" ] || [ "$$UI_BUCKET" = "None" ]; then \
		echo "UI bucket not found. Deploy the stack first."; \
		exit 1; \
	fi; \
	if [ -f "$(FRONTEND_DIR)/package.json" ]; then \
		echo "Building frontend from $(FRONTEND_DIR)..."; \
		cd $(FRONTEND_DIR) && npm install && npm run build; \
		SOURCE_DIR="$(FRONTEND_DIR)/dist"; \
	else \
		echo "No frontend package found. Uploading placeholder UI from $(UI_FALLBACK_DIR)."; \
		SOURCE_DIR="$(UI_FALLBACK_DIR)"; \
	fi; \
	aws s3 sync "$$SOURCE_DIR" "s3://$$UI_BUCKET" --delete --region $(AWS_REGION); \
	CF_DIST_ID=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
		--output text 2>/dev/null || echo "") ; \
	if [ -n "$$CF_DIST_ID" ] && [ "$$CF_DIST_ID" != "None" ]; then \
		echo "Invalidating CloudFront cache $$CF_DIST_ID..."; \
		aws cloudfront create-invalidation --distribution-id "$$CF_DIST_ID" --paths "/*" >/dev/null; \
	fi

outputs:
	@sam list stack-outputs --stack-name $(STACK_NAME) --region $(AWS_REGION)

teardown:
	@echo "Tearing down $(STACK_NAME)..."
	@UI_BUCKET=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION) \
		--query "Stacks[0].Outputs[?OutputKey=='UiBucketName'].OutputValue" \
		--output text 2>/dev/null || echo "") ; \
	if [ -n "$$UI_BUCKET" ] && [ "$$UI_BUCKET" != "None" ]; then \
		echo "Emptying UI bucket $$UI_BUCKET..."; \
		aws s3 rm "s3://$$UI_BUCKET" --recursive --region $(AWS_REGION) || true; \
	fi
	sam delete --stack-name $(STACK_NAME) --region $(AWS_REGION) --no-prompts
	@$(MAKE) clean

clean:
	@echo "Cleaning local SAM build artifacts..."
	rm -rf .aws-sam
