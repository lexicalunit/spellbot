.PHONY: all run

all: run

run:
	@command -v rbenv >/dev/null 2>&1 || brew install rbenv
	rbenv install --skip-existing
	eval "$$(rbenv init - zsh)" && \
		rbenv rehash && \
		(bundle update --bundler 2>/dev/null || true) && \
		bundle install && \
		bundle exec jekyll serve
