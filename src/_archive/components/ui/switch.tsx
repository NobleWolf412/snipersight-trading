"use client"

import { ComponentProps } from "react"
import * as SwitchPrimitive from "@radix-ui/react-switch"

import { cn } from "@/lib/utils"

function Switch({
  className,
  ...props
}: ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      style={{
        display: 'inline-flex',
        height: '2rem',
        width: '4.5rem',
        alignItems: 'center',
        borderRadius: '4px',
        border: props.checked 
          ? '2px solid rgba(0, 255, 170, 0.6)' 
          : '2px solid rgba(100, 116, 139, 0.4)',
        background: props.checked 
          ? 'linear-gradient(135deg, rgba(0, 255, 170, 0.15) 0%, rgba(0, 216, 138, 0.05) 100%)' 
          : 'linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.8) 100%)',
        transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        cursor: 'pointer',
        position: 'relative',
        boxShadow: props.checked 
          ? '0 0 20px rgba(0, 255, 170, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1), inset 0 -1px 0 rgba(0, 0, 0, 0.3)' 
          : 'inset 0 1px 0 rgba(255, 255, 255, 0.05), inset 0 -1px 0 rgba(0, 0, 0, 0.5)',
      }}
      className={className}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        style={{
          display: 'block',
          width: '1.5rem',
          height: '1.5rem',
          background: props.checked 
            ? 'linear-gradient(135deg, #00ffaa 0%, #00d88a 50%, #00b377 100%)' 
            : 'linear-gradient(135deg, #64748b 0%, #475569 50%, #334155 100%)',
          borderRadius: '3px',
          transition: 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
          transform: props.checked ? 'translateX(2.25rem) rotate(180deg)' : 'translateX(0.25rem) rotate(0deg)',
          boxShadow: props.checked
            ? '0 0 16px rgba(0, 255, 170, 0.8), 0 4px 8px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.3)'
            : '0 2px 6px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
          border: props.checked 
            ? '1px solid rgba(0, 255, 170, 0.5)' 
            : '1px solid rgba(100, 116, 139, 0.3)',
          position: 'relative',
        }}
      >
        <div style={{
          position: 'absolute',
          inset: '2px',
          borderRadius: '2px',
          background: props.checked 
            ? 'radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.4), transparent 60%)' 
            : 'radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.1), transparent 60%)',
          pointerEvents: 'none',
        }} />
      </SwitchPrimitive.Thumb>
    </SwitchPrimitive.Root>
  )
}

export { Switch }
