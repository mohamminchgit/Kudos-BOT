import sys
import os
import traceback

# Set up path
sys.path.insert(0, 'src')

print("Testing giftcard creation...")

try:
    from services.giftcard import create_gift_card_image
    print("Import successful")
    
    # Test with simple parameters
    result = create_gift_card_image("Test Sender", "Test Receiver", "This is a test message")
    
    if result:
        print(f"Success! File created at: {result}")
        print(f"File exists: {os.path.exists(result)}")
    else:
        print("Function returned None")
        
except Exception as e:
    print(f"Error occurred: {e}")
    print("Full traceback:")
    traceback.print_exc()

print("Test completed.")
