#!/bin/bash

# Script to revert a VMware virtual machine to a specific snapshot using vmrun

# --- Configuration ---
# Ensure vmrun is in your PATH or provide the full path to vmrun
VMRUN_COMMAND="vmrun"

# --- Functions ---

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Main Script ---

echo "VMware Snapshot Reverter"
echo "------------------------"

# 1. Check if vmrun command is available
if ! command_exists "$VMRUN_COMMAND"; then
    echo "Error: '$VMRUN_COMMAND' command not found."
    echo "Please ensure VMware Workstation/Fusion is installed and '$VMRUN_COMMAND' is in your PATH."
    echo "Alternatively, you can set the full path to vmrun in the VMRUN_COMMAND variable within this script."
    exit 1
fi

# 2. Get user input for VM path
read -p "Enter the full path to the .vmx file of your virtual machine: " VM_PATH

# Validate VM_PATH input
if [ -z "$VM_PATH" ]; then
    echo "Error: VM path cannot be empty."
    exit 1
fi

if [ ! -f "$VM_PATH" ]; then
    echo "Error: VM configuration file not found at '$VM_PATH'."
    echo "Please ensure the path is correct and the file exists."
    exit 1
fi

# 3. Get user input for Snapshot Name
read -p "Enter the name of the snapshot to revert to: " SNAPSHOT_NAME

# Validate SNAPSHOT_NAME input
if [ -z "$SNAPSHOT_NAME" ]; then
    echo "Error: Snapshot name cannot be empty."
    exit 1
fi

# 4. Confirm action
echo ""
echo "You are about to revert the VM at:"
echo "  VM Path: $VM_PATH"
echo "  Snapshot: $SNAPSHOT_NAME"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " CONFIRMATION

if [[ "$CONFIRMATION" != "yes" ]]; then
    echo "Operation cancelled by the user."
    exit 0
fi

# 5. Execute the vmrun command
echo ""
echo "Attempting to revert to snapshot '$SNAPSHOT_NAME' for VM '$VM_PATH'..."

"$VMRUN_COMMAND" revertToSnapshot "$VM_PATH" "$SNAPSHOT_NAME"

# 6. Check the exit status of the vmrun command
if [ $? -eq 0 ]; then
    echo ""
    echo "Successfully reverted VM '$VM_PATH' to snapshot '$SNAPSHOT_NAME'."
else
    echo ""
    echo "Error: Failed to revert snapshot. '$VMRUN_COMMAND' command returned an error."
    echo "Please check the vmrun output above for more details."
    echo "Common issues:"
    echo "  - The snapshot name might be incorrect or case-sensitive."
    echo "  - The VM might be powered on (some versions of vmrun require the VM to be off for revert)."
    echo "  - Insufficient permissions."
    exit 1
fi

exit 0

# --- Usage Example ---
#
# 1. Save this script as 'revert_vm.sh'.
# 2. Make it executable: chmod +x revert_vm.sh
# 3. Run the script: ./revert_vm.sh
#
# The script will then prompt you for:
#   - The full path to the .vmx file (e.g., /Users/username/Documents/Virtual Machines.localized/Windows 10.vmwarevm/Windows 10.vmx)
#   - The name of the snapshot you want to revert to (e.g., "Clean Install Snapshot")
#
# Example interaction:
#
# $ ./revert_vm.sh
# VMware Snapshot Reverter
# ------------------------
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
# <vmrun command output>
#
# Successfully reverted VM '/path/to/your/vm.vmx' to snapshot 'MySnapshot'.
#
# --- End of Script ---
