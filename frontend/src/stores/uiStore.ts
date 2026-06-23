/**
 * UI 状态 (sidebar, theme, 一些 dialog 开关).
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarOpen: boolean;
  rightSidebarOpen: boolean; // 历史对话右栏
  theme: 'light' | 'dark' | 'system';
  showDocumentPanel: boolean;
  /** Ferrofluid 流体背景开关. 默认 true, 顶栏可关闭以省 GPU / 提升性能. */
  showFluidBackground: boolean;
  // actions
  toggleSidebar: () => void;
  setSidebar: (open: boolean) => void;
  toggleRightSidebar: () => void;
  setRightSidebar: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  toggleDocumentPanel: () => void;
  toggleFluidBackground: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      rightSidebarOpen: true,
      theme: 'system',
      showDocumentPanel: true,
      showFluidBackground: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebar: (open) => set({ sidebarOpen: open }),
      toggleRightSidebar: () => set((s) => ({ rightSidebarOpen: !s.rightSidebarOpen })),
      setRightSidebar: (open) => set({ rightSidebarOpen: open }),
      setTheme: (theme) => set({ theme }),
      toggleDocumentPanel: () => set((s) => ({ showDocumentPanel: !s.showDocumentPanel })),
      toggleFluidBackground: () => set((s) => ({ showFluidBackground: !s.showFluidBackground })),
    }),
    {
      name: 'ai-chatbot:ui',
      partialize: (s) => ({
        sidebarOpen: s.sidebarOpen,
        rightSidebarOpen: s.rightSidebarOpen,
        theme: s.theme,
        showFluidBackground: s.showFluidBackground,
      }),
    },
  ),
);
