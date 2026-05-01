#!/bin/sh
#
# Use this script to run your program LOCALLY.
#
# Note: Changing this script WILL NOT affect how CodeCrafters runs your program.
#
# Learn more: https://codecrafters.io/program-interface

set -e # Exit early if any commands fail

if command -v pipenv >/dev/null 2>&1; then
  exec pipenv run python3 -m app.main "$@"
elif python3 -c 'import requests' >/dev/null 2>&1; then
  exec python3 -m app.main "$@"
elif command -v uv >/dev/null 2>&1; then
  exec uv run python3 -m app.main "$@"
else
  exec python3 -m app.main "$@"
fi
