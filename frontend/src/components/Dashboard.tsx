import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { 
  Play, Pause, Calendar, Mail, AlertTriangle, 
  RefreshCw, Volume2, Activity 
} from 'lucide-react';

interface CalendarEvent {
  summary: string;
  start: string;
  end: string;
}

interface EmailItem {
  sender: string;
  subject: string;
  snippet: string;
}

export const Dashboard: React.FC = () => {
  const { userId, setPendingAction } = useAuth();
  
  const [briefing, setBriefing] = useState<string>('일일 브리핑을 로드하는 중입니다...');
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    synthRef.current = window.speechSynthesis;
    loadDashboardData();

    // Google OAuth 콜백 쿼리 파라미터 감지
    const params = new URLSearchParams(window.location.search);
    const googleAuthStatus = params.get('google_auth');
    if (googleAuthStatus === 'success') {
      window.history.replaceState({}, document.title, window.location.pathname);
      alert('구글 계정이 성공적으로 연동되었습니다! 대시보드를 갱신합니다.');
      loadDashboardData();
    } else if (googleAuthStatus === 'error') {
      const errMsg = params.get('message') || '알 수 없는 오류';
      window.history.replaceState({}, document.title, window.location.pathname);
      alert(`구글 계정 연동에 실패하였습니다. 사유: ${errMsg}`);
    }

    // 15초마다 시스템 알림 경고 갱신 (실시간성 확보)
    const interval = setInterval(() => {
      refreshSystemNotifications();
    }, 15000);

    return () => {
      clearInterval(interval);
      if (synthRef.current) {
        synthRef.current.cancel();
      }
    };
  }, [userId]);

  const loadDashboardData = async () => {
    setIsRefreshing(true);
    try {
      // 1. 데일리 브리핑 로드
      const briefingRes = await apiClient.get('/daily-briefing');
      setBriefing(briefingRes.data.briefing_text);

      // 2. 캘린더 로드
      const calRes = await apiClient.get('/google/calendar');
      setEvents(calRes.data.events || []);

      // 3. Gmail 로드
      const gmailRes = await apiClient.get('/google/gmail/unread');
      setEmails(gmailRes.data.emails || []);

      // 4. 시스템 알림 로드
      await refreshSystemNotifications();
    } catch (err) {
      console.error('[Dashboard Error] Failed to load initial dashboard:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const refreshSystemNotifications = async () => {
    try {
      // 시스템 경고 알림 로드
      const notifRes = await apiClient.get('/notifications');
      setNotifications(notifRes.data.notifications || []);
    } catch (e) {
      console.error('[Dashboard Error] Failed to refresh diagnostic notifications:', e);
    }
  };

  // --- 1. TTS 브리핑 재생 제어 ---
  const handleToggleSpeech = () => {
    if (!synthRef.current) return;

    if (isSpeaking) {
      synthRef.current.cancel();
      setIsSpeaking(false);
    } else {
      synthRef.current.cancel(); // 기존 재생 정지
      
      const utterance = new SpeechSynthesisUtterance(briefing);
      utterance.lang = 'ko-KR';
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      
      utterance.onend = () => {
        setIsSpeaking(false);
      };
      
      utterance.onerror = () => {
        setIsSpeaking(false);
      };
      
      utteranceRef.current = utterance;
      setIsSpeaking(true);
      synthRef.current.speak(utterance);
    }
  };

  // --- 3. 고위험 시나리오 실행 (오케스트레이터 승인 트리거 테스트용) ---
  const triggerHighRiskAction = async (scenario: string) => {
    try {
      const res = await apiClient.post('/orchestration/run', {
        scenario_name: scenario
      });
      // PENDING_APPROVAL이 반환되면 승인 모달 출력 활성화
      if (res.data.status === 'PENDING_APPROVAL') {
        setPendingAction({
          state_id: res.data.state_id,
          scenario: res.data.scenario,
          message: res.data.message
        });
      }
    } catch (err) {
      console.error('[Orchestration Trigger Error]', err);
    }
  };

  // 2000W 과부하 기기 감지 비활성화 (기기 관리 기능 제거)
  const hasOverload = false;

  return (
    <div className="space-y-6">
      {/* Top Title & Quick Action bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg sm:text-xl md:text-2xl font-bold tracking-tight text-white flex items-center gap-2 break-keep">
            <Activity className="w-5 h-5 sm:w-6 sm:h-6 text-violet-500" />
            <span>보안 모니터링 대시보드</span>
          </h1>
          <p className="text-[11px] sm:text-sm text-slate-400">실시간 데이터 격리 및 디바이스 제어 패널</p>
        </div>
        <button
          onClick={loadDashboardData}
          disabled={isRefreshing}
          className="flex items-center justify-center gap-2 px-3 py-2 sm:px-4 bg-slate-900 border border-slate-800 rounded-xl text-slate-300 font-semibold hover:bg-slate-800 transition-colors disabled:opacity-50 text-xs sm:text-sm shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>새로고침</span>
        </button>
      </div>

      {/* Grid Layout Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* 1. Daily Briefing Card */}
        <div className="lg:col-span-2 glass rounded-2xl p-5 sm:p-6 border border-slate-800 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 p-2 sm:p-3 bg-violet-600/10 rounded-bl-2xl text-violet-400 font-bold text-[9px] sm:text-[10px] tracking-widest flex items-center gap-1.5 border-l border-b border-slate-800">
            <Volume2 className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
            <span>GEMINI 브리핑</span>
          </div>

          <div className="space-y-4 pt-4 sm:pt-0">
            <h3 className="text-sm sm:text-base md:text-lg font-bold text-slate-200 break-keep">오늘의 인공지능 일일 요약</h3>
            <div className="bg-slate-950/60 border border-slate-900 rounded-xl p-3 sm:p-4 text-xs sm:text-sm text-slate-300 leading-relaxed max-h-48 overflow-y-auto break-keep">
              {briefing}
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              onClick={handleToggleSpeech}
              className={`px-4 py-2 sm:px-5 sm:py-2.5 rounded-xl font-bold text-xs sm:text-sm flex items-center gap-2 transition-colors transform active:scale-95 ${
                isSpeaking 
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30' 
                  : 'bg-violet-600 text-white hover:bg-violet-500 shadow-lg shadow-violet-600/20'
              }`}
            >
              {isSpeaking ? (
                <>
                  <Pause className="w-3.5 h-3.5 sm:w-4 sm:h-4 fill-current" />
                  <span>요약 낭독 일시정지</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 sm:w-4 sm:h-4 fill-current" />
                  <span>요약 브리핑 듣기</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 2. System Alerts / Diagnostic Card */}
        <div className="glass rounded-2xl p-5 sm:p-6 border border-slate-800 flex flex-col justify-between">
          <div>
            <h3 className="text-sm sm:text-base md:text-lg font-bold text-slate-200 mb-4 flex items-center gap-2 break-keep">
              <AlertTriangle className={`w-4 h-4 sm:w-5 sm:h-5 ${hasOverload ? 'text-red-500 animate-bounce' : 'text-amber-500'}`} />
              <span>백그라운드 보안 경고</span>
            </h3>
            
            <div className="space-y-3 max-h-56 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-xs sm:text-sm">
                  검출된 시스템 보안 이상 징후가 없습니다.
                </div>
              ) : (
                notifications.map((notif) => (
                  <div 
                    key={notif.id} 
                    className={`p-3 rounded-xl border text-[11px] sm:text-xs flex gap-2.5 ${
                      notif.type === 'SMART_PLUG_OVERLOAD' 
                        ? 'bg-red-500/10 border-red-500/20 text-red-400' 
                        : notif.type === 'HOTSPOT_DETECTED'
                        ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                        : 'bg-slate-900 border-slate-800 text-slate-300'
                    }`}
                  >
                    <AlertTriangle className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
                    <div>
                      <p className="font-semibold break-keep">{notif.message}</p>
                      <span className="text-[9px] sm:text-[10px] text-slate-500 block mt-1">
                        {new Date(notif.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
          
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => triggerHighRiskAction('send_report_email')}
              className="flex-1 py-2.5 px-3 bg-slate-900 border border-slate-800 hover:border-red-500/30 hover:bg-red-500/5 hover:text-red-400 rounded-xl font-bold text-[10px] sm:text-xs text-slate-400 transition-colors break-keep"
            >
              이메일 보고서 발송 (Tier 2)
            </button>
          </div>
        </div>

        {/* 3. Calendar & Mail Widget */}
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Calendar Box */}
          <div className="glass rounded-2xl p-5 sm:p-6 border border-slate-800">
            <h3 className="text-xs sm:text-sm md:text-md font-bold text-slate-200 mb-4 flex items-center gap-2 border-b border-slate-800 pb-2 break-keep">
              <Calendar className="w-4 h-4 text-violet-400" />
              <span>오늘의 구글 캘린더 일정</span>
            </h3>
            
            <div className="space-y-3 max-h-48 overflow-y-auto">
              {events.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">일정이 등록되어 있지 않습니다.</p>
              ) : (
                events.map((ev, i) => (
                  <div key={i} className="p-3 bg-slate-900/50 border border-slate-900 rounded-xl flex flex-col gap-1">
                    <span className="text-xs font-bold text-slate-200 break-keep">{ev.summary}</span>
                    <span className="text-[10px] text-slate-500">
                      {ev.start.split('T')[1]?.slice(0, 5) || ev.start} ~ {ev.end.split('T')[1]?.slice(0, 5) || ev.end}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Mail Box */}
          <div className="glass rounded-2xl p-5 sm:p-6 border border-slate-800">
            <h3 className="text-xs sm:text-sm md:text-md font-bold text-slate-200 mb-4 flex items-center gap-2 border-b border-slate-800 pb-2 break-keep">
              <Mail className="w-4 h-4 text-violet-400" />
              <span>안읽은 Gmail 메일 요약</span>
            </h3>

            <div className="space-y-3 max-h-48 overflow-y-auto">
              {emails.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">안읽은 메일이 없습니다.</p>
              ) : (
                emails.map((em, i) => (
                  <div key={i} className="p-3 bg-slate-900/50 border border-slate-900 rounded-xl">
                    <div className="flex flex-col xs:flex-row justify-between items-start xs:items-center gap-1 mb-1.5">
                      <span className="text-[10px] font-bold text-violet-400 truncate max-w-full xs:max-w-[40%]">{em.sender.split('<')[0]}</span>
                      <span className="text-[9px] sm:text-[10px] text-slate-500 font-semibold truncate max-w-full xs:max-w-[60%] xs:text-right">{em.subject}</span>
                    </div>
                    <p className="text-[10px] sm:text-[11px] text-slate-400 line-clamp-1 break-all">{em.snippet}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
