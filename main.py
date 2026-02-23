import os

# [핵심 수정] 라이브러리 충돌 방지 (OpenMP 에러 해결)
# 반드시 다른 라이브러리 import보다 먼저 작성해야 합니다.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel
import threading
import queue
import sys
import time
import traceback

# ==========================================
# ⚙️ 설정값
# ==========================================
MODEL_SIZE = "Systran/faster-distil-whisper-small.en" 
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * 0.5)  # 0.5초 단위 청크
VOLUME_THRESHOLD = 0.0001
# ==========================================

audio_queue = queue.Queue()

def get_default_wasapi_device(p):
    """pyaudiowpatch를 사용해 윈도우 루프백(스피커 출력 캡처) 장치 탐색"""
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

def load_stt_model():
    print(f"Loading model '{MODEL_SIZE}' on CPU...")
    try:
        # compute_type="int8"로 CPU 속도 최적화
        model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print("✅ Model loaded successfully!")
        return model
    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        sys.exit(1)

def record_audio_loop():
    """녹음 스레드 - PyAudio WASAPI Loopback"""
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
            
            # byte를 float32 numpy array로 변환
            audio_array = np.frombuffer(data, dtype=np.float32)
            
            # 채널이 2개 이상이면 첫 번째 채널(Mono)만 추출하여 노이즈 방지
            if device_channels > 1:
                audio_array = np.reshape(audio_array, (-1, device_channels))
                audio_array = audio_array[:, 0]
                
            audio_queue.put((audio_array, actual_mic_sr))
            
    except Exception as e:
        print(f"❌ 녹음 스레드 오류: {e}")
        traceback.print_exc()
    finally:
        p.terminate()

def process_audio_loop(model):
    """처리 스레드"""
    print("📝 Ready to transcribe... (재생되는 소리가 없으면 대기합니다)")
    import scipy.signal
    
    accumulated_audio = np.array([], dtype=np.float32)
    silence_counter = 0

    while True:
        audio_data, mic_samplerate = audio_queue.get()
        # soundcard record returns shape: (frames, channels). Extract the first channel properly, DON'T just flatten it into chaos.
        if audio_data.ndim == 2:
            single_channel_data = audio_data[:, 0]
        else:
            single_channel_data = audio_data
            
        chunk_data = single_channel_data.astype(np.float32)

        # 1. 원본 해상도(48kHz 등)에서 16kHz로 리샘플링
        if mic_samplerate != SAMPLE_RATE:
            samples_count = int(len(chunk_data) * SAMPLE_RATE / mic_samplerate)
            chunk_16k = scipy.signal.resample(chunk_data, samples_count)
        else:
            chunk_16k = chunk_data

        # 2. 볼륨 체크
        vol = np.abs(chunk_16k).mean()
        
        if vol < VOLUME_THRESHOLD:
            silence_counter += 1
            # 2번 연속(약 10초) 무음이 지속되면 그동안 쌓인 걸 처리
            if silence_counter >= 2 and len(accumulated_audio) > 0:
                pass # 아래 처리 블록으로 넘어감
            else:
                continue
        else:
            silence_counter = 0
            
        # 3. 오디오 누적 (문장 단위 인식을 위해)
        if vol >= VOLUME_THRESHOLD:
             accumulated_audio = np.concatenate((accumulated_audio, chunk_16k))
        
        # 4. 버퍼가 너무 길어지면 (예: 15초 이상) 강제 분석, 
        #    혹은 무음 누적으로 처리 조건 달성 시 분석
        if len(accumulated_audio) >= SAMPLE_RATE * 15 or (silence_counter >= 2 and len(accumulated_audio) > 0):
            try:
                audio_array = accumulated_audio.copy()
                
                # 디버깅용: 현재 들어온 오디오를 wav 파일로 저장하여 깨져있는지 확인
                import scipy.io.wavfile
                scipy.io.wavfile.write("debug_audio.wav", SAMPLE_RATE, audio_array)
                print("💾 Saved debug_audio.wav for inspection.")
                
                # 정규화
                max_val = np.abs(audio_array).max()
                if max_val > 0:
                    audio_array = audio_array / max_val
                    
                segments, info = model.transcribe(audio_array, beam_size=5, language="en", vad_filter=False, condition_on_previous_text=False)
                
                full_text = []
                for segment in segments:
                    text = segment.text.strip()
                    if text and len(text) >= 2:
                        full_text.append(text)
                
                if full_text:
                    print(f"▶ {' '.join(full_text)}")
                    
            except Exception as e:
                print(f"변환 오류: {e}")
                
            # 분석 후 버퍼 정리
            accumulated_audio = np.array([], dtype=np.float32)
            silence_counter = 0

if __name__ == "__main__":
    model = load_stt_model()
    
    # 데몬 스레드로 설정하여 메인 프로그램 종료 시 같이 죽도록 설정
    recorder_thread = threading.Thread(target=record_audio_loop, daemon=True)
    recorder_thread.start()
    
    try:
        process_audio_loop(model)
    except KeyboardInterrupt:
        print("\n🛑 프로그램 종료.")