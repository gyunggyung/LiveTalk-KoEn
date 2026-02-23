import os
import threading
import queue
import sys
import time
import traceback
import warnings

# 환경 설정 (OpenMP 충돌 방지)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel
from flask import Flask, jsonify, render_template_string

# ==========================================
# ⚙️ 설정값
# ==========================================
MODEL_SIZE = "Systran/faster-distil-whisper-small.en"
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * 0.5)  # 0.5초 단위 청크
VOLUME_THRESHOLD = 0.0001
# ==========================================

audio_queue = queue.Queue()
transcribed_logs = []  # 전역 리스트 (텍스트 저장소)
app = Flask(__name__)

# ==========================================
# 🎨 웹 페이지 디자인 (생략)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-time Transcription</title>
    <style>
        body { 
            background-color: #121212; 
            color: #e0e0e0; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            padding: 20px; 
            margin: 0;
        }
        .container { max-width: 900px; margin: 0 auto; }
        #chat-box { 
            background-color: #1e1e1e; 
            border: 1px solid #333; 
            padding: 40px; 
            height: 60vh; 
            overflow-y: auto; 
            border-radius: 12px;
            font-size: 20px; 
            line-height: 1.8;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .log-entry { margin-bottom: 20px; color: #cccccc; }
        .btn-group { margin-top: 20px; display: flex; gap: 15px; justify-content: center; }
        button { padding: 15px 25px; cursor: pointer; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; color: white; transition: opacity 0.3s; }
        button:hover { opacity: 0.8; }
        .btn-copy { background-color: #3700b3; }
        .btn-trans { background-color: #018786; }
        .btn-clear { background-color: #cf6679; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <div id="chat-box">Waiting for audio...</div>
        <div class="btn-group">
            <button class="btn-copy" onclick="copyAll()">📋 전체 복사</button>
            <button class="btn-trans" onclick="window.open('https://translate.google.com', '_blank')">🌐 구글 번역기</button>
            <button class="btn-clear" onclick="clearScreen()">🗑️ 화면 비우기</button>
        </div>
    </div>
    <script>
        setInterval(fetchLogs, 1000);
        function fetchLogs() {
            fetch('/update')
                .then(response => response.json())
                .then(data => {
                    const box = document.getElementById('chat-box');
                    if (data.logs.length === 0) {
                        if (box.innerHTML.includes('<div class="log-entry">')) {
                             box.innerHTML = "Cleaned! Waiting for new audio...";
                        }
                        return;
                    }
                    const newHtml = data.logs.map(log => `<div class="log-entry">${log.text}</div>`).join('');
                    if (box.innerHTML !== newHtml) {
                        box.innerHTML = newHtml;
                        box.scrollTop = box.scrollHeight;
                    }
                });
        }
        function copyAll() {
            const text = document.getElementById('chat-box').innerText;
            navigator.clipboard.writeText(text).then(() => { alert("복사되었습니다!"); });
        }
        function clearScreen() {
            if(confirm("정말 모든 내용을 지우시겠습니까?")) {
                fetch('/clear').then(() => { document.getElementById('chat-box').innerHTML = "Resetting..."; });
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/update')
def update():
    return jsonify({'logs': transcribed_logs})

@app.route('/clear')
def clear_logs():
    global transcribed_logs
    transcribed_logs = []
    print("🧹 화면과 메모리가 초기화되었습니다.")
    return jsonify({'status': 'cleared'})

# ==========================================
# 백엔드 로직
# ==========================================
def get_default_wasapi_device(p):
    """pyaudiowpatch를 사용해 윈도우 루프백(스피커 출력 캡처) 장치 강제 탐색"""
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    print(f"🎤 Loopback found: {loopback['name']}")
                    return loopback
                    
        print(f"🎤 Loopback fallback: {default_speakers['name']}")
        return default_speakers
    except Exception as e:
        print(f"❌ 장치 검색 오류: {e}")
        return None

def record_audio_loop():
    p = pyaudio.PyAudio()
    device = get_default_wasapi_device(p)
    if device is None:
        print("❌ 시스템 오디오를 캡처할 수 없습니다.")
        return

    try:
        device_channels = device["maxInputChannels"]
        actual_mic_sr = int(device["defaultSampleRate"])
        
        # PyAudio 스트림 열기
        stream = p.open(format=pyaudio.paFloat32,
                        channels=device_channels,
                        rate=actual_mic_sr,
                        input=True,
                        input_device_index=device["index"],
                        frames_per_buffer=int(actual_mic_sr * 0.5))
                        
        while True:
            # 0.5초 단위로 수신
            data = stream.read(int(actual_mic_sr * 0.5), exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.float32)
            
            # 윈도우 채널 분리 (Mono 추출)
            if device_channels > 1:
                audio_array = np.reshape(audio_array, (-1, device_channels))
                audio_array = audio_array[:, 0]
                
            audio_queue.put((audio_array, actual_mic_sr))
            
    except Exception as e:
        print(f"녹음 오류: {e}")
    finally:
        p.terminate()

def process_audio_loop():
    print("Loading model...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print(f"✅ Web Server Running on http://127.0.0.1:5000")
    
    import scipy.signal
    accumulated_audio = np.array([], dtype=np.float32)
    silence_counter = 0
    
    while True:
        audio_data, mic_samplerate = audio_queue.get()
        
        # 1. 원본 해상도(48kHz 등)에서 16kHz로 리샘플링
        if mic_samplerate != SAMPLE_RATE:
            samples_count = int(len(audio_data) * SAMPLE_RATE / mic_samplerate)
            chunk_16k = scipy.signal.resample(audio_data, samples_count)
        else:
            chunk_16k = audio_data

        # 2. 볼륨 체크
        vol = np.abs(chunk_16k).mean()
        
        if vol < VOLUME_THRESHOLD:
            silence_counter += 1
            if silence_counter >= 2 and len(accumulated_audio) > 0:
                pass 
            else:
                continue
        else:
            silence_counter = 0

        # 3. 오디오 누적
        if vol >= VOLUME_THRESHOLD:
             accumulated_audio = np.concatenate((accumulated_audio, chunk_16k))
        
        # 4. 분석 진행 (실시간성을 위해 3초 단위 혹은 무음 1초(카운터 2) 도달 시 바로 번역)
        if len(accumulated_audio) >= SAMPLE_RATE * 3 or (silence_counter >= 2 and len(accumulated_audio) > 0):
            try:
                audio_array = accumulated_audio.copy()
                max_val = np.abs(audio_array).max()
                if max_val > 0:
                    audio_array = audio_array / max_val
                    
                # 신속한 처리를 위해 beam_size를 1로 낮춰도 됩니다 (정확도 vs 속도 조절)
                segments, info = model.transcribe(audio_array, beam_size=2, language="en", vad_filter=False, condition_on_previous_text=False)
                
                full_text = []
                for segment in segments:
                    text = segment.text.strip()
                    if text and len(text) > 1:  # 짧은 감탄사도 잡도록 조건 완화
                        full_text.append(text)
                
                if full_text:
                    final_text = ' '.join(full_text)
                    print(f"💬 {final_text}")
                    transcribed_logs.append({"text": final_text})
                    
            except Exception as e:
                print(f"변환 오류: {e}")
                
            accumulated_audio = np.array([], dtype=np.float32)
            silence_counter = 0

if __name__ == "__main__":
    t1 = threading.Thread(target=record_audio_loop, daemon=True)
    t1.start()
    
    t2 = threading.Thread(target=process_audio_loop, daemon=True)
    t2.start()
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)