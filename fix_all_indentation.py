#!/usr/bin/env python3
"""Fix all indentation issues in the CHOCH detection block"""

# Read the file
with open('core/smart_money_concepts.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# We need to indent everything from line 437 onwards that's part of the CHOCH detection
# until we hit the BOS detection section

# Lines that need fixing (0-indexed):
# 437 (438 in editor): if current.swing_type == SwingType.LL:
# and all subsequent lines in the CHOCH block need proper indentation

# The pattern: after "if trend_before == "uptrend":" on line 436,
# everything should be indented by 4 more spaces (20 total)

start_line = 437  # 0-indexed (line 438 in editor)
end_line = 514    # Approximate end of CHOCH block (before BOS detection)

# Find where the CHOCH block actually ends (look for BOS detection comment)
for i in range(start_line, min(start_line + 100, len(lines))):
    if '# --- OPTIMIZED BOS Detection' in lines[i]:
        end_line = i
        break

print(f"Fixing indentation from line {start_line+1} to {end_line}")

# Fix each line in the CHOCH detection block
for i in range(start_line, end_line):
    line = lines[i]
    if line.strip():  # Only process non-empty lines
        # Count current indentation
        current_indent = len(line) - len(line.lstrip())
        # Add 4 spaces to current indentation
        lines[i] = ' ' * (current_indent + 4) + line.lstrip()

print(f"Fixed {end_line - start_line} lines")

# Write back
with open('core/smart_money_concepts.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Indentation fixed successfully!")
