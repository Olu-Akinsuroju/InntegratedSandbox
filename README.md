# VM-Based Malware Analysis Orchestrator

This project is a web-based interface designed to automate the process of malware analysis by orchestrating a virtual machine (VM) to safely execute and log suspicious files. As a Solution Architect, I designed this system to bridge the gap between a user-friendly web application and the complex, low-level environment of a sandboxed VM. It provides a clear, real-time stream of analysis logs and generates a concise, actionable report, demonstrating a practical solution to the challenge of safely analyzing potential threats.

**Note:** This project is currently in a proof-of-concept stage. The backend analysis script is designed to run on a local Windows machine with VMware, and the web interface is configured for deployment on Render. A known issue prevents the Render-deployed application from connecting to the local VM. This is a priority for future development.

## Table of Contents

*   [Problem Solved](#problem-solved)
*   [Key Features](#key-features)
*   [Tech Stack](#tech-stack)
*   [Installation](#installation)
*   [Usage](#usage)
*   [Roadmap](#roadmap)
*   [Contributing](#contributing)
*   [License](#license)
*   [Contact](#contact)

## Problem Solved

Analyzing potentially malicious files on a local machine poses a significant security risk. This project addresses that problem by providing a system to offload the execution and analysis of suspicious files to an isolated virtual machine. The architecture is designed to provide a safe, sandboxed environment for analysis while still delivering a seamless and informative user experience through a web-based interface.

## Key Features

*   **Remote Orchestration:** The system is built around the principle of remote orchestration, where a web interface can trigger and monitor a complex workflow on a separate machine.
*   **Real-time Log Streaming:** The FastAPI backend uses server-sent events (SSE) to stream analysis logs from the backend agent to the frontend, providing immediate feedback to the user.
*   **Decoupled Architecture:** The frontend (FastAPI on Render) and the backend (Python script on a local VM) are decoupled, allowing for independent development and scaling. This is a foundational architectural decision for building a resilient and maintainable system.
*   **Dynamic Reporting:** Upon completion of the analysis, the system generates a dynamic report that includes a threat assessment, malware family (if identified), and links to detailed log files (EVTX and CSV).
*   **Safe File Handling:** The application ensures that uploaded files are handled safely, with security checks to prevent directory traversal and other potential vulnerabilities.

## Tech Stack

*   **Frontend:**
    *   **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python.
    *   **Uvicorn:** A lightning-fast ASGI server, used to run the FastAPI application.
    *   **Jinja2:** A templating engine for Python, used to render the HTML frontend.
    *   **Server-Sent Events (SSE):** For real-time, unidirectional communication from the server to the client.
*   **Backend (Analysis Agent):**
    *   **Python:** The core language for the analysis script.
    *   **VMware VIX API (`vmrun`):** Used to programmatically control VMware virtual machines.
    *   **PowerShell:** For scripting actions within the Windows guest OS, such as exporting event logs.
*   **Deployment:**
    *   **Render:** A cloud platform for building and running applications. The FastAPI web interface is configured for deployment on Render.
    *   **GitHub Actions (Implied):** For continuous integration and deployment (CI/CD) to Render.

## Installation

### Prerequisites

*   A Windows machine with VMware Workstation or Player installed.
*   A Windows 10/11 virtual machine configured with Sysmon.
*   Python 3.8+ installed on both the host machine (for the FastAPI server) and the guest VM (if running Python scripts within it).

### Local Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Configure the analysis script:**
    *   Open `automate_sysmon_export_and_convert.py` and update the following variables to match your local VMware setup:
        *   `VMRUN`: The path to your `vmrun.exe` executable.
        *   `VMX_PATH`: The path to the `.vmx` file of your Windows guest VM.
        *   `GUEST_USER`: The username for the guest OS.
        *   `GUEST_PASS`: The password for the guest OS.

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the FastAPI server:**
    ```bash
    uvicorn main:app --reload
    ```
    The application will be available at `http://127.0.0.1:8000`.

## Usage

1.  **Start the FastAPI server** as described in the installation steps.
2.  **Open your web browser** and navigate to `http://127.0.0.1:8000`.
3.  **Drag and drop a file** onto the upload zone, or click to browse for a file.
4.  The application will upload the file and trigger the analysis script on the configured VM.
5.  You will see a real-time stream of the analysis logs.
6.  Once the analysis is complete, a report will be displayed with the results and links to download the log files.

## Roadmap

*   **Resolve Render Deployment Issue:** The top priority is to re-architect the communication between the web interface and the analysis agent to work in a cloud environment. This may involve:
    *   Using a message queue (e.g., RabbitMQ, Redis) to decouple the web server from the analysis agent.
    *   Creating a secure API endpoint on the analysis agent that can be accessed from the Render application.
*   **Enhance Analysis Capabilities:**
    *   Integrate additional analysis tools (e.g., Yara, VirusTotal API).
    *   Implement more sophisticated threat detection logic.
*   **Improve User Experience:**
    *   Add a history of previous scans.
    *   Provide more detailed and interactive reports.

## Contributing

Contributions are welcome! If you have suggestions for improvements, please open an issue or submit a pull request.

### Contribution Flow

1.  **Fork the repository.**
2.  **Create a new branch** for your feature or bug fix: `git checkout -b feature/your-feature-name`.
3.  **Make your changes** and commit them with a clear message.
4.  **Push your changes** to your fork: `git push origin feature/your-feature-name`.
5.  **Open a pull request** to the `main` branch of this repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

As the Solution Architect for this project, I am always open to discussing the design choices, architecture, and potential improvements. Please feel free to reach out with any questions or feedback.

*   **GitHub:** [Your GitHub Profile](https://github.com/it's me)
*   **Email:** your.email@example.com
