# Host-side automation script: automate_sysmon_export_and_convert.py
# ----------------------------------------------------------
# This script exports Sysmon logs from the guest VM, converts the .evtx to CSV inside the VM,
# then copies both the .evtx and .csv files back to the host.

import os
import subprocess
import time
from datetime import datetime

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
VMX_PATH = r"C:\Users\HP\Documents\Virtual Machines\Windows 10 x64\Windows 10 x64.vmx"
GUEST_USER = "user"
GUEST_PASS = "boy"
SNAPSHOT = "stage 8.7"

# Guest paths
SYSLOG_GUEST_EVTX = r"C:\Logs\sysmon_log.evtx"      # exported from event log
SYSLOG_GUEST_CSV  = r"C:\Logs\sysmon_log.csv"       # will be created

# PowerShell conversion command inside guest
CONVERT_COMMAND = (
    r"Import-Module -Name Microsoft.PowerShell.Eventing; "
    r"Get-WinEvent -Path C:\Logs\sysmon_log.evtx | "
    r"Export-Csv -Path C:\Logs\sysmon_log.csv -NoTypeInformation"
)

# Host output directory
# Changed to a relative path for consistency with main.py and Render deployment
HOST_LOG_DIR = "host_log_output"
if not os.path.isdir(HOST_LOG_DIR):
    os.makedirs(HOST_LOG_DIR, exist_ok=True)
# ────────────────────────────────────────────────────────────────────────────────

def run_in_guest(command_to_run_in_guest):
    """Execute a PowerShell command in the VM guest."""
    print(f"[VMRUN] Executing in guest: {command_to_run_in_guest[:50]}...") # Log partial command
    cmd = [
        VMRUN, "-T", "ws",
        "-gu", GUEST_USER, "-gp", GUEST_PASS,
        "runProgramInGuest", VMX_PATH,
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-Command", command_to_run_in_guest
    ]
    try:
        # Capture output for better logging, though check_call doesn't return it directly
        # For Popen, you'd use process.communicate()
        # Using check_call for simplicity as the original script did
        subprocess.check_call(cmd)
        print(f"[VMRUN] Successfully executed in guest.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_ERROR] Failed to execute in guest. Error: {e}")
        # Potentially re-raise or handle if critical
        raise


def copy_from_guest(guest_path, host_path):
    """Copy file from the VM guest to the host."""
    print(f"[VMRUN] Copying from guest '{guest_path}' to host '{host_path}'...")
    cmd = [
        VMRUN, "-T", "ws",
        "-gu", GUEST_USER, "-gp", GUEST_PASS,
        "copyFileFromGuestToHost", VMX_PATH,
        guest_path, host_path
    ]
    try:
        subprocess.check_call(cmd)
        print(f"[VMRUN] Successfully copied '{guest_path}' to '{host_path}'.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_ERROR] Failed to copy from guest. Error: {e}")
        # Potentially re-raise or handle
        raise

def revert_and_start():
    """Revert VM to snapshot and ensure it's running."""
    print(f"[VMRUN] Reverting to snapshot '{SNAPSHOT}'...")
    try:
        subprocess.check_call([VMRUN, "-T", "ws", "revertToSnapshot", VMX_PATH, SNAPSHOT])
        print(f"[VMRUN] Successfully reverted to snapshot '{SNAPSHOT}'.")
    except subprocess.CalledProcessError as e:
        print(f"[VMRUN_ERROR] Failed to revert to snapshot. Error: {e}")
        raise

    print(f"[VMRUN] Starting VM '{VMX_PATH}'...")
    try:
        subprocess.check_call([VMRUN, "-T", "ws", "start", VMX_PATH])
        print(f"[VMRUN] VM started successfully.")
    except subprocess.CalledProcessError as e:
        # It's possible the VM is already running, vmrun start might error in that case.
        # A more robust check would be to use `vmrun list` and see if it's powered on.
        # For now, we'll print the error and continue, assuming it might be a non-critical issue.
        print(f"[VMRUN_WARNING] 'vmrun start' failed. This might be okay if VM was already running. Error: {e}")
        # Check if VM is running, if not, then it's a critical error
        # This is a placeholder for a more robust check
        print("[VMRUN] Assuming VM is running or attempting to continue. Waiting for guest OS to boot...")


    # Increased sleep time to ensure guest OS is fully booted and services are ready
    print("[INFO] Waiting for VM to boot and guest tools to be ready (60 seconds)...")
    time.sleep(60) # Increased wait time


def main():
    # Ensure print statements are flushed so they appear in Flask stream
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    print("--- VM Automation Script Started ---")

    # Prepare
    print("[STAGE] Preparation: Reverting to snapshot and starting VM...")
    try:
        revert_and_start()
    except Exception as e:
        print(f"[CRITICAL_ERROR] Failed during VM revert/start: {e}. Aborting.")
        return 1 # Indicate failure
    print("[STAGE_COMPLETE] VM Reverted and Started.")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # These paths will be used by the script and printed out for the Flask app to potentially parse
    global host_evtx_path, host_csv_path # Make them global to be accessible in finally block if needed
    host_evtx_path = os.path.join(HOST_LOG_DIR, f"sysmon_log_{timestamp}.evtx")
    host_csv_path  = os.path.join(HOST_LOG_DIR, f"sysmon_log_{timestamp}.csv")

    print(f"[INFO] Target host EVTX path: {host_evtx_path}")
    print(f"[INFO] Target host CSV path: {host_csv_path}")

    try:
        # Export Sysmon log
        print("[STAGE] Exporting Sysmon EVTX inside guest...")
        # Ensure the C:\Logs directory exists in the guest
        run_in_guest(f"if (-not (Test-Path -Path C:\\Logs)) {{ New-Item -ItemType Directory -Path C:\\Logs -Force }}")
        run_in_guest(f"wevtutil epl Microsoft-Windows-Sysmon/Operational {SYSLOG_GUEST_EVTX}")
        print("[INFO] Sysmon EVTX export command issued.")
        # Add a check to see if the file was created in guest, or rely on copy failing
        time.sleep(5) # Give some time for the export to complete
        print("[STAGE_COMPLETE] Sysmon EVTX Exported.")

        # Convert EVTX to CSV inside guest
        print("[STAGE] Converting EVTX to CSV inside guest...")
        run_in_guest(CONVERT_COMMAND)
        print("[INFO] EVTX to CSV conversion command issued.")
        time.sleep(5) # Give some time for the conversion to complete
        print("[STAGE_COMPLETE] EVTX to CSV Converted.")

        # Copy EVTX and CSV to host
        print("[STAGE] Copying files to host...")
        print(f"[INFO] Copying EVTX to host: {host_evtx_path}")
        copy_from_guest(SYSLOG_GUEST_EVTX, host_evtx_path)

        print(f"[INFO] Copying CSV to host: {host_csv_path}")
        copy_from_guest(SYSLOG_GUEST_CSV, host_csv_path)
        print("[STAGE_COMPLETE] Files Copied to Host.")

        print("[AUTOMATION_SUCCESS] All operations completed successfully.")
        print(f"EVTX_FILE:{host_evtx_path}") # For easy parsing by frontend
        print(f"CSV_FILE:{host_csv_path}")   # For easy parsing by frontend

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] A VMRUN command failed: {e}")
        print("[AUTOMATION_FAILED] Automation script encountered an error during VMRUN execution.")
        return 1 # Indicate failure
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        print("[AUTOMATION_FAILED] Automation script encountered an unexpected error.")
        return 1 # Indicate failure
    finally:
        print("--- VM Automation Script Finished ---")

    return 0 # Indicate success

if __name__ == "__main__":
    exit_code = main()
    # The exit code will be picked up by Popen.wait() in the Flask app
    # The SCRIPT_DONE or SCRIPT_ERROR messages in Flask app are more for client-side logic
    os._exit(exit_code) # Use os._exit to prevent SystemExit from being caught if script is imported
