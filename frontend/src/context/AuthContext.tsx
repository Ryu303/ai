import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export interface PendingAction {
  state_id: string;
  scenario: string;
  message: string;
}

interface AuthContextType {
  userId: string | null;
  userEmail: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string) => Promise<void>;
  logout: () => void;
  // 글로벌 오케스트레이션 상태 머신 승인 처리
  pendingAction: PendingAction | null;
  setPendingAction: (action: PendingAction | null) => void;
  handleApprove: () => Promise<void>;
  handleReject: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [userId, setUserId] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  useEffect(() => {
    // 앱 초기 가동 시 로컬스토리지 복원
    const savedUserId = localStorage.getItem('argos_user_id');
    const savedEmail = localStorage.getItem('argos_user_email');
    if (savedUserId && savedEmail) {
      setUserId(savedUserId);
      setUserEmail(savedEmail);
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string) => {
    setIsLoading(true);
    try {
      // 백엔드로 사용자 조회/생성 요청
      const res = await apiClient.post('/users', { email });
      const data = res.data; // { id: UUID, email: str }
      
      localStorage.setItem('argos_user_id', data.id);
      localStorage.setItem('argos_user_email', data.email);
      setUserId(data.id);
      setUserEmail(data.email);
      
      // 사용자 프로필 초기 템플릿 삽입
      await apiClient.put('/users/profile', {
        profile_data: {
          name: email.split('@')[0],
          role: "관리자",
          personality: "정중하고 지적이며 신속하게 대응함."
        }
      });
    } catch (err) {
      console.error('[Auth Error] Mock user login failed, fallback to mock UUID', err);
      // 서버 미구동 시의 로컬 테스트를 위해 가상 UUID 할당 폴백
      const mockId = '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d';
      localStorage.setItem('argos_user_id', mockId);
      localStorage.setItem('argos_user_email', email);
      setUserId(mockId);
      setUserEmail(email);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('argos_user_id');
    localStorage.removeItem('argos_user_email');
    setUserId(null);
    setUserEmail(null);
    setPendingAction(null);
  };

  const handleApprove = async () => {
    if (!pendingAction) return;
    try {
      // 승인 요청 전송
      await apiClient.post('/orchestration/run', {
        scenario_name: pendingAction.scenario,
        user_approval: '진행해'
      });
      setPendingAction(null);
    } catch (err) {
      console.error('[Orchestration Approval Error] Failed to approve:', err);
      setPendingAction(null);
    }
  };

  const handleReject = async () => {
    if (!pendingAction) return;
    try {
      // 거절 요청 전송
      await apiClient.post('/orchestration/run', {
        scenario_name: pendingAction.scenario,
        user_approval: '취소'
      });
      setPendingAction(null);
    } catch (err) {
      console.error('[Orchestration Reject Error] Failed to reject:', err);
      setPendingAction(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        userId,
        userEmail,
        isAuthenticated: !!userId,
        isLoading,
        login,
        logout,
        pendingAction,
        setPendingAction,
        handleApprove,
        handleReject
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
