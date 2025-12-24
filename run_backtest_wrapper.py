
import subprocess
import sys

def run_backtest():
    cmd = [sys.executable, "trading_bot.py", "--backtest", "--symbol", "XAUUSD", "--days", "5", "--debug"]
    print(f"Running command: {' '.join(cmd)}")
    
    with open("backend_log.txt", "w", encoding="utf-8") as f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )
        
        for line in process.stdout:
            print(line, end='')  # Echo to console
            f.write(line)        # Write to file
            f.flush()            # Ensure write
            
        process.wait()
        print(f"\nProcess finished with exit code {process.returncode}")

if __name__ == "__main__":
    run_backtest()
