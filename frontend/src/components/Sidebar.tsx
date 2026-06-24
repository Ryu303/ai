import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LayoutDashboard, Radio, ShieldCheck, LogOut, Terminal, User, Settings, X } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onOpenSettings: () => void;
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, onOpenSettings, isOpen, onClose }) => {
  const { userEmail, logout } = useAuth();
  const userName = userEmail ? userEmail.split('@')[0] : '사용자';

  const handleTabClick = (tab: string) => {
    setActiveTab(tab);
    onClose(); // 모바일 뷰인 경우 탭 클릭 후 메뉴를 닫아줌
  };

  return (
    <>
      {/* Mobile Sidebar Backdrop overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside className={`w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between h-screen fixed left-0 top-0 z-55 transition-transform duration-300 transform lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div>
          {/* Logo Area */}
          <div className="p-6 border-b border-slate-800 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center text-white font-black shadow-glow-green/10">
                A
              </div>
              <div>
                <h2 className="text-md font-bold tracking-wider text-white">ARGOS SYSTEM</h2>
                <span className="text-[10px] text-violet-400 font-semibold tracking-widest uppercase">Admin Terminal</span>
              </div>
            </div>
            {/* Close button for mobile screen */}
            <button 
              onClick={onClose}
              className="lg:hidden p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
              title="메뉴 닫기"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Tabs */}
          <nav className="p-4 space-y-1">
            <div className="px-3 py-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              Main Panel
            </div>

            <button 
              onClick={() => handleTabClick('dashboard')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-violet-600/10 border border-violet-500/20 text-violet-400'
                  : 'border border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>대시보드 위젯</span>
            </button>
            
            <button 
              onClick={() => handleTabClick('iot')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                activeTab === 'iot'
                  ? 'bg-violet-600/10 border border-violet-500/20 text-violet-400'
                  : 'border border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`}
            >
              <Radio className="w-4 h-4" />
              <span>IoT 기기 제어</span>
            </button>

            <button 
              onClick={() => handleTabClick('voice')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                activeTab === 'voice'
                  ? 'bg-violet-600/10 border border-violet-500/20 text-violet-400'
                  : 'border border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>음성 성문 보안</span>
            </button>

            <button 
              onClick={() => handleTabClick('orchestration')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                activeTab === 'orchestration'
                  ? 'bg-violet-600/10 border border-violet-500/20 text-violet-400'
                  : 'border border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`}
            >
              <Terminal className="w-4 h-4" />
              <span>오케스트레이션</span>
            </button>
          </nav>
        </div>

        {/* Footer User Info */}
        <div className="p-4 border-t border-slate-800 space-y-3">
          <div className="flex items-center gap-3 px-2">
            <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-300 border border-slate-700">
              <User className="w-5 h-5" />
            </div>
            <div className="overflow-hidden">
              <h4 className="text-sm font-bold text-slate-100 capitalize truncate">{userName}</h4>
              <span className="text-[10px] text-slate-500 truncate block">{userEmail}</span>
            </div>
          </div>

          {/* API Settings toggle Button */}
          <button
            onClick={() => {
              onOpenSettings();
              onClose();
            }}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 border border-slate-800 text-slate-300 hover:text-violet-400 hover:border-violet-500/30 hover:bg-violet-500/5 rounded-xl font-bold text-xs transition-all"
          >
            <Settings className="w-4 h-4" />
            <span>환경설정 / API 연동</span>
          </button>

          <button
            onClick={() => {
              logout();
              onClose();
            }}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 border border-slate-800 text-slate-400 hover:text-red-400 hover:border-red-500/30 hover:bg-red-500/5 rounded-xl font-bold text-xs transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>인증 로그아웃</span>
          </button>
        </div>
      </aside>
    </>
  );
};

