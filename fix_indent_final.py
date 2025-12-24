#!/usr/bin/env python3
"""Fix indentation in smart_money_concepts.py - CHOCH detection block"""

with open('core/smart_money_concepts.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 437-514 need to be indented by 4 spaces (they're inside the if statement on line 436)
# Line 436 (0-indexed 435): if trend_before == "uptrend":
# Lines 437-514 need to be indented

# Find the start and end of the block to indent
start_idx = 436  # Line 437 in editor (0-indexed)
end_idx = None

# Find where the CHOCH block ends (look for the BOS detection or elif)
for i in range(start_idx, min(start_idx + 100, len(lines))):
    if '# --- OPTIMIZED BOS Detection' in lines[i]:
        end_idx = i
        break
    if i > start_idx and lines[i].strip().startswith('elif trend_before'):
        end_idx = i
        break

if end_idx is None:
    end_idx = start_idx + 80  # Fallback

print(f"Indenting lines {start_idx + 1} to {end_idx} (editor line numbers)")

# Indent each line by adding 4 spaces
fixed_count = 0
for i in range(start_idx, end_idx):
    if lines[i].strip():  # Only indent non-empty lines
        # Add 4 spaces at the beginning
        lines[i] = '    ' + lines[i]
        fixed_count += 1

print(f"Fixed {fixed_count} lines")

# Write back
with open('core/smart_money_concepts.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Indentation fixed!")

# Test import
try:
    import sys
    sys.path.insert(0, '.')
    from core.smart_money_concepts import MarketStructureAnalyzer
    print("✅ Import successful!")
except Exception as e:
    print(f"❌ Import failed: {e}")
