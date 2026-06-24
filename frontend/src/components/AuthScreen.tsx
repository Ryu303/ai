import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock } from 'lucide-react';

export const AuthScreen: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState<string>('admin@argos.security');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      login(email.trim());
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 relative overflow-hidden">
      {/* Background Gradients */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[120px]" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-cyan-500/10 blur-[120px]" />

      {/* Login Card */}
      <div className="w-full max-w-md p-6 sm:p-8 glass rounded-2xl shadow-2xl relative z-10 mx-4 border border-slate-800">
        <div className="flex flex-col items-center mb-8">
          <div className="p-4 bg-violet-600/20 rounded-2xl border border-violet-500/30 text-violet-400 mb-4 shadow-glow-green/10">
            <Shield className="w-10 h-10 animate-pulse" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent break-keep">
            ARGOS SYSTEM
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-2 font-medium break-keep">
            비동기 멀티테넌트 보안 클라이언트
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="email" className="block text-[10px] sm:text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Google Workspace Account (Email)
            </label>
            <div className="relative">
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@argos.security"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors font-medium"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 sm:py-3.5 px-4 bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold rounded-xl shadow-lg hover:from-violet-500 hover:to-indigo-500 focus:outline-none transform transition-transform active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-2 text-xs sm:text-sm"
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <Lock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                <span>Google 계정으로 모의 로그인</span>
              </>
            )}
          </button>
        </form>

        <div className="mt-8 text-center text-[10px] sm:text-xs text-slate-500 break-keep leading-relaxed">
          <p>외부 타사 유료 SaaS 및 쿠키 추적 툴을 일절 배제하여</p>
          <p className="mt-1">개인 음성 및 캘린더 보안 격리가 영구 보장됩니다.</p>
        </div>
      </div>
    </div>
  );
};
