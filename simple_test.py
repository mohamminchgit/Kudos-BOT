import sys
import os
sys.path.insert(0, 'src')

try:
    from services.giftcard import create_gift_card_image
    print("Import successful")
    
    result = create_gift_card_image("تست", "گیرنده", "پیام تست")
    print(f"Result: {result}")
    
    with open("test_result.txt", "w", encoding="utf-8") as f:
        f.write(f"Result: {result}")
        
except Exception as e:
    print(f"Error: {e}")
    with open("test_result.txt", "w", encoding="utf-8") as f:
        f.write(f"Error: {e}")
    import traceback
    traceback.print_exc()
