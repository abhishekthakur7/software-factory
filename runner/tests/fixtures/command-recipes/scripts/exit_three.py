#!/usr/bin/env python3
"""A recipe fixture that always fails with an exit code no catalogue expects."""
import sys

print("boom")
sys.exit(3)
