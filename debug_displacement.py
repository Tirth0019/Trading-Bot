
import subprocess
import sys
import re

def run_debug_displacement():
    # Run backtest for 20 days to ensure we catch CHOCH events
    # Added -u for unbuffered output to ensure we see logs immediately
    cmd = [sys.executable, "-u", "trading_bot.py", "--backtest", "--symbol", "XAUUSD", "--days", "20", "--debug"]
    print(f"🚀 Running Displacement Debug: {' '.join(cmd)}")
    print("----------------------------------------------------------------")
    print("Waiting for CHOCH signals (showing heartbeat '.' for every 50 lines)...")
    print("----------------------------------------------------------------")
    
    # Merge current environment with unbuffered flag
    import os
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8',
        env=env
    )
    
    # Regex to capture the specific displacement Log block
    # 🔍 CHOCH @ {time} | Dir: {dir}
    #    ATR_1M: {atr} | MaxMove: {move}
    #    Displacement: {val} (Req: 0.6)
    #    Result: PASS/FAIL
    
    capture_mode = False
    buffer = []
    line_count = 0
    
    try:
        for line in process.stdout:
            line_count += 1
            # Heartbeat
            if line_count % 50 == 0:
                print(".", end="", flush=True)

            # Check for start of block or key debug messages
            if "🔍 CHOCH @" in line or "🧠 Executor initialized" in line or "LOCK CHECK" in line or "🔒 EXECUTION LOCK" in line:
                if line_count >= 50: print() # Newline if we were printing dots
                capture_mode = True
                print(line.strip())
                continue
                
            if capture_mode:
                if "ATR_1M:" in line or "Displacement:" in line or "Result:" in line or "CHOCH" in line:
                    print(line.strip())
                    if "Result:" in line or "LOCK:" in line: # End of block markers
                        print("----------------------------------------------------------------")
                        capture_mode = False # Reset after result
                else:
                    # Generic indented check
                    if line.startswith("   "):
                        print(line.strip())
                    else:
                         # End capture if we hit a non-indented line that isn't part of the block
                        capture_mode = False

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
    finally:
        process.terminate()

if __name__ == "__main__":
    run_debug_displacement()
