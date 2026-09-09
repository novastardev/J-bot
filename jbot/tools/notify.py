import os
import platform
import time
from jbot.tools.registry import tool


@tool
def send_notification(title: str, message: str):
    """
    Send a desktop notification using plyer (cross-platform) or fall back to Termux,
    then platform-native commands, then a simple print. Silent fail if none work.

    Args:
        title: Notification title.
        message: Notification body/message.
    """
    # Try plyer first (works on Windows, macOS, Linux, Android, iOS, etc.)
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="J-bot", timeout=10)
        return f"Notification sent via plyer: {title}"
    except Exception:
        pass

    # Termux-specific fallback
    if os.getenv("TERMUX_VERSION"):
        try:
            subprocess = __import__("subprocess")
            subprocess.run(
                ["termux-notification", "--title", title, "--content", message],
                check=False,
                timeout=5,
            )
            return f"Notification sent via termux-notification: {title}"
        except Exception:
            pass

    # Platform-native fallbacks
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess = __import__("subprocess")
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{title}"',
                ],
                check=False,
                timeout=5,
            )
            return f"Notification sent via osascript: {title}"
        elif system == "Linux":
            subprocess = __import__("subprocess")
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                timeout=5,
            )
            return f"Notification sent via notify-send: {title}"
        elif system == "Windows":
            # Try PowerShell toast
            subprocess = __import__("subprocess")
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $toastXml = $template.GetXml()
            ($toastXml.GetElementsByTagName("text"))[0].AppendChild($toastXml.CreateTextNode("{title}")) > $null
            ($toastXml.GetElementsByTagName("text"))[1].AppendChild($toastXml.CreateTextNode("{message}")) > $null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($toastXml)
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("J-bot")
            $notifier.Show($toast)
            '''
            subprocess.run(
                ["powershell", "-Command", ps_script],
                check=False,
                timeout=5,
            )
            return f"Notification sent via PowerShell toast: {title}"
    except Exception:
        pass

    # Final fallback: just print to console (visible in terminal)
    print(f"[NOTIFICATION] {title}: {message}")
    return f"Notification printed to console: {title}"


@tool
def speak_text(text: str):
    """
    Speak text aloud using the best available TTS engine on the platform.
    Silent if no engine is found or user prefers silence.

    Tries:
    - pyttsx3 (offline, works on Windows, macOS, Linux)
    - gTTS + playsound (online, falls back if no net)
    - say (macOS)
    - espeak (Linux)
    - PowerShell SpeechSynthesizer (Windows)

    Args:
        text: Text to speak.
    """
    # Try pyttsx3 first (best offline cross-platform)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return f"Spoke via pyttsx3: {text[:50]}..."
    except Exception:
        pass

    # macOS say command
    if platform.system() == "Darwin":
        try:
            import subprocess
            subprocess.run(["say", text], check=False)
            return f"Spoke via macOS say: {text[:50]}..."
        except Exception:
            pass

    # Linux espeak
    if platform.system() == "Linux":
        try:
            import subprocess
            subprocess.run(["espeak", text], check=False)
            return f"Spoke via espeak: {text[:50]}..."
        except Exception:
            pass

    # Windows PowerShell SpeechSynthesizer
    if platform.system() == "Windows":
        try:
            import subprocess
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.Speak("{text}")
            '''
            subprocess.run(["powershell", "-Command", ps_script], check=False)
            return f"Spoke via PowerShell Synthesizer: {text[:50]}..."
        except Exception:
            pass

    # gTTS + playsound (online fallback)
    try:
        from gtts import gTTS
        from playsound import playsound
        import tempfile

        tts = gTTS(text=text, lang="slow")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            playsound(fp.name)
            os.unlink(fp.name)
        return f"Spoke via gTTS: {text[:50]}..."
    except Exception:
        pass

    return "TTS attempted but no engine available."