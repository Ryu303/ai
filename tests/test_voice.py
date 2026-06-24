import io
import wave
import numpy as np
import pytest
from app.services import voice

def create_dummy_wav(duration: float = 1.0, freq: float = 200.0, sample_rate: int = 16000) -> bytes:
    """메모리 내에 테스트용 단일 주파수 사인파 WAV 오디오 바이트를 생성합니다."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # 1. Sine wave 신호 생성
    signal = np.sin(2 * np.pi * freq * t)
    
    # 2. 볼륨 정규화 및 16-bit PCM 스케일링
    signal = (signal * 32767).astype(np.int16)
    
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)       # 모노
        wav.setsampwidth(2)       # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(signal.tobytes())
        
    return buf.getvalue()

def test_extract_mfcc_frames():
    """WAV 바이너리에서 40차원 MFCC 특징 벡터 시퀀스가 올바르게 추출되는지 검증합니다."""
    audio_bytes = create_dummy_wav(duration=0.5, freq=300.0)
    
    # MFCC 특징 행렬 추출
    mfcc = voice.extract_mfcc_frames(audio_bytes)
    
    # 출력 검증
    assert isinstance(mfcc, np.ndarray), "결과물은 NumPy ndarray여야 합니다."
    assert mfcc.ndim == 2, "2차원 행렬 구조여야 합니다."
    assert mfcc.shape[1] == 40, "열(Feature)의 차원은 40이어야 합니다."
    assert mfcc.shape[0] > 0, "프레임이 최소 1개 이상 생성되어야 합니다."
    print(f"[TEST PASS] extract_mfcc_frames. Output shape: {mfcc.shape}")

def test_dtw_distance():
    """동일한 소리와 서로 다른 소리 간의 DTW 거리가 상대적으로 타당한지 검증합니다."""
    # 동일 소스 2개
    audio_ref = create_dummy_wav(duration=0.5, freq=250.0)
    audio_same = create_dummy_wav(duration=0.5, freq=250.0)
    # 다른 주파수 소스 1개
    audio_diff = create_dummy_wav(duration=0.5, freq=450.0)
    
    mfcc_ref = voice.extract_mfcc_frames(audio_ref)
    mfcc_same = voice.extract_mfcc_frames(audio_same)
    mfcc_diff = voice.extract_mfcc_frames(audio_diff)
    
    dist_same = voice.dtw_distance(mfcc_ref, mfcc_same)
    dist_diff = voice.dtw_distance(mfcc_ref, mfcc_diff)
    
    # 동일 주파수의 신호는 거리가 0에 수렴해야 하며, 다른 신호와의 거리가 더 멀어야 함.
    assert dist_same < 1.0, f"동일 신호 간 거리는 낮아야 합니다: {dist_same}"
    assert dist_same < dist_diff, f"다른 신호 간의 거리({dist_diff})가 동일 신호 거리({dist_same})보다 멀어야 합니다."
    print(f"[TEST PASS] dtw_distance. Same: {dist_same:.4f}, Diff: {dist_diff:.4f}")

def test_voice_data_augmentation():
    """데이터 증강(노이즈 가산 및 타임 스트레칭)이 적용되었을 때의 특징 형상을 검증합니다."""
    audio_bytes = create_dummy_wav(duration=0.6, freq=300.0)
    mfcc = voice.extract_mfcc_frames(audio_bytes)
    
    augmented = voice.augment_mfcc_features(mfcc)
    
    assert augmented.shape[1] == 40, "증강 후에도 특징 차원은 40이어야 합니다."
    assert augmented.shape[0] != mfcc.shape[0] or not np.array_equal(augmented, mfcc), "증강된 신호는 원본과 상이해야 합니다."
    print(f"[TEST PASS] voice_data_augmentation. Original shape: {mfcc.shape}, Augmented shape: {augmented.shape}")

def test_analyze_voice_emotion():
    """음성 스트레스 진단 및 가이드 문장이 잘 생성되는지 검증합니다."""
    audio_bytes = create_dummy_wav(duration=1.0, freq=180.0)
    
    analysis = voice.analyze_voice_emotion(audio_bytes)
    
    assert "status" in analysis, "상태 필드가 존재해야 합니다."
    assert "system_guide" in analysis, "시스템 권장 가이드가 존재해야 합니다."
    assert analysis["status"] in ["Calm", "Stressed", "Fatigued", "Excited"], "정의된 상태 범주 내에 속해야 합니다."
    assert len(analysis["system_guide"]) > 0, "가이드 텍스트가 비어있으면 안 됩니다."
    
    print(f"[TEST PASS] analyze_voice_emotion. Status: {analysis['status']}, F0 Mean: {analysis['f0_mean']:.2f}")
