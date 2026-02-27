import { useEffect, useRef, useState } from 'react';

export function useMousePosition() {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const rafId = useRef<number | null>(null);
  const pending = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const update = () => {
      if (pending.current) {
        setPosition(pending.current);
        pending.current = null;
      }
      rafId.current = null;
    };

    const handleMouseMove = (e: MouseEvent) => {
      pending.current = { x: e.clientX, y: e.clientY };
      if (rafId.current == null) {
        rafId.current = requestAnimationFrame(update);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (rafId.current != null) cancelAnimationFrame(rafId.current);
    };
  }, []);

  return position;
}
