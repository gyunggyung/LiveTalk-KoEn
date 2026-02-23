# 🎙️ LiveTalk-KoEn (Real-Time English to Korean Translation)

[🇰🇷 한국어 (Korean)](README.md) | [🇺🇸 English](README_EN.md)

**LiveTalk-KoEn** is a Python-based local application that captures system audio (from video conferences, YouTube videos, system sounds, etc.) in real-time, performs **English Speech-to-Text (STT)**, and instantly translates it into **Korean**, providing the results via a web UI.

## 🌟 Key Features

- 🔊 **Real-Time System Audio Capture**: Captures audio directly from your computer (Loopback) without needing a separate microphone. Ready to use instantly during video conferences (Zoom, Teams), lectures, and video streaming.
- ⚡ **Fast Speech Recognition (Faster-Whisper)**: Uses the `faster-distil-whisper-small.en` model, optimized for fast and accurate English-to-text conversion even on CPU environments.
- 🌐 **Real-Time Korean Translation**: Leverages the Google Translate API to instantly translate recognized English sentences into Korean with minimal latency. It also displays the real-time drafting process of sentences.
- 💻 **Web-Based Real-Time Monitoring**: View the translation results in real-time through an eye-friendly dark mode UI in your web browser.
- 📋 **Copy All Text Support**: Easily copy the entire translated text with a single click, perfect for taking meeting minutes or writing scripts.

## 🛠️ Prerequisites

- **OS**: Windows OS only (Uses Windows WASAPI API for system audio loopback capture).
- **Python**: Python 3.9 ~ 3.13

### Required Packages Installation
Run the following command in your command prompt or terminal to install the necessary packages:

```bash
pip install numpy faster-whisper flask googletrans==4.0.0-rc1 PyAudioWPatch scipy
```
*(Note: `googletrans` temporarily uses the rc version for stability, and `PyAudioWPatch` is used instead of the standard PyAudio for system audio capture.)*

## 🚀 How to Run

Follow these steps to use the real-time translation feature with the web UI:

1. Navigate to the project directory.
2. Run the translation server and web UI using the following command:

```bash
python live_translate.py
```

3. After running, open a web browser and connect to the local server address displayed in the terminal (`http://127.0.0.1:5001`).
4. Play media containing English audio on your computer, and real-time subtitles will be generated on the browser screen.
5. (Optional) If you want to run it in the background as a console text-only version without the web UI, run `python main.py`.

## 📂 File Structure & Description
- `live_translate.py`: The core executable file that runs audio capture, speech recognition, real-time translation logic, and the local web server (Flask). (⭐ Recommended)
- `main.py`: The backend core module used for testing STT logic in the console environment without a web server.
- `web.py` / `test_audio.py`: Scripts written for early testing purposes.

## 🔧 Troubleshooting
- **If you encounter the "OMP: Error #15: Initializing libiomp5md.dll..." error**:
  - Ensure that the code `os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"` is present and placed at the very top of `live_translate.py` and `main.py`.
- **If audio is not being captured**:
  - Check your Windows sound settings and ensure the default output device (speakers) is set correctly.

## 📝 License

This project is licensed under the [Apache License 2.0](LICENSE). Anyone is free to use, modify, and distribute it.
