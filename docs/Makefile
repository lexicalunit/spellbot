.PHONY: all run dev build

all: run

# Serve with local development overrides so the live-stats widget points at a
# locally running API instead of production. See `_config_dev.yml`.
dev:
	cd .. && npm ci && npm run docs:vendor
	@command -v rbenv >/dev/null 2>&1 || brew install rbenv
	rbenv install --skip-existing
	eval "$$(rbenv init - zsh)" && \
		rbenv rehash && \
		(bundle update --bundler 2>/dev/null || true) && \
		bundle install && \
		bundle exec jekyll serve --config _config.yml,_config_dev.yml

run:
	cd .. && npm ci && npm run docs:vendor
	@command -v rbenv >/dev/null 2>&1 || brew install rbenv
	rbenv install --skip-existing
	eval "$$(rbenv init - zsh)" && \
		rbenv rehash && \
		(bundle update --bundler 2>/dev/null || true) && \
		bundle install && \
		bundle exec jekyll serve

build:
	cd .. && npm ci && npm run docs:vendor
	@command -v rbenv >/dev/null 2>&1 || brew install rbenv
	rbenv install --skip-existing
	eval "$$(rbenv init - zsh)" && \
		rbenv rehash && \
		(bundle update --bundler 2>/dev/null || true) && \
		bundle install && \
		bundle exec jekyll build --strict_front_matter
