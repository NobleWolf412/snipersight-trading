import { create } from 'zustand';

export type ThemeMode = 'system' | 'light' | 'dark';

interface UIState {
  sidebarOpen: boolean;
  theme: ThemeMode;
  modal: {
    open: boolean;
    content?: string;
  };
  setSidebar: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: ThemeMode) => void;
  openModal: (content?: string) => void;
  closeModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: false,
  theme: 'system',
  modal: { open: false },
  setSidebar: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
  openModal: (content) => set({ modal: { open: true, content } }),
  closeModal: () => set({ modal: { open: false } }),
}));
