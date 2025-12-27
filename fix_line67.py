with open('core/backtester.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 67 (index 66)
lines[66] = '        print("\\n Configuration:")\\r\\n'

with open('core/backtester.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed line 67!")
