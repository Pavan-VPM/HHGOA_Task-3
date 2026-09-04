#!/usr/bin/env python3
"""
Convenience entrypoint wrapper pointing to main.py
"""
import sys
from main import main, demo_command

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default to running the full demo if no arguments provided
        demo_command()
    else:
        main()
