#!/usr/bin/env bash
# Minimal sherlock-proxyhat example.
#
#   PROXYHAT_API_KEY=ph_xxx ./examples/basic.sh johndoe
#
# Runs Sherlock through a US residential IP, rotating a fresh IP per connection
# (the default) so the hundreds of per-site checks are spread across many IPs.
set -euo pipefail

USERNAME="${1:-johndoe}"

# api_key defaults to $PROXYHAT_API_KEY and auto-selects an active sub-user.
# Everything after the --proxyhat-* flags is passed straight to `sherlock`.
sherlock-proxyhat \
  --proxyhat-country us \
  "$USERNAME" \
  --timeout 30
