import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { X, Save, ShieldCheck, Key, CheckCircle, AlertCircle } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Integration {
  id: string;
  service_name: string;
  masked_key: string;
  created_at: string;
  updated_at: string;
}

const AVAILABLE_SERVICES = [
  { key: 'weather', label: 'OpenWeather API Key', placeholder: 'Enter OpenWeather API Key' }
];

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { userId } = useAuth();
  const [integrations, setIntegrations] = useState<Record<string, Integration>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadIntegrations();
    }
  }, [isOpen]);

  const loadIntegrations = async () => {
    try {
      const res = await apiClient.get('/settings/integrations');
      const data: Integration[] = res.data;
      
      const mapped = data.reduce((acc, item) => {
        acc[item.service_name] = item;
        return acc;
      }, {} as Record<string, Integration>);
      
      setIntegrations(mapped);
    } catch (err) {
      console.error('[Settings Error] Failed to load integrations:', err);
    }
  };

  const handleSave = async (serviceName: string) => {
    const apiKey = apiKeys[serviceName];
    if (!apiKey || !apiKey.trim()) return;

    setIsSubmitting(serviceName);
    try {
      await apiClient.post('/settings/integrations', {
        service_name: serviceName,
        api_key: apiKey.trim()
      });

      // 입력란 클리어
      setApiKeys(prev => ({ ...prev, [serviceName]: '' }));
      
      // 토스트 메시지 알림
      showToast(`${serviceName.toUpperCase()} 연동 키가 안전하게 저장되었습니다.`);
      
      // 데이터 갱신
      await loadIntegrations();
    } catch (err) {
      console.error(`[Settings Error] Failed to save key for ${serviceName}:`, err);
      showToast(`저장에 실패했습니다. 관리자에게 문의해 주세요.`);
    } finally {
      setIsSubmitting(null);
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const isGoogleClientIdConnected = !!integrations['google_client_id'];
  const isGoogleClientSecretConnected = !!integrations['google_client_secret'];
  const isGoogleOAuthConnected = !!integrations['google'];

  const handleGoogleOAuthLogin = () => {
    if (!userId) {
      showToast('사용자 세션이 만료되었습니다. 다시 로그인해 주세요.');
      return;
    }
    window.location.href = `http://localhost:8000/api/v1/google/login?user_id=${userId}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md z-50 flex items-center justify-center p-4">
      {/* Toast Alert */}
      {toastMessage && (
        <div className={`fixed top-6 right-6 z-50 p-4 rounded-xl border flex items-center gap-2.5 shadow-2xl animate-bounce ${
          toastMessage.includes('실패')
            ? 'bg-red-500/10 border-red-500/20 text-red-400'
            : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
        }`}>
          {toastMessage.includes('실패') ? <AlertCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          <span className="text-xs font-bold">{toastMessage}</span>
        </div>
      )}

      {/* Modal Box */}
      <div className="w-full max-w-lg p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl relative z-10 animate-scale-in">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-violet-400" />
            <h2 className="text-sm sm:text-base md:text-lg font-bold text-slate-100 break-keep">API 연동 관리 설정</h2>
          </div>
          <button onClick={onClose} className="p-1.5 bg-slate-950 border border-slate-850 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors" title="닫기">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="space-y-6 max-h-[380px] overflow-y-auto pr-1">
          <p className="text-[11px] sm:text-xs text-slate-400 leading-normal break-keep">
            외부 API 토큰 정보를 대칭키 암호화(Fernet)하여 데이터베이스에 격리 보존합니다. 입력한 API 키는 마스킹 처리되어 실제 값 조회가 원천 차단됩니다.
          </p>

          {AVAILABLE_SERVICES.map((srv) => {
            const isConnected = !!integrations[srv.key];
            const maskedVal = integrations[srv.key]?.masked_key || '';

            return (
              <div key={srv.key} className="p-4 bg-slate-950/40 border border-slate-950 rounded-xl space-y-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-300">{srv.label}</span>
                  {isConnected ? (
                    <div className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-md font-bold text-[9px] uppercase flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" />
                      <span>연동됨 (Connected)</span>
                    </div>
                  ) : (
                    <div className="px-2 py-0.5 bg-slate-800 border border-slate-700 text-slate-500 rounded-md font-bold text-[9px] uppercase">
                      미연동
                    </div>
                  )}
                </div>

                {isConnected && (
                  <div className="text-[11px] text-slate-500 font-semibold tracking-wider bg-slate-950/80 p-2.5 rounded-lg border border-slate-900 break-all">
                    현재 키 값: <code className="text-violet-400 font-mono text-xs ml-1">{maskedVal}</code>
                  </div>
                )}

                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeys[srv.key] || ''}
                    onChange={(e) => setApiKeys(prev => ({ ...prev, [srv.key]: e.target.value }))}
                    placeholder={srv.placeholder}
                    className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-650 focus:outline-none focus:border-violet-500 transition-colors font-medium"
                  />
                  <button
                    onClick={() => handleSave(srv.key)}
                    disabled={isSubmitting !== null || !apiKeys[srv.key]}
                    className="py-2 px-4 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors disabled:opacity-40 disabled:pointer-events-none transform active:scale-95 shrink-0"
                  >
                    {isSubmitting === srv.key ? (
                      <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <>
                        <Save className="w-3.5 h-3.5" />
                        <span>저장</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}

          {/* Google OAuth 전용 연동 카드 */}
          <div className="p-4 bg-slate-950/40 border border-slate-950 rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300">Google Workspace (캘린더 / Gmail) OAuth 연동</span>
              {isGoogleOAuthConnected ? (
                <div className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-md font-bold text-[9px] uppercase flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" />
                  <span>계정 연동 완료</span>
                </div>
              ) : isGoogleClientIdConnected && isGoogleClientSecretConnected ? (
                <div className="px-2 py-0.5 bg-amber-500/10 border border-emerald-500/20 text-amber-400 rounded-md font-bold text-[9px] uppercase">
                  로그인 대기 중
                </div>
              ) : (
                <div className="px-2 py-0.5 bg-slate-800 border border-slate-700 text-slate-500 rounded-md font-bold text-[9px] uppercase">
                  미연동
                </div>
              )}
            </div>

            <div className="space-y-3.5">
              {/* Client ID Input */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold flex-wrap gap-1">
                  <span>Google Client ID</span>
                  {isGoogleClientIdConnected && (
                    <span className="text-emerald-400 font-mono text-[9px] break-all">저장됨: {integrations['google_client_id']?.masked_key}</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeys['google_client_id'] || ''}
                    onChange={(e) => setApiKeys(prev => ({ ...prev, google_client_id: e.target.value }))}
                    placeholder="Enter Client ID (...apps.googleusercontent.com)"
                    className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-650 focus:outline-none focus:border-violet-500 transition-colors font-medium font-mono"
                  />
                  <button
                    onClick={() => handleSave('google_client_id')}
                    disabled={isSubmitting !== null || !apiKeys['google_client_id']}
                    className="py-2 px-4 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-bold transition-colors disabled:opacity-40 disabled:pointer-events-none transform active:scale-95 shrink-0"
                  >
                    저장
                  </button>
                </div>
              </div>

              {/* Client Secret Input */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold flex-wrap gap-1">
                  <span>Google Client Secret</span>
                  {isGoogleClientSecretConnected && (
                    <span className="text-emerald-400 font-mono text-[9px] break-all">저장됨: {integrations['google_client_secret']?.masked_key}</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeys['google_client_secret'] || ''}
                    onChange={(e) => setApiKeys(prev => ({ ...prev, google_client_secret: e.target.value }))}
                    placeholder="Enter Client Secret"
                    className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-650 focus:outline-none focus:border-violet-500 transition-colors font-medium font-mono"
                  />
                  <button
                    onClick={() => handleSave('google_client_secret')}
                    disabled={isSubmitting !== null || !apiKeys['google_client_secret']}
                    className="py-2 px-4 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-bold transition-colors disabled:opacity-40 disabled:pointer-events-none transform active:scale-95 shrink-0"
                  >
                    저장
                  </button>
                </div>
              </div>

              {/* OAuth Link Trigger Button */}
              {isGoogleClientIdConnected && isGoogleClientSecretConnected && (
                <div className="pt-2.5 border-t border-slate-850">
                  <button
                    onClick={handleGoogleOAuthLogin}
                    className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-1.5 shadow-md shadow-emerald-950/20 transform active:scale-95 shrink-0"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    <span>구글 계정 연동하기 (OAuth 로그인)</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-800 text-right">
          <button onClick={onClose} className="px-4 py-2 bg-slate-950 border border-slate-850 hover:bg-slate-800 text-slate-300 font-bold rounded-xl text-xs transition-colors">
            닫기
          </button>
        </div>

      </div>
    </div>
  );
};
