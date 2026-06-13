/**
 * UI 状态 (sidebar, theme, 一些 dialog 开关).
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark' | 'system';
  showDocumentPanel: boolean;
  // actions
  toggleSidebar: () => void;
  setSidebar: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  toggleDocumentPanel: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'system',
      showDocumentPanel: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebar: (open) => set({ sidebarOpen: open }),
      setTheme: (theme) => set({ theme }),
      toggleDocumentPanel: () => set((s) => ({ showDocumentPanel: !s.showDocumentPanel })),
    }),
    {
      name: 'ai-chatbot:ui',
      partialize: (s) => ({ sidebarOpen: s.sidebarOpen, theme: s.theme }),
    },
  ),
);
