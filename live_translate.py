import os
import threading
import queue
import time
import traceback
import warnings

# 환경 설정 (OpenMP 충돌 방지)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel
from flask import Flask, jsonify, render_template_string

# Python 3.13에서 cgi 모듈이 삭제되어 googletrans 호환성 문제가 발생하므로 임시 Mock 적용
import sys
if 'cgi' not in sys.modules:
    import types
    mock_cgi = types.ModuleType('cgi')
    mock_cgi.parse_header = lambda header: (header, {})
    sys.modules['cgi'] = mock_cgi

from googletrans import Translator

# ==========================================
# ⚙️ 설정값
# ==========================================
MODEL_SIZE = "Systran/faster-distil-whisper-small.en"
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * 0.5)  # 0.5초 단위 청크
VOLUME_THRESHOLD = 0.0001
# ==========================================

audio_queue = queue.Queue()
transcribed_logs = []  # 완료된 번역 로그 (Final)
current_draft = {"en": "", "ko": ""}  # 현재 실시간 작성중인 문장 (Draft)

app = Flask(__name__)

# Python 3.13 호환 패치
import sys
if 'cgi' not in sys.modules:
    import types
    mock_cgi = types.ModuleType('cgi')
    mock_cgi.parse_header = lambda header: (header, {})
    sys.modules['cgi'] = mock_cgi

from googletrans import Translator
translator = Translator()

# ==========================================
# 🎨 웹 페이지 디자인 (번역 및 실시간 Draft 포함)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Transcription & Translation</title>
    <style>
        body { 
            background-color: #121212; 
            color: #e0e0e0; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            padding: 20px; 
            margin: 0;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        #chat-box { 
            background-color: #1e1e1e; 
            border: 1px solid #333; 
            padding: 40px; 
            height: 65vh; 
            overflow-y: auto; 
            border-radius: 12px;
            font-size: 20px; 
            line-height: 1.6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            scroll-behavior: smooth;
        }
        .log-entry { margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .en-text { color: #aaaaaa; font-size: 18px; margin-bottom: 5px; }
        .ko-text { color: #ffffff; font-size: 24px; font-weight: bold; }
        
        /* 실시간으로 말하고 있는 중인 문장 (Draft) 효과 */
        .draft-entry {
            opacity: 0.7;
            border-bottom: 1px dashed #555;
        }
        .draft-entry .ko-text::after {
            content: ' ...';
            animation: blink 1s infinite steps(1);
        }
        @keyframes blink { 50% { opacity: 0; } }
        
        .btn-group { margin-top: 20px; display: flex; gap: 15px; justify-content: center; }
        button { padding: 15px 25px; cursor: pointer; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; color: white; transition: opacity 0.3s; }
        button:hover { opacity: 0.8; }
        .btn-copy { background-color: #3700b3; }
        .btn-clear { background-color: #cf6679; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <div id="chat-box">Waiting for audio to translate...</div>
        <div class="btn-group">
            <button class="btn-copy" onclick="copyAll()">📋 전체 복사</button>
            <button class="btn-clear" onclick="clearScreen()">🗑️ 화면 비우기</button>
        </div>
    </div>
    <script>
        setInterval(fetchLogs, 500); // 0.5초마다 빠르게 갱신 (실시간 체감 극대화)
        
        let lastDraftEn = '';
        
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
                    
                    const newHtml = data.logs.map(log => `
                        <div class="log-entry ${log.is_draft ? 'draft-entry' : ''}">
                            <div class="en-text">🇺🇸 ${log.en}</div>
                            <div class="ko-text">🇰🇷 ${log.ko}</div>
                        </div>
                    `).join('');
                    
                    if (box.innerHTML !== newHtml) {
                        const isAtBottom = box.scrollHeight - box.scrollTop <= box.clientHeight + 50;
                        box.innerHTML = newHtml;
                        if (isAtBottom) {
                            box.scrollTop = box.scrollHeight;
                        }
                    }
                });
        }
        function copyAll() {
            // draft 문구, 아이콘 빼고 텍스트 부분만 깔끔하게 복사하면 더 좋지만 지금은 전체 복사 유지
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
    # 확정된 로그에 실시간 작성중인 초안(Draft)을 더해서 웹으로 전송
    logs_to_send = transcribed_logs.copy()
    if current_draft['en']:
        draft_copy = current_draft.copy()
        draft_copy['is_draft'] = True
        logs_to_send.append(draft_copy)
    return jsonify({'logs': logs_to_send})

@app.route('/clear')
def clear_logs():
    global transcribed_logs, current_draft
    transcribed_logs = []
    current_draft = {"en": "", "ko": ""}
    print("🧹 화면과 메모리가 초기화되었습니다.")
    return jsonify({'status': 'cleared'})

# ==========================================
# 백엔드 로직
# ==========================================
def get_default_wasapi_device(p):
    """pyaudiowpatch 윈도우 루프백 장치 탐색"""
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    print(f"🎤 Loopback found: {loopback['name']}")
                    return loopback
                    
        return default_speakers
    except Exception as e:
        print(f"❌ 장치 검색 오류: {e}")
        return None

def record_audio_loop():
    p = pyaudio.PyAudio()
    device = get_default_wasapi_device(p)
    if device is None: return

    try:
        device_channels = device["maxInputChannels"]
        actual_mic_sr = int(device["defaultSampleRate"])
        
        stream = p.open(format=pyaudio.paFloat32,
                        channels=device_channels,
                        rate=actual_mic_sr,
                        input=True,
                        input_device_index=device["index"],
                        frames_per_buffer=int(actual_mic_sr * 0.5))
                        
        while True:
            data = stream.read(int(actual_mic_sr * 0.5), exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.float32)
            if device_channels > 1:
                audio_array = np.reshape(audio_array, (-1, device_channels))
                audio_array = audio_array[:, 0]
            audio_queue.put((audio_array, actual_mic_sr))
    except Exception as e:
        print(f"녹음 오류: {e}")
    finally:
        p.terminate()

def process_audio_loop():
    global current_draft, transcribed_logs
    print("Loading Faster-Whisper model...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print(f"✅ Web Server Running on http://127.0.0.1:5001")
    
    import scipy.signal
    accumulated_audio = np.array([], dtype=np.float32)
    silence_counter = 0
    last_translated_en = ""
    last_translated_ko = ""
    
    while True:
        audio_data, mic_samplerate = audio_queue.get()
        
        # 1. 16kHz 다운샘플링
        if mic_samplerate != SAMPLE_RATE:
            samples_count = int(len(audio_data) * SAMPLE_RATE / mic_samplerate)
            chunk_16k = scipy.signal.resample(audio_data, samples_count)
        else:
            chunk_16k = audio_data

        # 2. 볼륨 체크 및 무음 카운터 증가
        vol = np.abs(chunk_16k).mean()
        if vol < VOLUME_THRESHOLD:
            silence_counter += 1
        else:
            silence_counter = 0

        # 누적
        if len(accumulated_audio) > 0 or vol >= VOLUME_THRESHOLD:
             accumulated_audio = np.concatenate((accumulated_audio, chunk_16k))
        
        # 음성이 존재할 때만 분석 실행. 너무 짧은(0.5초 미만) 길이는 오인식 방지를 위해 스킵
        if len(accumulated_audio) >= SAMPLE_RATE * 0.5:
            try:
                audio_array = accumulated_audio.copy()
                max_val = np.abs(audio_array).max()
                if max_val > 0: audio_array = audio_array / max_val
                    
                # Draft 번역 (실시간)
                segments, _ = model.transcribe(audio_array, beam_size=2, language="en", vad_filter=False, condition_on_previous_text=False)
                full_text = [seg.text.strip() for seg in segments if len(seg.text.strip()) > 1]
                
                if full_text:
                    en_text = ' '.join(full_text)
                    
                    # 새롭게 단어가 추가되었을 때만 번역 API 호출 (API 제한/지연 방지)
                    if en_text != last_translated_en:
                        try:
                            # 번역기 품질 개선: 전체 문맥을 통째로 넣음
                            ko_trans = translator.translate(en_text, dest='ko').text
                        except Exception as e:
                            ko_trans = f"[번역 중...]"
                        
                        last_translated_en = en_text
                        last_translated_ko = ko_trans
                        
                    current_draft = {"en": en_text, "ko": last_translated_ko}
            except Exception as e:
                pass

        # 1초 이상 무음(silence_counter >= 2)이거나 버퍼가 너무 길어진 경우 (최대 12초), 문장을 마감(Commit)
        if (silence_counter >= 2 and len(accumulated_audio) > 0) or len(accumulated_audio) > SAMPLE_RATE * 12:
            if current_draft['en']:
                transcribed_logs.append({"en": current_draft['en'], "ko": current_draft['ko'], "is_draft": False})
                print(f"✅ [저장됨] {current_draft['en']} -> {current_draft['ko']}")
            
            # 버퍼 및 초기화
            accumulated_audio = np.array([], dtype=np.float32)
            current_draft = {"en": "", "ko": ""}
            last_translated_en = ""
            last_translated_ko = ""
            silence_counter = 0

if __name__ == "__main__":
    t1 = threading.Thread(target=record_audio_loop, daemon=True)
    t1.start()
    
    t2 = threading.Thread(target=process_audio_loop, daemon=True)
    t2.start()
    
    # 새 포트는 5001 사용 (기존 web.py 충돌 방지)
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
