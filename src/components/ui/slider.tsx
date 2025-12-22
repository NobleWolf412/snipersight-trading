"use client"

import { ComponentProps, useMemo } from "react"
import * as SliderPrimitive from "@radix-ui/react-slider"

import { cn } from "@/lib/utils"

interface TacticalSliderProps extends ComponentProps<typeof SliderPrimitive.Root> {
  color?: string;
  zones?: { limit: number; color: string; label: string }[];
}

function Slider({
  className,
  defaultValue,
  value,
  min = 0,
  max = 100,
  color = '#00ff88',
  zones,
  ...props
}: TacticalSliderProps) {
  const _values = useMemo(
    () =>
      Array.isArray(value)
        ? value
        : Array.isArray(defaultValue)
          ? defaultValue
          : [min, max],
    [value, defaultValue, min, max]
  )

  // Determine active zone color based on current value
  const currentValue = Array.isArray(value) ? value[0] : (value ?? min);
  const activeZone = zones?.find(z => currentValue <= z.limit) || zones?.[zones.length - 1];
  const activeColor = activeZone?.color || color;

  return (
    <SliderPrimitive.Root
      data-slot="slider"
      defaultValue={defaultValue}
      value={value}
      min={min}
      max={max}
      className={cn(
        "relative flex w-full touch-none items-center select-none data-[disabled]:opacity-50 h-20",
        className
      )}
      {...props}
    >
      {/* TACTICAL TRACK - Much thicker */}
      <SliderPrimitive.Track
        data-slot="slider-track"
        className={cn(
          "relative grow overflow-hidden rounded-full h-8 w-full",
          "bg-black/80 border-2 border-white/10",
          "shadow-[inset_0_4px_8px_rgba(0,0,0,0.6)]"
        )}
      >
        {/* Zone background segments */}
        {zones && (
          <div className="absolute inset-0 flex">
            {zones.map((zone, i) => {
              const prevLimit = i === 0 ? min : zones[i - 1].limit;
              const width = ((Math.min(zone.limit, max) - Math.max(prevLimit, min)) / (max - min)) * 100;
              return (
                <div
                  key={i}
                  className="h-full opacity-20 border-r border-black/30"
                  style={{ width: `${width}%`, backgroundColor: zone.color }}
                />
              );
            })}
          </div>
        )}

        {/* Active fill range */}
        <SliderPrimitive.Range
          data-slot="slider-range"
          className="absolute h-full"
          style={{
            backgroundColor: activeColor,
            boxShadow: `0 0 15px ${activeColor}40`
          }}
        />

        {/* Scanline overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-black/10 pointer-events-none" />
      </SliderPrimitive.Track>

      {/* TACTICAL THUMB - Much larger and more visible */}
      {Array.from({ length: _values.length }, (_, index) => (
        <SliderPrimitive.Thumb
          data-slot="slider-thumb"
          key={index}
          className={cn(
            "block w-10 h-16 rounded-lg cursor-grab active:cursor-grabbing",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
            "disabled:pointer-events-none disabled:opacity-50",
            "transition-transform hover:scale-105 active:scale-95",
            "flex items-center justify-center"
          )}
          style={{
            background: `linear-gradient(180deg, #3a3a3a 0%, #1a1a1a 100%)`,
            border: `3px solid ${activeColor}`,
            boxShadow: `0 0 20px ${activeColor}60, 0 4px 12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.15)`
          }}
        >
          {/* Grip lines inside thumb */}
          <div className="flex gap-1.5 pointer-events-none">
            <div className="w-0.5 h-6 bg-white/40 rounded-full" />
            <div className="w-0.5 h-6 bg-white/40 rounded-full" />
          </div>
        </SliderPrimitive.Thumb>
      ))}
    </SliderPrimitive.Root>
  )
}

export { Slider }
export type { TacticalSliderProps }

