---
name: Bug report
about: Create a report to help us improve
title: "[BUG] Render Deployment Fails to Connect to Local VM"
labels: bug, deployment
assignees: ''

---

**Describe the bug**
The application is designed with a decoupled architecture where a FastAPI frontend (deployed on Render) communicates with a backend analysis agent running on a local Windows VM. The communication is initiated via `httpx` requests from the FastAPI backend to the agent. This architecture fails in the Render environment because the Render service cannot resolve or connect to the local IP address of the VM.

**To Reproduce**
Steps to reproduce the behavior:
1. Deploy the FastAPI application to Render using the provided `render.yaml` file.
2. Access the web interface and upload a file for analysis.
3. The application will attempt to connect to the `AGENT_URL` specified in `main.py` (e.g., `http://ec2-13-51-207-164.eu-north-1.compute.amazonaws.com:8000`).
4. The connection will fail, and an error will be logged in the Render console.

**Expected behavior**
The FastAPI application on Render should be able to communicate with the analysis agent to trigger a scan and stream the results.

**Current behavior**
The application fails to connect to the analysis agent, and the analysis never starts. The user sees an error in the web interface.

**Screenshots**
N/A

**Desktop (please complete the following information):**
 - OS: N/A (Render environment)
 - Browser: N/A
 - Version: N/A

**Smartphone (please complete the following information):**
 - Device: N/A
 - OS: N/A
 - Browser: N/A
 - Version: N/A

**Additional context**
This is a known architectural issue. The `automate_sysmon_export_and_convert.py` script is fundamentally incompatible with the Render environment because it relies on local VMware `vmrun` commands. To fix this, we need to re-architect the communication layer between the frontend and the backend.

**Possible Solutions**
- **Message Queue:** Implement a message queue (e.g., RabbitMQ, Redis) to decouple the web server from the analysis agent. The Render app would publish a job to the queue, and the local agent would subscribe to it.
- **Secure API Endpoint:** Expose a secure API endpoint on the analysis agent that can be accessed from the Render application. This would require a secure way to expose the local agent to the internet (e.g., using a tunneling service like ngrok for development, or a proper VPN/firewall configuration for production).
- **Containerize the Agent:** A more advanced solution would be to containerize the analysis agent and run it in a cloud environment that supports nested virtualization, but this is a significant undertaking.
