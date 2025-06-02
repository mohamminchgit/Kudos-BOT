"""
این اسکریپت خطوط مشکل‌دار را در فایل ai.py نمایش می‌دهد
"""

with open("src/services/ai.py", 'r', encoding='utf-8') as file:
    lines = file.readlines()

# چاپ خطوط حول 302
print("=== خطوط حول 302 ===")
for i in range(298, 308):
    print(f"{i+1}: {repr(lines[i])}")

# چاپ خطوط حول 428
print("\n=== خطوط حول 428 ===")
for i in range(424, 434):
    print(f"{i+1}: {repr(lines[i])}") 