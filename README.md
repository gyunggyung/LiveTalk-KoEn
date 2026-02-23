# 🎙️ LiveTalk-KoEn (Real-Time English to Korean Translation)

[🇰🇷 한국어 (Korean)](README.md) | [🇺🇸 English](README_EN.md)

**LiveTalk-KoEn**은 컴퓨터에서 재생되는 오디오(화상 회의, 유튜브 영상, 시스템 사운드 등)를 실시간으로 인식하여 **영어 음성을 인식(STT)**하고, 이를 **한국어로 즉시 번역**하여 웹 UI로 제공하는 파이썬 기반의 로컬 어플리케이션입니다.

## 🌟 주요 기능

- 🔊 **실시간 시스템 오디오 캡처**: 별도의 마이크 입력 없이 컴퓨터에서 재생되는 소리(Loopback)를 직접 분석합니다. 화상 회의(Zoom, Teams), 강의, 영상 시청 중 즉시 사용 가능합니다.
- ⚡ **빠른 음성 인식 (Faster-Whisper)**: CPU 환경에서도 최적화된 속도로 동작하는 `faster-distil-whisper-small.en` 모델을 사용하여 영어 음성을 텍스트로 고속 변환합니다.
- 🌐 **실시간 한국어 번역**: 구글 번역 API를 활용하여 인식된 영어 문장을 지연을 최소화하여 즉각적으로 한국어로 번역합니다. 초안(Draft) 작성 과정도 실시간으로 보여줍니다.
- 💻 **웹 기반 실시간 모니터링**: 브라우저를 통해 눈이 편안한 다크 모드 UI 환경에서 번역 결과를 실시간으로 확인할 수 있습니다.
- 📋 **전체 텍스트 복사 지원**: 회의록이나 스크립트 작성에 용이하도록 번역된 내용을 원클릭으로 전체 복사할 수 있습니다.

## 🛠️ 요구 사항 (Prerequisites)

- **OS**: 윈도우(Windows) 운영체제 전용 (시스템 오디오 캡처용 Loopback은 Windows WASAPI API를 사용합니다)
- **Python**: Python 3.9 ~ 3.13

### 필수 패키지 설치
명령 프롬프트 혹은 터미널에서 아래 명령어를 실행하여 필요한 패키지를 설치합니다:

```bash
pip install numpy faster-whisper flask googletrans==4.0.0-rc1 PyAudioWPatch scipy
```
*(참고: `googletrans`는 임시로 rc 버전을 사용해야 오류가 적으며, 시스템 오디오 캡처를 위해 일반 PyAudio 대신 `PyAudioWPatch`를 사용합니다.)*

## 🚀 사용 방법 (How to Run)

웹 UI와 함께 실시간 번역 기능을 사용하려면 다음 단계를 따르세요.

1. 프로젝트 디렉토리로 이동합니다.
2. 아래 명령어를 통해 번역 서버와 웹 UI를 실행합니다.

```bash
python live_translate.py
```

3. 실행 후 터미널에 표시되는 로컬 서버 주소(`http://127.0.0.1:5001`)로 웹 브라우저를 통해 접속합니다.
4. 컴퓨터에서 영어 음성이 포함된 미디어를 재생하면, 브라우저 화면에 실시간으로 자막이 생성됩니다.
5. (선택) 웹 UI 없이 백그라운드에서 콘솔 텍스트 전용으로 실행하고 싶다면 `python main.py`를 실행하세요.

## 📂 파일 구조 및 설명
- `live_translate.py`: 오디오 캡처, 음성 인식, 실시간 번역 로직 및 로컬 웹 서버(Flask)를 모두 구동하는 핵심 실행 파일입니다. (⭐ 추천 실행 파일)
- `main.py`: 웹 서버 없이 콘솔 환경에서 STT 로직만을 테스트할 때 사용하는 백엔드 코어 모듈입니다.
- `web.py` / `test_audio.py`: 초기 테스트 용도로 작성된 스크립트들입니다.

## 🔧 문제 해결 (Troubleshooting)
- **"OMP: Error #15: Initializing libiomp5md.dll..." 오류 발생 시**:
  - `live_translate.py` 와 `main.py` 최상단에 적용된 `os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"` 코드가 정상적으로 있는지 확인하세요.
- **오디오가 캡처되지 않을 때**:
  - 윈도우 소리 설정에서 기본 출력 장치(스피커)가 올바르게 설정되어 있는지 확인하세요.

## 📝 라이선스 (License)

이 프로젝트는 [Apache License 2.0](LICENSE)을 따릅니다. 누구나 자유롭게 사용, 수정 및 배포할 수 있습니다.
