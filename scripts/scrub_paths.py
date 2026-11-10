#!/usr/bin/env python3
"""Reads text on stdin, writes it to stdout with local user, temp and repo paths replaced.

Used by scripts/tdd_step.sh and scripts/make_g1_results.py so committed logs carry no local username
or temp directory. Usage: some-command | python3 scripts/scrub_paths.py [repo_path]
"""
import re
import sys

_RULES = (
    (re.compile(r"/(?:private/)?var/folders/[^\s:'\"]*"), "<tmp>"),
    (re.compile(r"pytest-of-[^/\s]+"), "pytest-of-<user>"),
    (re.compile(r"/Users/[^/\s:'\"]+"), "<home>"),
    (re.compile(r"/home/[^/\s:'\"]+"), "<home>"),
)


def scrub(text, repo=None):
    if repo:
        text = text.replace(repo, "<repo>")
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


if __name__ == "__main__":
    sys.stdout.write(scrub(sys.stdin.read(), sys.argv[1] if len(sys.argv) > 1 else None))
