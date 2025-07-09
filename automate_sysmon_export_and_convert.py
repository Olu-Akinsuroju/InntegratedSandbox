import os
import subprocess
import time
from datetime import datetime
import argparse # For command-line arguments
import json # For structured JSON output
import random # For mocking data

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
VMRUN = r"C:\Program Files (x86)\VMware\VMware Player\vmrun.exe"
VMX_PATH = r"C:\Users\Administrator\Documents\Virtual Machines\Windows 10 x64\windows 10 x64\Windows 10 x64.vmx"
GUEST_USER = "user"
GUEST_PASS = "boy"

SYSLOG_GUEST_EVTX = r"C:\Logs\sysmon_log.evtx"
SYSLOG_GUEST_CSV  = r"C:\Logs\sysmon_log.csv"

CONVERT_COMMAND = (
    r"Import-Module -Name Microsoft.PowerShell.Eventing; "
    r"Get-WinEvent -Path C:\Logs\sysmon_log.evtx | "
    r"Export-Csv -Path C:\Logs\sysmon_log.csv -NoTypeInformation"
)

HOST_LOG_DIR = "host_log_output"
if not os.path.isdir(HOST_LOG_DIR):
    os.makedirs(HOST_LOG_DIR, exist_ok=True)
# ────────────────────────────────────────────────────────────────────────────────

def run_in_guest(command_to_run_in_guest):
    print(f"[VMRUN] Executing in guest: {command_to_run_in_guest[:60]}...")
    cmd = [
        VMRUN, "-T", "ws",
        "-gu", GUEST_USER, "-gp", GUEST_PASS,
        "runProgramInGuest", VMX_PATH,
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-Command", command_to_run_in_guest
    ]
    try:
        subprocess.check_call(cmd)
        print(f"[VMRUN] Successfully executed in guest.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_ERROR] Failed to execute in guest. Error: {e}")
        raise

def copy_from_guest(guest_path, host_path):
    print(f"[VMRUN] Copying from guest '{guest_path}' to host '{host_path}'...")
    cmd = [
        VMRUN, "-T", "ws", "-gu", GUEST_USER, "-gp", GUEST_PASS,
        "copyFileFromGuestToHost", VMX_PATH,
        guest_path, host_path
    ]
    try:
        subprocess.check_call(cmd)
        print(f"[VMRUN] Successfully copied '{guest_path}' to '{host_path}'.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_ERROR] Failed to copy from guest. Error: {e}")
        raise

def ensure_vm_running():
    print("[VMRUN] Attempting to start VM if not already running...")
    try:
        subprocess.check_call([VMRUN, "-T", "ws", "start", VMX_PATH, "nogui"])
        print("[VMRUN] 'start' command issued. VM should be running.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_INFO] 'vmrun start' command resulted in an error (possibly already running): {e}. Proceeding...")

    print("[INFO] Waiting for VM to boot and guest tools to be ready (60 seconds)...")
    time.sleep(60)

def generate_mock_threat_data():
    """Generates mocked threat data for the report."""
    threat_levels = ["Low", "Medium", "High", "Critical", "Informational"]
    malware_families = ["Generic Trojan", "Ransomware.WannaCry", "Spyware.ZeuS", "Adware.Generic", "NotAPotato"]
    indicators_list = [
        ["Suspicious network connection to C2 server", "File masquerading as system process", "Registry modification for persistence"],
        ["Encrypted files with ransom note", "High CPU usage from unknown process"],
        ["Keystroke logging detected", "Attempts to access sensitive browser data"],
        ["Unwanted pop-up advertisements", "Browser homepage changed"],
        ["Benign file characteristics", "No malicious indicators found"]
    ]

    chosen_level = random.choice(threat_levels)
    family_index = threat_levels.index(chosen_level) if chosen_level in threat_levels else random.randint(0, len(malware_families)-1)

    return {
        "threatLevel": chosen_level,
        "threatFamily": malware_families[family_index % len(malware_families)], # Ensure index is valid
        "confidence": f"{random.randint(60, 99)}%",
        "indicators": random.choice(indicators_list) if chosen_level not in ["Low", "Informational"] else indicators_list[-1]
    }

def main(input_file_path: str):
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    print(f"--- Malware Analysis Script Started (File: {os.path.basename(input_file_path)}) ---")

    # Simulate analysis of the input file
    print(f"[STAGE] Initializing analysis for {os.path.basename(input_file_path)}...")
    time.sleep(2)
    print(f"[INFO] File size: {os.path.getsize(input_file_path) if os.path.exists(input_file_path) else 'N/A'} bytes")
    print(f"[INFO] File type detection (mock): {random.choice(['PE32 executable', 'PDF document', 'ZIP archive'])}")
    print("[STAGE_COMPLETE] Initial analysis phase complete.")

    # Existing VM-based log export logic (simulating part of a deeper analysis)
    host_evtx_path_str = ""
    host_csv_path_str = ""

    try:
        print("[STAGE] Performing deep environment analysis (VM-based log export)...")
        ensure_vm_running()
        print("[STAGE_COMPLETE] VM is presumed running for deep analysis.")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Define paths for EVTX and CSV files. These will be part of the report.
        # Ensure HOST_LOG_DIR is an absolute path or correctly relative for os.path.join
        abs_host_log_dir = os.path.abspath(HOST_LOG_DIR)
        host_evtx_path_str = os.path.join(abs_host_log_dir, f"sysmon_log_{timestamp}.evtx")
        host_csv_path_str = os.path.join(abs_host_log_dir, f"sysmon_log_{timestamp}.csv")

        print(f"[INFO] Target host EVTX path for detailed logs: {host_evtx_path_str}")
        print(f"[INFO] Target host CSV path for detailed logs: {host_csv_path_str}")

        print("[STAGE] Preparing guest for logs (creating C:\\Logs if not exists)...")
        run_in_guest("if (-not (Test-Path -Path C:\\Logs)) { New-Item -ItemType Directory -Path C:\\Logs -Force }")
        print("[STAGE_COMPLETE] Guest log directory ensured.")

        print("[STAGE] Exporting Sysmon EVTX from guest...")
        run_in_guest(f"wevtutil epl Microsoft-Windows-Sysmon/Operational {SYSLOG_GUEST_EVTX}")
        print("[INFO] Sysmon EVTX export command issued. Waiting 5s...")
        time.sleep(5)
        print("[STAGE_COMPLETE] Sysmon EVTX Exported.")

        print("[STAGE] Converting EVTX to CSV in guest...")
        run_in_guest(CONVERT_COMMAND)
        print("[INFO] EVTX to CSV conversion command issued. Waiting 5s...")
        time.sleep(5)
        print("[STAGE_COMPLETE] EVTX to CSV Converted.")

        print("[STAGE] Copying detailed logs to host...")
        copy_from_guest(SYSLOG_GUEST_EVTX, host_evtx_path_str)
        copy_from_guest(SYSLOG_GUEST_CSV, host_csv_path_str)
        print("[STAGE_COMPLETE] Detailed logs copied to host.")

        print("[AUTOMATION_SUCCESS] Deep environment analysis completed successfully.")

        # Generate mocked threat data
        threat_data = generate_mock_threat_data()

        # Prepare final JSON output
        scan_complete_data = {
            "event": "scan_complete",
            "data": {
                "evtxUrl": host_evtx_path_str, # Full path for backend to resolve
                "csvUrl": host_csv_path_str,   # Full path for backend to resolve
                "threatLevel": threat_data["threatLevel"],
                "threatFamily": threat_data["threatFamily"],
                "confidence": threat_data["confidence"],
                "indicators": threat_data["indicators"],
                "analyzedFile": os.path.basename(input_file_path)
            }
        }
        # Print the JSON object as a single line for easy parsing by the backend
        print(json.dumps(scan_complete_data))
        exit_code = 0

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] A VMRUN command failed: {e}")
        print("[AUTOMATION_FAILED] Script encountered an error during VMRUN execution.")
        exit_code = 1
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        print(f"[ERROR_DETAILS] Type: {type(e).__name__}, Args: {e.args}")
        import traceback
        print(f"[ERROR_TRACEBACK]\n{traceback.format_exc()}")
        print("[AUTOMATION_FAILED] Script encountered an unexpected error.")
        exit_code = 1
    finally:
        print("--- Malware Analysis Script Finished ---")

    return exit_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Malware Analysis Script (mocked).")
    parser.add_argument("input_file", help="Path to the file to be 'analyzed'.")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"[CRITICAL_ERROR] Input file not found: {args.input_file}")
        os._exit(2) # Specific exit code for file not found

    # os._exit is used to ensure the process exits with the specific code,
    # especially when called via subprocess from the FastAPI app.
    os._exit(main(args.input_file))
