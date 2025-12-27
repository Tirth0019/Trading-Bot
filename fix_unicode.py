with open('core/trading_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the emoji print statement
content = content.replace(
    'print("🧠 Executor initialized", id(self))',
    'print("Executor initialized", id(self))'
)

# Also fix other emoji prints that might cause issues
content = content.replace('🎯 CHOCH detected', 'CHOCH detected')
content = content.replace('✅ BOS confirmed', 'BOS confirmed')
content = content.replace('⏸️', '')
content = content.replace('🔒', '')

with open('core/trading_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed Unicode encoding issues!")
