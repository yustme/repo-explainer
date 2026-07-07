# repo-explainer — build & publish the standalone Agnes skill.
#
# The Claude Code plugin under plugins/repo-explainer/ is the source of truth;
# scripts/build_skill.py flattens it into a standalone skill bundle and validates it.

.PHONY: skill upload test clean

# Build + validate + package -> dist/repo-explainer.skill
skill:
	python3 scripts/build_skill.py

# Build, then publish to the Agnes Flea Market (needs `agnes` on PATH + `agnes auth login`).
upload:
	python3 scripts/build_skill.py --upload

# Run the plugin's script tests.
test:
	cd plugins/repo-explainer && python3 -m pytest -q

# Remove build outputs.
clean:
	rm -rf build dist
