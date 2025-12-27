with open('core/backtester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all emoji characters with ASCII-safe alternatives
replacements = {
    '🚀': '',
    '📊': '',
    '📅': '',
    '✅': '',
    '❌': '',
    '⚠️': 'WARNING:',
    '💰': '',
    '📈': '',
    '📉': '',
    '🎯': '',
    '⏱️': '',
}

for emoji, replacement in replacements.items():
    content = content.replace(emoji, replacement)

with open('core/backtester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed Unicode issues in backtester.py!")
