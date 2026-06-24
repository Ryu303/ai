import io
import wave
import uuid
import numpy as np
import scipy.signal
import scipy.fftpack
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud

# ==========================================
# 1. 오디오 PCM 데이터 처리 유틸리티
# ==========================================

def load_wav_bytes(audio_bytes: bytes):
    """WAV 바이너리 데이터를 분석하여 NumPy Array 신호와 샘플 레이트를 반환합니다."""
    try:
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav:
            n_channels = wav.getnchannels()
            sampwidth = wav.getsampwidth()
            framerate = wav.getframerate()
            n_frames = wav.getnframes()
            
            content = wav.readframes(n_frames)
            
            # 16-bit PCM 포맷 디코딩
            if sampwidth == 2:
                data = np.frombuffer(content, dtype=np.int16).astype(np.float32)
            elif sampwidth == 1:
                data = np.frombuffer(content, dtype=np.uint8).astype(np.float32) - 128.0
            else:
                data = np.frombuffer(content, dtype=np.int32).astype(np.float32)
            
            # 스테레오 -> 모노 믹스다운
            if n_channels > 1:
                data = data.reshape(-1, n_channels).mean(axis=1)
                
            return data, framerate
    except Exception as e:
        print(f"[Wav Load Warning] wave header parsing failed, using fallback: {e}")
        # 헤더가 없는 Raw PCM 데이터로 간주해 디코딩 시도 (기본 16kHz, mono, int16)
        try:
            data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            return data, 16000
        except Exception:
            # 최종 1초 분량의 무음 신호 반환
            return np.zeros(16000, dtype=np.float32), 16000

def normalize_and_remove_silence(signal: np.ndarray, samplerate: int, threshold_db: float = -35.0) -> np.ndarray:
    """오디오 데이터의 볼륨을 정규화하고 프레임 단위 RMS 기준 무음 구간을 직접 판별해 제거합니다."""
    if len(signal) == 0:
        return signal
        
    # 1. 볼륨 정규화 (Peak Amplitude 기준 1.0 맵핑)
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak
        
    # 2. 무음 제거 (20ms 프레임, 10ms 홉 단위 연산)
    frame_len = int(0.02 * samplerate)
    hop_len = int(0.01 * samplerate)
    
    non_silent_frames = []
    
    for start in range(0, len(signal) - frame_len, hop_len):
        frame = signal[start : start + frame_len]
        # RMS 계산
        rms = np.sqrt(np.mean(frame**2) + 1e-10)
        rms_db = 20 * np.log10(rms)
        
        # 설정 임계 데시벨보다 큰 경우에만 특징 구간으로 포함
        if rms_db >= threshold_db:
            non_silent_frames.append(frame[:hop_len])
            
    if len(non_silent_frames) == 0:
        return signal
        
    return np.concatenate(non_silent_frames)

# ==========================================
# 2. MFCC 특징 벡터 시퀀스 직접 계산 (NumPy/SciPy)
# ==========================================

def hz_to_mel(hz: float) -> float:
    return 2595.0 * np.log10(1.0 + hz / 700.0)

def mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

def get_mel_filterbank(num_filters: int, fft_size: int, sample_rate: int) -> np.ndarray:
    """Mel 스케일 필터 뱅크 행렬을 생성합니다."""
    low_mel = hz_to_mel(0)
    high_mel = hz_to_mel(sample_rate / 2.0)
    mel_points = np.linspace(low_mel, high_mel, num_filters + 2)
    hz_points = mel_to_hz(mel_points)
    
    bin_points = np.floor((fft_size + 1) * hz_points / sample_rate).astype(int)
    
    filters = np.zeros((num_filters, int(fft_size / 2 + 1)))
    
    for i in range(1, num_filters + 1):
        left = bin_points[i - 1]
        center = bin_points[i]
        right = bin_points[i + 1]
        
        for j in range(left, center):
            if center != left:
                filters[i - 1, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                filters[i - 1, j] = (right - j) / (right - center)
                
    return filters

def extract_mfcc_frames(audio_bytes: bytes) -> np.ndarray:
    """오디오 바이트에 직접 정규화/무음 제거를 거친 후 40차원 MFCC 시퀀스를 추출합니다."""
    # 1. WAV 파싱
    signal, sr = load_wav_bytes(audio_bytes)
    
    # 2. 정규화 및 무음 제거
    processed_signal = normalize_and_remove_silence(signal, sr)
    
    if len(processed_signal) == 0:
        return np.zeros((1, 40), dtype=np.float32)
        
    # 3. Pre-emphasis 고주파 부스팅 ($y_t = x_t - 0.97 x_{t-1}$)
    pre_emphasis = 0.97
    emphasized_signal = np.append(processed_signal[0], processed_signal[1:] - pre_emphasis * processed_signal[:-1])
    
    # 4. 프레이밍 (25ms 윈도우, 10ms 스트라이드)
    frame_size = int(0.025 * sr)
    frame_stride = int(0.010 * sr)
    
    signal_len = len(emphasized_signal)
    if signal_len <= frame_size:
        # 신호 길이가 프레임보다 짧은 경우 제로 패딩
        pad_signal = np.pad(emphasized_signal, (0, frame_size - signal_len), 'constant')
        num_frames = 1
    else:
        num_frames = int(np.ceil(float(np.abs(signal_len - frame_size)) / frame_stride)) + 1
        pad_signal_len = num_frames * frame_stride + frame_size
        pad_signal = np.pad(emphasized_signal, (0, pad_signal_len - signal_len), 'constant')
        
    indices = np.tile(np.arange(0, frame_size), (num_frames, 1)) + \
              np.tile(np.arange(0, num_frames * frame_stride, frame_stride), (frame_size, 1)).T
              
    frames = pad_signal[indices.astype(np.int32, copy=False)]
    
    # 해밍 윈도잉 적용
    frames *= np.hamming(frame_size)
    
    # 5. FFT 및 Power Spectrum 도출
    NFFT = 512
    mag_frames = np.absolute(np.fft.rfft(frames, NFFT))
    pow_frames = ((1.0 / NFFT) * ((mag_frames) ** 2))
    
    # 6. Mel Filterbank 에너지 누적 (40개 채널)
    num_filters = 40
    filterbank = get_mel_filterbank(num_filters, NFFT, sr)
    filter_energies = np.dot(pow_frames, filterbank.T)
    filter_energies = np.where(filter_energies == 0, 1e-10, filter_energies) # 로그 언더플로우 회피
    log_filter_energies = 10.0 * np.log10(filter_energies)
    
    # 7. 이산 코사인 변환 (DCT-II) 적용 -> 40차원 MFCC
    mfcc = scipy.fftpack.dct(log_filter_energies, type=2, axis=1, norm='ortho')
    
    return mfcc

# ==========================================
# 3. MFCC 데이터 증강
# ==========================================

def augment_mfcc_features(mfcc_features: np.ndarray) -> np.ndarray:
    """마이크 노이즈 시뮬레이션 및 속도 변화 변조 처리를 위한 데이터 증강을 적용합니다."""
    if len(mfcc_features) <= 1:
        return mfcc_features
        
    augmented = mfcc_features.copy()
    
    # 1. 마이크 노이즈 시뮬레이션 (가우시안 노이즈 주입)
    noise = np.random.normal(0, 0.02, augmented.shape)
    augmented += noise
    
    # 2. 속도 변화 변조 (Time Stretching)
    # 속도를 무작위로 0.95배 또는 1.05배 변경한 후, Linear Interpolation으로 매칭
    speed_factor = np.random.choice([0.95, 1.05])
    n_frames = len(augmented)
    new_n_frames = int(n_frames * speed_factor)
    
    if new_n_frames > 1:
        x_old = np.linspace(0, 1, n_frames)
        x_new = np.linspace(0, 1, new_n_frames)
        
        resized_mfcc = np.zeros((new_n_frames, augmented.shape[1]), dtype=np.float32)
        for i in range(augmented.shape[1]):
            resized_mfcc[:, i] = np.interp(x_new, x_old, augmented[:, i])
        augmented = resized_mfcc
        
    return augmented

# ==========================================
# 4. DTW 알고리즘 직접 구현 및 성문 매칭
# ==========================================

def dtw_distance(s: np.ndarray, t: np.ndarray) -> float:
    """두 MFCC 시퀀스 간의 Dynamic Time Warping (DTW) 최소 거리를 계산합니다."""
    n, m = len(s), len(t)
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0
    
    # 누적 코스트 행렬 도출 (유클리드 거리 기준)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = np.linalg.norm(s[i - 1] - t[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],    # Insertion
                dtw_matrix[i, j - 1],    # Deletion
                dtw_matrix[i - 1, j - 1] # Match
            )
            
    # 누적 매칭 패스 길이로 나누어 정규화된 최소 거리 반환
    return float(dtw_matrix[n, m] / (n + m))

async def calculate_voice_similarity(user_id: uuid.UUID, input_audio_bytes: bytes, db: AsyncSession) -> Dict[str, Any]:
    """저장된 성문과 입력 오디오 간의 최소 DTW 거리를 계산하고, 인증 및 성문 업데이트를 관리합니다."""
    # 1. 입력 음성의 40차원 MFCC 추출
    input_mfcc = extract_mfcc_frames(input_audio_bytes)
    
    # 2. 성문 템플릿 로드
    voice_sig = await crud.get_voice_signature(db, user_id)
    if not voice_sig:
        return {
            "verified": False,
            "message": "성문이 아직 등록되지 않았습니다.",
            "distance": -1.0
        }
        
    saved_mfcc = np.array(voice_sig.mfcc_signature, dtype=np.float32)
    threshold = voice_sig.similarity_threshold
    
    # 3. DTW 거리 연산
    dist = dtw_distance(saved_mfcc, input_mfcc)
    
    # 4. 임계치 내 매칭 여부 판단
    if dist <= threshold:
        # 인증 성공 시 성문 특징 가중치 업데이트 (기존 템플릿 90% + 신규 입력 10%)
        n_saved = len(saved_mfcc)
        n_input = len(input_mfcc)
        
        # 선형 보간을 사용하여 입력 음성 시퀀스 축 길이를 기존에 맞춤
        x_saved = np.linspace(0, 1, n_saved)
        x_input = np.linspace(0, 1, n_input)
        aligned_input = np.zeros_like(saved_mfcc)
        for i in range(saved_mfcc.shape[1]):
            aligned_input[:, i] = np.interp(x_saved, x_input, input_mfcc[:, i])
            
        updated_mfcc = 0.9 * saved_mfcc + 0.1 * aligned_input
        
        # 성공 거리에 연동하여 임계치 점진 최적화 (하한선 15.0 설정)
        new_threshold = float(max(15.0, 0.85 * threshold + 0.15 * dist))
        
        await crud.register_voice(db, user_id, updated_mfcc.tolist(), new_threshold)
        
        return {
            "verified": True,
            "message": "바이오메트릭 성문 인증이 정상 승인되었습니다.",
            "distance": dist,
            "threshold": threshold,
            "new_threshold": new_threshold
        }
    else:
        return {
            "verified": False,
            "message": f"성문 불일치: 입력 패턴의 거리({dist:.2f})가 임계치({threshold:.2f})를 초과했습니다.",
            "distance": dist,
            "threshold": threshold
        }

# ==========================================
# 5. 음성 감정 및 스트레스 분석
# ==========================================

def analyze_voice_emotion(audio_bytes: bytes) -> Dict[str, Any]:
    """오디오 바이트로부터 피치(F0), Jitter, Shimmer, RMS를 산출하여 스트레스/피로 등 사용자의 감정 상태를 정밀 판정합니다."""
    signal, sr = load_wav_bytes(audio_bytes)
    
    # RMS 진폭
    rms = float(np.sqrt(np.mean(signal**2) + 1e-10))
    
    # Peak Normalization
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak
        
    frame_len = int(0.02 * sr)
    hop_len = int(0.01 * sr)
    
    pitches = []
    amplitudes = []
    
    # 20ms 프레임별 피치(F0) 및 진폭 추적
    for start in range(0, len(signal) - frame_len, hop_len):
        frame = signal[start : start + frame_len]
        if len(frame) < frame_len:
            break
            
        # 프레임 RMS 진폭
        amplitudes.append(np.sqrt(np.mean(frame**2) + 1e-10))
        
        # 자기상관(Autocorrelation) 활용 F0 피치 추정
        # 성인 가청 기본 주파수 범위 고려 (80Hz ~ 500Hz)
        min_period = int(sr / 500)
        max_period = int(sr / 80)
        
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr)//2 :]
        
        if len(corr) > max_period:
            search_range = corr[min_period:max_period]
            if len(search_range) > 0:
                peak_idx = np.argmax(search_range) + min_period
                # 피크 신뢰 한계 이상인 경우에만 기본주파수로 등록
                if corr[peak_idx] > 0.25 * corr[0]:
                    pitches.append(sr / peak_idx)
                    
    # 주파수 변동(Jitter) 산출 (인접 피치 차이 평균 / 평균 피치)
    jitter = 0.0
    if len(pitches) > 1:
        diffs = np.abs(np.diff(pitches))
        jitter = float(np.mean(diffs) / (np.mean(pitches) + 1e-10))
        
    # 진폭 변동(Shimmer) 산출 (인접 진폭 차이 평균 / 평균 진폭)
    shimmer = 0.0
    if len(amplitudes) > 1:
        diffs_amp = np.abs(np.diff(amplitudes))
        shimmer = float(np.mean(diffs_amp) / (np.mean(amplitudes) + 1e-10))
        
    f0_mean = float(np.mean(pitches)) if len(pitches) > 0 else 0.0
    
    # 감정 상태 인덱스 맵핑 휴리스틱 알고리즘
    status = "Calm"
    system_guide = "안정적이고 편안한 상태인 것으로 분석됩니다. 좋은 하루 보내십시오!"
    
    if len(pitches) > 0:
        # 스트레스 감지 (음색 떨림 및 불안정 - 높은 Jitter 및 Shimmer)
        if jitter > 0.05 or shimmer > 0.12:
            status = "Stressed"
            system_guide = "몸과 마음의 긴장이나 스트레스 상태가 감지되었습니다. 허브 차 한 잔을 드시며 천천히 3회 심호흡해 보세요."
        # 피로 상태 감지 (주파수가 비정상적으로 낮고 볼륨 에너지가 미약함)
        elif f0_mean < 110.0 and rms < 0.08:
            status = "Fatigued"
            system_guide = "음성 톤에서 높은 피로감이 누적된 것으로 감지되었습니다. 무리한 활동을 중단하고 즉시 충분한 휴식을 취하실 것을 권장해 드립니다."
        # 흥분 상태 감지 (평균 주파수와 볼륨 에너지가 모두 급증)
        elif f0_mean > 210.0 and rms > 0.15:
            status = "Excited"
            system_guide = "매우 기쁘고 긍정적인 흥분/활력 에너지가 충만하게 감지되었습니다!"
            
    return {
        "status": status,
        "f0_mean": f0_mean,
        "jitter": jitter,
        "shimmer": shimmer,
        "rms": rms,
        "system_guide": system_guide
    }
