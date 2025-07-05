import subprocess
import shutil
import os

# Script to revert a VMware virtual machine to a specific snapshot using vmrun

# --- Configuration ---
# Ensure vmrun is in your PATH or provide the full path to vmrun
VMRUN_COMMAND = "vmrun"

# --- Functions ---

def check_vmrun():
    """Checks if the vmrun command is available in the system PATH."""
    if shutil.which(VMRUN_COMMAND):
        return True
    else:
        print(f"Error: '{VMRUN_COMMAND}' command not found.")
        print("Please ensure VMware Workstation/Fusion is installed and "
              f"'{VMRUN_COMMAND}' is in your system's PATH.")
        print("Alternatively, you can set the full path to vmrun in the "
              "VMRUN_COMMAND variable within this script.")
        return False

def revert_snapshot(vmx_path, snapshot_name):
    """
    Reverts the specified VM to the given snapshot.

    Args:
        vmx_path (str): The full path to the .vmx file of the virtual machine.
        snapshot_name (str): The name of the snapshot to revert to.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    print(f"\nAttempting to revert to snapshot '{snapshot_name}' for VM '{vmx_path}'...")
    try:
        # Construct the command
        command = [VMRUN_COMMAND, "revertToSnapshot", vmx_path, snapshot_name]

        # Execute the command
        # We use capture_output=True to get stdout and stderr
        # text=True decodes them as strings
        # check=True will raise a CalledProcessError if vmrun returns a non-zero exit code
        process = subprocess.run(command, capture_output=True, text=True, check=False)

        if process.returncode == 0:
            print("\nSuccessfully reverted VM "
                  f"'{os.path.basename(vmx_path)}' to snapshot '{snapshot_name}'.")
            if process.stdout:
                print("vmrun output:\n", process.stdout)
            return True
        else:
            print(f"\nError: Failed to revert snapshot. '{VMRUN_COMMAND}' command returned an error.")
            print(f"Return code: {process.returncode}")
            if process.stdout:
                print("stdout:\n", process.stdout)
            if process.stderr:
                print("stderr:\n", process.stderr)
            print("\nCommon issues:")
            print("  - The snapshot name might be incorrect or case-sensitive.")
            print("  - The VM might be powered on (some versions of vmrun require the VM to be off for revert).")
            print("  - Insufficient permissions or the .vmx path is incorrect.")
            return False

    except FileNotFoundError:
        # This exception is for VMRUN_COMMAND itself not being found,
        # though check_vmrun() should catch this first.
        print(f"Error: The command '{VMRUN_COMMAND}' was not found. "
              "Please ensure it is installed and in your PATH.")
        return False
    except subprocess.CalledProcessError as e:
        # This exception is raised when check=True and vmrun returns non-zero.
        # Kept for completeness, though current check=False handles it manually.
        print(f"Error executing vmrun: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

# --- Main Script ---
if __name__ == "__main__":
    print("VMware Snapshot Reverter (Python)")
    print("---------------------------------")

    # 1. Check if vmrun is available
    if not check_vmrun():
        exit(1)

    # 2. Get user input for VM path
    vm_path_input = input("Enter the full path to the .vmx file of your virtual machine: ").strip()

    # Validate VM_PATH input
    if not vm_path_input:
        print("Error: VM path cannot be empty.")
        exit(1)

    if not os.path.isfile(vm_path_input):
        print(f"Error: VM configuration file not found at '{vm_path_input}'.")
        print("Please ensure the path is correct and the file exists.")
        exit(1)

    # 3. Get user input for Snapshot Name
    snapshot_name_input = input("Enter the name of the snapshot to revert to: ").strip()

    # Validate SNAPSHOT_NAME input
    if not snapshot_name_input:
        print("Error: Snapshot name cannot be empty.")
        exit(1)

    # 4. Confirm action
    print("\nYou are about to revert the VM at:")
    print(f"  VM Path: {vm_path_input}")
    print(f"  Snapshot: {snapshot_name_input}")
    print("")

    confirmation = input("Are you sure you want to proceed? (yes/no): ").strip().lower()

    if confirmation != "yes":
        print("Operation cancelled by the user.")
        exit(0)

    # 5. Execute the revert operation
    success = revert_snapshot(vm_path_input, snapshot_name_input)

    if success:
        exit(0)
    else:
        exit(1)

# --- Usage Example ---
#
# 1. Save this script as 'revert_vm.py'.
# 2. Make it executable (optional, can also run with `python revert_vm.py`):
#    chmod +x revert_vm.py
# 3. Run the script:
#    python revert_vm.py
#    or if executable:
#    ./revert_vm.py
#
# The script will then prompt you for:
#   - The full path to the .vmx file (e.g., /Users/username/Documents/Virtual Machines.localized/Windows 10.vmwarevm/Windows 10.vmx)
#   - The name of the snapshot you want to revert to (e.g., "Clean Install Snapshot")
#
# Example interaction:
#
# $ python revert_vm.py
# VMware Snapshot Reverter (Python)
# ---------------------------------
# Enter the full path to the .vmx file of your virtual machine: /path/to/your/vm.vmx
# Enter the name of the snapshot to revert to: MySnapshot
#
# You are about to revert the VM at:
#   VM Path: /path/to/your/vm.vmx
#   Snapshot: MySnapshot
#
# Are you sure you want to proceed? (yes/no): yes
#
# Attempting to revert to snapshot 'MySnapshot' for VM '/path/to/your/vm.vmx'...
# <vmrun command output, if any>
#
# Successfully reverted VM 'vm.vmx' to snapshot 'MySnapshot'.
#
# --- End of Script ---
