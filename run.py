#!/usr/bin/env python3
"""FlowSpeak launcher.

Thin entry point so the app can be started with `python run.py`,
double-clicked, or frozen by PyInstaller. The real work lives in the
`flowspeak` package.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowspeak.app import main

if __name__ == "__main__":
    main()
