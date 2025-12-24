#!/usr/bin/env python3
"""Fix indentation in smart_money_concepts.py"""

# Read the file
with open('core/smart_money_concepts.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 475 (index 474) - add 4 spaces of indentation
if lines[474].strip().startswith('elif trend_before =='):
    # Count current indentation
    current_indent = len(lines[474]) - len(lines[474].lstrip())
    # Should be indented 16 spaces (4 levels)
    lines[474] = ' ' * 16 + lines[474].lstrip()
    print(f"Fixed line 475: indentation changed from {current_indent} to 16 spaces")

# Write back
with open('core/smart_money_concepts.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Indentation fixed successfully!")
