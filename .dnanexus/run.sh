#!/bin/bash
set -euo pipefail

exec /opt/conda/bin/aixportcmd.py "$@"
