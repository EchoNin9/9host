import { Moon, Sun } from "lucide-react"
import { useTheme } from "@/hooks/use-theme"

export function ThemeToggle() {
  const { resolved, toggle } = useTheme()

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground text-left"
      title={resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {resolved === "dark" ? (
        <Sun className="size-3.5" />
      ) : (
        <Moon className="size-3.5" />
      )}
      {resolved === "dark" ? "Light mode" : "Dark mode"}
    </button>
  )
}
