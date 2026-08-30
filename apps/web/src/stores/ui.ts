import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UiState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void

  commandOpen: boolean
  setCommandOpen: (open: boolean) => void

  /** Ambient WebGL background. Off by default on low-power machines. */
  ambientEnabled: boolean
  setAmbientEnabled: (enabled: boolean) => void

  /** Services page view preference (grid | list | topology). */
  servicesView: 'grid' | 'list' | 'topology'
  setServicesView: (view: 'grid' | 'list' | 'topology') => void
}

/**
 * Client-only view state.
 *
 * Deliberately small: anything the server owns belongs in React Query, not
 * here. This store holds preferences and transient UI flags only.
 */
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),

      commandOpen: false,
      setCommandOpen: (commandOpen) => set({ commandOpen }),

      ambientEnabled: true,
      setAmbientEnabled: (ambientEnabled) => set({ ambientEnabled }),

      servicesView: 'grid',
      setServicesView: (servicesView) => set({ servicesView }),
    }),
    {
      name: 'kaiops.ui',
      // Never persist transient flags — a reload should not reopen the palette.
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        ambientEnabled: state.ambientEnabled,
        servicesView: state.servicesView,
      }),
    },
  ),
)
