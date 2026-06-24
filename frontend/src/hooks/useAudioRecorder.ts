import { useState, useRef, useCallback } from 'react';

export const useAudioRecorder = () => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // 녹음 시작 함수
  const startRecording = useCallback(async () => {
    audioChunksRef.current = [];
    try {
      // 1. 마이크 권한 요청
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // 2. 브라우저 지원 마임타입 감지
      let options = {};
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        options = { mimeType: 'audio/webm;codecs=opus' };
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        options = { mimeType: 'audio/ogg;codecs=opus' };
      }

      // 3. MediaRecorder 기동
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(10); // 10ms 단위 슬라이스 캡처
      setIsRecording(true);
      console.log('[MediaRecorder] Voice capturing started...');
    } catch (err) {
      console.error('[MediaRecorder Error] Failed to gain mic access:', err);
    }
  }, []);

  // 녹음 중지 및 오디오 Blob 회수 함수
  const stopRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      if (!mediaRecorderRef.current) {
        reject('MediaRecorder가 초기화되지 않았습니다.');
        return;
      }

      mediaRecorderRef.current.onstop = () => {
        // 백엔드 파이싱 안정성을 위해 wav 헤더 라벨링을 적용한 Blob 빌드
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        
        // 마이크 스트림 리소스 완전 릴리즈 (오퍼레이팅 시스템 마이크 아이콘 비활성화 보장)
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }

        setIsRecording(false);
        console.log('[MediaRecorder] Recording stopped. Blob size:', audioBlob.size);
        resolve(audioBlob);
      };

      mediaRecorderRef.current.stop();
    });
  }, []);

  return {
    isRecording,
    startRecording,
    stopRecording,
  };
};
