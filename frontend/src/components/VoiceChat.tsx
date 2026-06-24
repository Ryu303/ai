import React, { useState, useRef, useEffect } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { Mic, Send, MessageSquare, ShieldCheck, Heart, AlertCircle } from 'lucide-react';

interface ChatMessage {
  sender: 'user' | 'system';
  text: string;
  isVerified?: boolean;
}

export const VoiceChat: React.FC = () => {
  const { setPendingAction } = useAuth();
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  
  const [messages, setMessages] = useState<ChatMessage[]>([
    { sender: 'system', text: '안녕하십니까. ARGOS 보안 비서 터미널입니다. 마이크 버튼을 누른 채로 명령을 내리실 수 있습니다.' }
  ]);
  const [textQuery, setTextQuery] = useState<string>('');
  const [userStress, setUserStress] = useState<string | null>(null);
  const [stressGuide, setStressGuide] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // 자동 스크롤
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- 1. Push-to-talk 이벤트 핸들러 ---
  const handleMicPress = () => {
    startRecording();
  };

  const handleMicRelease = async () => {
    try {
      setIsProcessing(true);
      const audioBlob = await stopRecording();
      
      // 폼 데이터 조립
      const formData = new FormData();
      formData.append('file', audioBlob, 'voice.wav');

      // 통합 API 호출
      const res = await apiClient.post('/audio/ai_chat_voice', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const { verified, verification_details, stress_details, chat_details } = res.data;

      // 1. 유저 발화 추가 (가상 STT 쿼리 반영)
      const userText = verified 
        ? `[음성 명령] "${verification_details.distance.toFixed(1)}m 일치" - 서재 가습기 ON`
        : `[음성 명령] 성문 인증 불일치 (인증 거부)`;
      
      setMessages(prev => [...prev, { sender: 'user', text: userText, isVerified: verified }]);

      // 2. 스트레스 진단 및 가이드 반영
      if (stress_details) {
        setUserStress(stress_details.status);
        if (stress_details.status === 'Stressed' || stress_details.status === 'Fatigued') {
          setStressGuide(stress_details.system_guide);
        } else {
          setStressGuide(null);
        }
      }

      // 3. AI 응답 추가
      if (chat_details) {
        setMessages(prev => [...prev, { sender: 'system', text: chat_details.response }]);
        
        // PENDING_APPROVAL 체크 (예: 음성 명령으로 메일 발송 등을 요구하여 상태가 지연된 경우)
        if (chat_details.status === 'PENDING_APPROVAL') {
          setPendingAction({
            state_id: chat_details.state_id,
            scenario: chat_details.scenario,
            message: chat_details.message
          });
        }
      }
    } catch (err) {
      console.error('[Voice upload error]', err);
      setMessages(prev => [...prev, { sender: 'system', text: '오디오 서버 전송 과정에서 네트워크 장애가 발생했습니다.' }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // --- 2. 텍스트 폴백 전송 핸들러 ---
  const handleTextSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textQuery.trim() || isProcessing) return;

    const query = textQuery.trim();
    setTextQuery('');
    setMessages(prev => [...prev, { sender: 'user', text: query, isVerified: true }]);
    
    setIsProcessing(true);
    try {
      const res = await apiClient.post('/ai/chat', { query });
      setMessages(prev => [...prev, { sender: 'system', text: res.data.response }]);
      
      // 오케스트레이션 PENDING_APPROVAL 확인
      if (res.data.status === 'PENDING_APPROVAL') {
        setPendingAction({
          state_id: res.data.state_id,
          scenario: res.data.scenario,
          message: res.data.message
        });
      }
    } catch (err) {
      console.error('[Text Chat Error]', err);
      setMessages(prev => [...prev, { sender: 'system', text: '답변을 로드하지 못했습니다.' }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // 스트레스 뱃지 스타일 맵퍼
  const getStressBadge = () => {
    if (!userStress) return null;
    let color = 'bg-slate-800 text-slate-400 border-slate-700';
    let label = '안정';
    
    if (userStress === 'Stressed') {
      color = 'bg-red-500/10 border-red-500/30 text-red-400 animate-pulse';
      label = '스트레스 긴장';
    } else if (userStress === 'Fatigued') {
      color = 'bg-amber-500/10 border-amber-500/30 text-amber-400';
      label = '피로 누적';
    } else if (userStress === 'Excited') {
      color = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
      label = '활기참';
    } else if (userStress === 'Calm') {
      color = 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400';
      label = '편안함';
    }

    return (
      <div className={`px-2.5 py-1 rounded-full border text-[10px] font-bold flex items-center gap-1.5 ${color}`}>
        <Heart className="w-3 h-3 fill-current" />
        <span>유저 상태: {label}</span>
      </div>
    );
  };

  return (
    <div className="glass rounded-2xl border border-slate-800 flex flex-col h-[520px] shadow-2xl relative overflow-hidden">
      
      {/* Header Panel */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-violet-400" />
          <span className="text-xs font-bold text-slate-200">AI 대화 및 음성 보안 인증</span>
        </div>
        {getStressBadge()}
      </div>

      {/* Stress Guide Notice */}
      {stressGuide && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2.5 text-[10px] text-amber-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 animate-bounce" />
          <p className="font-semibold leading-normal">{stressGuide}</p>
        </div>
      )}

      {/* Messages Window */}
      <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-950/20">
        {messages.map((msg, i) => (
          <div 
            key={i} 
            className={`flex flex-col max-w-[80%] ${
              msg.sender === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'
            }`}
          >
            {msg.sender === 'user' && msg.isVerified && (
              <span className="text-[9px] text-emerald-400 font-bold flex items-center gap-1 mb-1">
                <ShieldCheck className="w-3 h-3" />
                <span>성문 검증 승인됨</span>
              </span>
            )}
            <div 
              className={`p-3 rounded-2xl text-xs font-medium leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-violet-600 text-white rounded-tr-none'
                  : 'bg-slate-900 text-slate-300 rounded-tl-none border border-slate-800'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {isProcessing && (
          <div className="flex mr-auto items-start max-w-[80%]">
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none flex items-center gap-2 text-xs text-slate-500">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span>보안 필터 분석 중...</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Control Action bar */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex items-center gap-3">
        {/* Push-to-talk Micro Button */}
        <button
          onMouseDown={handleMicPress}
          onMouseUp={handleMicRelease}
          onTouchStart={handleMicPress}
          onTouchEnd={handleMicRelease}
          disabled={isProcessing}
          className={`w-12 h-12 rounded-full border transition-all flex items-center justify-center shrink-0 ${
            isRecording 
              ? 'bg-red-500 border-red-600 text-white scale-110 shadow-glow-red animate-pulse' 
              : 'bg-slate-900 border-slate-800 text-violet-400 hover:bg-slate-800 hover:text-violet-300 hover:scale-105 active:scale-95 disabled:opacity-50'
          }`}
          title="길게 누르는 동안 녹음, 떼면 전송 (Push-to-talk)"
        >
          <Mic className="w-5 h-5" />
        </button>

        {/* Text Field fallback */}
        <form onSubmit={handleTextSend} className="flex-1 flex gap-2">
          <input
            type="text"
            value={textQuery}
            onChange={(e) => setTextQuery(e.target.value)}
            disabled={isProcessing}
            placeholder="명령어 또는 질의 입력..."
            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors disabled:opacity-50 font-medium"
          />
          <button
            type="submit"
            disabled={isProcessing || !textQuery.trim()}
            className="p-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl transition-colors disabled:opacity-50 disabled:pointer-events-none transform active:scale-95"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

    </div>
  );
};
