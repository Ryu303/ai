import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Check, X, ShieldAlert } from 'lucide-react';

export const ApprovalModal: React.FC = () => {
  const { pendingAction, handleApprove, handleReject } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!pendingAction) return null;

  const onConfirm = async () => {
    setIsSubmitting(true);
    await handleApprove();
    setIsSubmitting(false);
  };

  const onCancel = async () => {
    setIsSubmitting(true);
    await handleReject();
    setIsSubmitting(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
      {/* Glow highlight */}
      <div className="absolute w-[350px] h-[350px] rounded-full bg-red-600/10 blur-[100px] pointer-events-none" />

      {/* Modal Box */}
      <div className="w-full max-w-md p-6 bg-slate-900 border border-red-500/30 rounded-2xl shadow-2xl relative z-10 animate-scale-in">
        
        {/* Header Alert Icon */}
        <div className="flex items-center gap-4 mb-6">
          <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-xl text-red-500 shadow-glow-red animate-pulse-fast">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-slate-100 tracking-tight">Tier 2 권한 승인 요구됨</h2>
            <span className="text-[10px] text-red-400 font-bold uppercase tracking-wider">High Risk Action Security Check</span>
          </div>
        </div>

        {/* Action Details Description */}
        <div className="bg-slate-950/60 border border-slate-950 rounded-xl p-4 space-y-3 mb-6">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
            작업 상세 설명
          </div>
          <p className="text-xs sm:text-sm text-slate-300 font-semibold leading-relaxed break-keep">
            {pendingAction.message}
          </p>
          <div className="flex justify-between items-center text-[10px] text-slate-500 pt-2 border-t border-slate-900">
            <span>시나리오: {pendingAction.scenario}</span>
            <span>ID: {pendingAction.state_id.slice(0, 8)}...</span>
          </div>
        </div>

        <p className="text-[10px] sm:text-[11px] text-slate-400 mb-6 text-center leading-normal break-keep">
          본 작업은 이메일 발송 등 외부 격리망 정보 누출의 위험도가 존재하므로, 사용자의 명시적인 승인 키워드 입력 또는 터미널 단독 승인이 요구됩니다. 진행하시겠습니까?
        </p>

        {/* Buttons Panel */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="flex-1 py-3 px-4 bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-300 font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            <span>승인 취소(Reject)</span>
          </button>
          
          <button
            onClick={onConfirm}
            disabled={isSubmitting}
            className="flex-1 py-3 px-4 bg-gradient-to-r from-red-600 to-rose-600 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 hover:from-red-500 hover:to-rose-500 shadow-lg shadow-red-600/10 transition-all transform active:scale-98 disabled:opacity-50"
          >
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>진행해(Approve)</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
};
