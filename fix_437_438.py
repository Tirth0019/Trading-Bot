#!/usr/bin/env python3
"""Fix lines 437-438 indentation"""

with open('core/smart_money_concepts.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 437 (index 436) - add 4 spaces
if '# Bearish CHOCH: Must be a new LL' in lines[436]:
    lines[436] = '                        # Bearish CHOCH: Must be a new LL breaking below previous HL\r\n'
    print("✅ Fixed line 437")

# Fix line 438 (index 437) - add 4 spaces  
if 'if current.swing_type == SwingType.LL:' in lines[437]:
    lines[437] = '                        if current.swing_type == SwingType.LL:\r\n'
    print("✅ Fixed line 438")

with open('core/smart_money_concepts.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done! Testing import...")

try:
    import sys
    sys.path.insert(0, '.')
    from core.smart_money_concepts import MarketStructureAnalyzer
    print("✅ Import successful!")
except IndentationError as e:
    print(f"❌ Still has indentation error: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")
