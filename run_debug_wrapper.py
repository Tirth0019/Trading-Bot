
import subprocess
import sys

def run_debug():
    cmd = [sys.executable, "debug_step_by_step.py"]
    print(f"Running command: {' '.join(cmd)}")
    
    with open("debug_log.txt", "w", encoding="utf-8") as f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            print(line, end='')
            f.write(line)
            f.flush()
            
        process.wait()
        print(f"\nProcess finished with exit code {process.returncode}")

if __name__ == "__main__":
    run_debug()
