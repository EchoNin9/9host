import { useCallback, useSyncExternalStore } from "react"

type Theme = "light" | "dark" | "system"

const STORAGE_KEY = "9host-theme"

function getStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === "light" || v === "dark" || v === "system") return v
  } catch {}
  return "system"
}

function getResolvedTheme(theme: Theme): "light" | "dark" {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  }
  return theme
}

function applyTheme(theme: Theme) {
  const resolved = getResolvedTheme(theme)
  document.documentElement.classList.toggle("dark", resolved === "dark")
}

// Simple external store for cross-component reactivity
let currentTheme: Theme = getStoredTheme()
const listeners = new Set<() => void>()

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

function getSnapshot(): Theme {
  return currentTheme
}

function setTheme(theme: Theme) {
  currentTheme = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {}
  applyTheme(theme)
  listeners.forEach((cb) => cb())
}

// Apply on load
applyTheme(currentTheme)

// Listen for system preference changes
if (typeof window !== "undefined") {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (currentTheme === "system") applyTheme("system")
  })
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot)
  const resolved = getResolvedTheme(theme)

  const toggle = useCallback(() => {
    setTheme(resolved === "dark" ? "light" : "dark")
  }, [resolved])

  const set = useCallback((t: Theme) => setTheme(t), [])

  return { theme, resolved, toggle, setTheme: set }
}
