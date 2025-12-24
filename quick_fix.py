with open('core/smart_money_concepts.py', 'r') as f:
    content = f.read()

# Replace the problematic lines with correctly indented versions
content = content.replace(
    '                if trend_before == "uptrend":\r\n                # Bearish CHOCH',
    '                if trend_before == "uptrend":\r\n                    # Bearish CHOCH'
)

content = content.replace(
    '                # Bearish CHOCH: Must be a new LL breaking below previous HL\r\n                if current.swing_type == SwingType.LL:',
    '                    # Bearish CHOCH: Must be a new LL breaking below previous HL\r\n                    if current.swing_type == SwingType.LL:'
)

with open('core/smart_money_concepts.py', 'w') as f:
    f.write(content)

print("Fixed!")
