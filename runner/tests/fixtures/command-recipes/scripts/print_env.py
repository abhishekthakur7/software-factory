#!/usr/bin/env python3
"""A recipe fixture that prints one environment variable it was given."""
import os

print(os.environ.get("SAFE_VAR", "<unset>"))
