#!/usr/bin/env python3
try:
    import src.handlers.ai_callbacks
    print("AI callbacks import successful")
except Exception as e:
    print(f"Error importing ai_callbacks: {e}")
    import traceback
    traceback.print_exc()
