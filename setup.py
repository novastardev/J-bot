import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE = ROOT_DIR / ".env.example"


def setup_wizard():
    print("==========================================")
    print("        J-BOT SETUP WIZARD")
    print("==========================================")
    print("Configure your LLM provider and API keys.\n")

    if ENV_FILE.exists():
        choice = input(".env file already exists. Overwrite? (y/N): ").strip().lower()
        if choice != "y":
            print("Setup cancelled. Existing .env preserved.")
            return

    print("\nChoose your LLM setup:")
    print("1. Custom / Remote API endpoint (e.g. Inception Labs, OpenAI, Groq, custom)")
    print("2. Connect to existing local LLM (Ollama / LM Studio already running)")
    print("3. Auto-setup local model (Install Ollama, pull model, and start service)")

    mode = input("\nEnter choice [1-3] (default 1): ").strip()

    base_url = "https://api.inceptionlabs.ai/v1"
    model = "mercury-2"
    api_key = ""

    if mode == "3":
        print("\nAuto-Setup Local Model (Ollama)")
        model_name = input("Enter model name to pull and run [llama3]: ").strip() or "llama3"
        print("\nChecking for Ollama installation...")
        if shutil.which("ollama") is None:
            print("Ollama not found. Attempting automatic installation...")
            install_cmd = "curl -fsSL https://ollama.com/install.sh | sh"
            res = subprocess.run(install_cmd, shell=True)
            if res.returncode != 0:
                print("Error: Automated Ollama installation failed. Please install Ollama manually from https://ollama.com/")
                sys.exit(1)
        print("Starting Ollama background service...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        print(f"Pulling model '{model_name}' (this may take a few minutes)...")
        pull_res = subprocess.run(["ollama", "pull", model_name])
        if pull_res.returncode != 0:
            print(f"Error: Failed to pull model '{model_name}'.")
            sys.exit(1)
        base_url = "http://localhost:11434/v1"
        model = model_name
        api_key = "local-ollama"
        print(f"Successfully configured local model '{model_name}' at {base_url}!")
    elif mode == "2":
        print("\nLocal LLM Selected (Make sure Ollama or LM Studio is running).")
        base_url = input("Enter local endpoint base URL [http://localhost:11434/v1]: ").strip() or "http://localhost:11434/v1"
        model = input("Enter model name [llama3]: ").strip() or "llama3"
        api_key = "local-dummy-key"
    else:
        base_url = input("Enter API base URL [https://api.inceptionlabs.ai/v1]: ").strip() or "https://api.inceptionlabs.ai/v1"
        model = input("Enter model name [mercury-2]: ").strip() or "mercury-2"
        api_key = input("Enter your API key: ").strip()

    smtp_host = ""
    smtp_port = "587"
    smtp_user = ""
    smtp_pass = ""

    configure_smtp = input("\nDo you wish to configure SMTP for mails? (y/N): ").strip().lower()
    if configure_smtp == "y":
        smtp_host = input("SMTP host (e.g. smtp.gmail.com): ").strip()
        smtp_port = input("SMTP port [587]: ").strip() or "587"
        smtp_user = input("SMTP user / email: ").strip()
        smtp_pass = input("SMTP password: ").strip()

    env_content = f"""# LLM Configuration
USER_LLM_API_KEY={api_key}
USER_LLM_BASE_URL={base_url}
USER_LLM_MODEL={model}

# SMTP Email Configuration
SMTP_HOST={smtp_host}
SMTP_PORT={smtp_port}
SMTP_USER={smtp_user}
SMTP_PASSWORD={smtp_pass}

# Runtime Settings
JBOT_SANDBOX=.
JBOT_MAX_STEPS=8
JBOT_TIMEOUT=60
JBOT_TEMPERATURE=0.2
JBOT_HISTORY_LIMIT=20
"""

    ENV_FILE.write_text(env_content, encoding="utf-8")
    print(f"\nConfiguration saved to {ENV_FILE}")
    print("\nSetup complete! Starting J-bot...\n")

    try:
        import subprocess
        subprocess.run([sys.executable, "-m", "jbot"])
    except Exception as e:
        print(f"Failed to start J-bot automatically: {e}")
        print("You can start it manually with: python -m jbot")


if __name__ == "__main__":
    setup_wizard()
