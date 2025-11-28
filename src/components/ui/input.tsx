import { ComponentProps } from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "hud-terminal text-primary/90 tracking-wide text-center",
        "border-2 border-primary/30 hover:border-primary/60 focus-visible:border-primary",
        "bg-gradient-to-b from-slate-900/60 to-slate-950/80 backdrop-blur-sm",
        "hover:from-slate-900/80 hover:to-slate-950/90",
        "shadow-[0_0_15px_rgba(0,255,170,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]",
        "hover:shadow-[0_0_20px_rgba(0,255,170,0.3),inset_0_1px_0_rgba(255,255,255,0.15)]",
        "focus-visible:shadow-[0_0_25px_rgba(0,255,170,0.4),0_0_10px_rgba(0,255,170,0.2),inset_0_1px_0_rgba(255,255,255,0.2)]",
        "rounded-sm",
        "flex h-9 w-full min-w-0 px-3 py-1 text-base",
        "transition-all duration-300 ease-out outline-none",
        "placeholder:text-primary/40",
        "selection:bg-primary/20 selection:text-primary",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-primary/90",
        "md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
