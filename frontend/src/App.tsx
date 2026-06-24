import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AuthScreen } from './components/AuthScreen';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './components/Dashboard';
import { VoiceChat } from './components/VoiceChat';
import { ApprovalModal } from './components/ApprovalModal';
import { SettingsModal } from './components/SettingsModal';
import { Cpu, ShieldCheck, Terminal, Menu } from 'lucide-react';

// IoT 전용 뷰 컴포넌트
const IoTView: React.FC = () => {
  return (
    <div className="glass rounded-2xl p-5 sm:p-8 border border-slate-800 space-y-6">
      <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
        <Cpu className="w-5.5 h-5.5 sm:w-6 sm:h-6 text-violet-400" />
        <h2 className="text-lg sm:text-xl font-bold text-slate-100 break-keep">IoT 스마트홈 허브 상세 패널</h2>
      </div>
      <p className="text-xs sm:text-sm text-slate-400 leading-relaxed break-keep">
        연동된 SwitchBot 및 스마트 플러그 기기의 정밀 분석 상태를 제공합니다. 백그라운드 모니터 60초 주기 스레드가 활성화되어 과부하(2000W 이상) 상태를 15초 단위로 갱신 진단 중입니다.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
        <div className="bg-slate-900/50 p-5 sm:p-6 border border-slate-950 rounded-xl space-y-2">
          <h4 className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-widest">네트워크 상태</h4>
          <p className="text-sm sm:text-md font-bold text-emerald-400">ONLINE (정상 연결)</p>
          <span className="text-[9px] sm:text-[10px] text-slate-500 block">Wi-Fi 및 스마트홈 게이트웨이 지연속도: 8ms</span>
        </div>
        <div className="bg-slate-900/50 p-5 sm:p-6 border border-slate-950 rounded-xl space-y-2">
          <h4 className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-widest">일일 누적 총 소비량</h4>
          <p className="text-sm sm:text-md font-bold text-violet-400">4.8 kWh</p>
          <span className="text-[9px] sm:text-[10px] text-slate-500 block break-keep">최대 피크 전력량: 2150W (난방기 기동 시간대)</span>
        </div>
      </div>
    </div>
  );
};

// 성문 보안 전용 뷰 컴포넌트
const VoiceView: React.FC = () => {
  return (
    <div className="glass rounded-2xl p-5 sm:p-8 border border-slate-800 space-y-6">
      <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
        <ShieldCheck className="w-5.5 h-5.5 sm:w-6 sm:h-6 text-violet-400" />
        <h2 className="text-lg sm:text-xl font-bold text-slate-100 break-keep">바이오메트릭 성문 보안 관리자</h2>
      </div>
      <p className="text-xs sm:text-sm text-slate-400 leading-relaxed break-keep">
        NumPy 및 SciPy의 FFT 연산을 직접 수행하여 도출한 40차원 MFCC 특징 벡터 분석 결과입니다. DTW(Dynamic Time Warping) 거리를 연산하여 성문을 매칭하고, 인증 성공 빈도에 맞춰 최소 잠금 임계치(Similarity Threshold)를 유동적으로 갱신합니다.
      </p>
      <div className="bg-slate-950/60 p-4 sm:p-6 border border-slate-950 rounded-xl space-y-4">
        <h4 className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-widest border-b border-slate-900 pb-2">성문 락 상태 정보</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[11px] sm:text-xs">
          <div>
            <span className="text-slate-500 block mb-1">성문 등록 여부</span>
            <span className="font-bold text-emerald-400">ACTIVE (등록됨)</span>
          </div>
          <div>
            <span className="text-slate-500 block mb-1">MFCC 계수</span>
            <span className="font-bold text-slate-300">40 Coefficients</span>
          </div>
          <div>
            <span className="text-slate-500 block mb-1">인증 기본 임계치</span>
            <span className="font-bold text-slate-300">70.0 (거리 수치)</span>
          </div>
          <div>
            <span className="text-slate-500 block mb-1">자동 임계 최적화</span>
            <span className="font-bold text-violet-400">ON (동작 중)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// 오케스트레이션 이력 전용 뷰 컴포넌트
const OrchestrationView: React.FC = () => {
  return (
    <div className="glass rounded-2xl p-5 sm:p-8 border border-slate-800 space-y-6">
      <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
        <Terminal className="w-5.5 h-5.5 sm:w-6 sm:h-6 text-violet-400" />
        <h2 className="text-lg sm:text-xl font-bold text-slate-100 break-keep">태스크 오케스트레이션 콘솔</h2>
      </div>
      <p className="text-xs sm:text-sm text-slate-400 leading-relaxed break-keep">
        비동기 상태 머신 엔진이 제어한 태스크 흐름과 실행 승인 이력입니다. 이메일 발송 등 민감도가 높은 Tier 2 작업은 PENDING_APPROVAL 상태로 안전 구역에 임시 적재됩니다.
      </p>
      <div className="space-y-4">
        <div className="p-4 bg-slate-900/30 border border-slate-800 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          <div className="flex items-start sm:items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-md font-bold text-[9px] uppercase">COMPLETED</span>
            <span className="font-bold text-slate-200 break-all">morning_briefing (일일 종합 브리핑 빌드)</span>
          </div>
          <span className="text-slate-500 text-[11px] sm:text-xs shrink-0">자동 승인 (Tier 1)</span>
        </div>
        <div className="p-4 bg-slate-900/30 border border-slate-800 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          <div className="flex items-start sm:items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md font-bold text-[9px] uppercase">PENDING_CHECK</span>
            <span className="font-bold text-slate-200 break-all">send_report_email (시스템 진단 결과 이메일 발송)</span>
          </div>
          <span className="text-slate-500 text-[11px] sm:text-xs shrink-0">사용자 승인 대기 (Tier 2)</span>
        </div>
      </div>
    </div>
  );
};

const MainLayout: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  const renderActiveView = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'iot':
        return <IoTView />;
      case 'voice':
        return <VoiceView />;
      case 'orchestration':
        return <OrchestrationView />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex relative overflow-x-hidden">
      {/* 1. Global Orchestration Approval Modal Overlay */}
      <ApprovalModal />

      {/* 2. Global API Settings Modal Overlay */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />

      {/* 3. Fixed Left Navigation Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        onOpenSettings={() => setIsSettingsOpen(true)} 
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* 4. Main Frame content area */}
      <main className="flex-1 lg:pl-64 min-h-screen flex flex-col transition-all duration-300">
        {/* Top Header diagnostic stats bar */}
        <header className="h-16 border-b border-slate-900 px-4 sm:px-8 flex items-center justify-between bg-slate-900/10">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setIsSidebarOpen(true)}
              className="lg:hidden p-2 -ml-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="메뉴 열기"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-glow-green animate-pulse" />
              <span className="text-[10px] sm:text-xs font-semibold text-slate-400 whitespace-nowrap">ARGOS SECURE NETWORK CONNECTED</span>
            </div>
          </div>
          <div className="text-[9px] sm:text-xs text-slate-500 font-semibold uppercase tracking-wider hidden xs:block">
            Terminal Status: Active
          </div>
        </header>

        {/* Dynamic Responsive Widgets Content */}
        <div className="flex-1 p-4 sm:p-6 lg:p-8 grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">
          {/* Main Widgets Area (3/4 span) */}
          <div className="xl:col-span-3 space-y-6">
            {renderActiveView()}
          </div>

          {/* AI Voice Chat Area (1/4 span) */}
          <div className="xl:col-span-1 xl:sticky xl:top-6">
            <VoiceChat />
          </div>
        </div>
      </main>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}

export default App;
