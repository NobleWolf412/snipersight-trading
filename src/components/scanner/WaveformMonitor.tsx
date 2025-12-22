import { useRef, useEffect, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface WaveformMonitorProps {
    isActive: boolean;
    intensity?: number; // 0-1, affects wave amplitude
    className?: string;
}

// Waveform line using Line geometry
function WaveformLine({ isActive, intensity = 0.5 }: { isActive: boolean; intensity: number }) {
    const lineRef = useRef<THREE.Line>(null);
    const pointCount = 128;
    const width = 6;

    // Create geometry with positions
    const geometry = useMemo(() => {
        const geo = new THREE.BufferGeometry();
        const positions = new Float32Array(pointCount * 3);

        for (let i = 0; i < pointCount; i++) {
            positions[i * 3] = (i / pointCount) * width - width / 2;
            positions[i * 3 + 1] = 0;
            positions[i * 3 + 2] = 0;
        }

        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        return geo;
    }, []);

    useFrame((state) => {
        if (!lineRef.current) return;

        const positions = lineRef.current.geometry.attributes.position.array as Float32Array;
        const time = state.clock.elapsedTime;

        for (let i = 0; i < pointCount; i++) {
            const x = (i / pointCount) * width - width / 2;
            let y = 0;

            if (isActive) {
                // Multiple wave frequencies for more organic look
                const baseWave = Math.sin(x * 2 + time * 3) * 0.3;
                const harmonic1 = Math.sin(x * 5 + time * 5) * 0.15;
                const harmonic2 = Math.sin(x * 8 + time * 7) * 0.08;
                const noise = (Math.random() - 0.5) * 0.05 * intensity;

                y = (baseWave + harmonic1 + harmonic2 + noise) * intensity;
            } else {
                // Idle flat line with tiny noise
                y = (Math.random() - 0.5) * 0.02;
            }

            positions[i * 3 + 1] = y;
        }

        lineRef.current.geometry.attributes.position.needsUpdate = true;
    });

    return (
        <line ref={lineRef} geometry={geometry}>
            <lineBasicMaterial color="#00ff88" linewidth={2} />
        </line>
    );
}

// Grid lines for oscilloscope background
function OscilloscopeGrid() {
    const horizontalLines = 5;
    const verticalLines = 10;
    const width = 6;
    const height = 2;

    return (
        <group position={[0, 0, -0.01]}>
            {/* Horizontal lines */}
            {Array.from({ length: horizontalLines }).map((_, i) => {
                const y = (i / (horizontalLines - 1)) * height - height / 2;
                return (
                    <mesh key={`h-${i}`} position={[0, y, 0]}>
                        <planeGeometry args={[width, 0.003]} />
                        <meshBasicMaterial color="#00ff88" transparent opacity={i === Math.floor(horizontalLines / 2) ? 0.2 : 0.08} />
                    </mesh>
                );
            })}

            {/* Vertical lines */}
            {Array.from({ length: verticalLines + 1 }).map((_, i) => {
                const x = (i / verticalLines) * width - width / 2;
                return (
                    <mesh key={`v-${i}`} position={[x, 0, 0]}>
                        <planeGeometry args={[0.003, height]} />
                        <meshBasicMaterial color="#00ff88" transparent opacity={0.08} />
                    </mesh>
                );
            })}

            {/* Background */}
            <mesh position={[0, 0, -0.01]}>
                <planeGeometry args={[width + 0.1, height + 0.1]} />
                <meshBasicMaterial color="#050805" />
            </mesh>
        </group>
    );
}

// Glow effect behind the waveform
function WaveformGlow({ isActive, intensity }: { isActive: boolean; intensity: number }) {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current && isActive) {
            const glow = 0.05 + Math.sin(state.clock.elapsedTime * 2) * 0.02 * intensity;
            (meshRef.current.material as THREE.MeshBasicMaterial).opacity = glow;
        }
    });

    return (
        <mesh ref={meshRef} position={[0, 0, -0.005]}>
            <planeGeometry args={[6, 0.8]} />
            <meshBasicMaterial color="#00ff88" transparent opacity={isActive ? 0.05 : 0.01} />
        </mesh>
    );
}

// Main scene
function WaveformScene({ isActive, intensity }: { isActive: boolean; intensity: number }) {
    return (
        <>
            <OscilloscopeGrid />
            <WaveformGlow isActive={isActive} intensity={intensity} />
            <WaveformLine isActive={isActive} intensity={intensity} />
        </>
    );
}

export function WaveformMonitor({ isActive, intensity = 0.6, className = '' }: WaveformMonitorProps) {
    return (
        <div className={`relative ${className}`}>
            <Canvas
                camera={{ position: [0, 0, 3], fov: 50 }}
                style={{ background: 'transparent' }}
                gl={{ alpha: true, antialias: true }}
            >
                <WaveformScene isActive={isActive} intensity={intensity} />
            </Canvas>

            {/* HUD overlay */}
            <div className="absolute inset-0 pointer-events-none">
                {/* Top left label */}
                <div className="absolute top-2 left-3 text-[10px] font-mono text-[#00ff88]/60 tracking-wider">
                    WAVEFORM ANALYSIS
                </div>

                {/* Scale markers */}
                <div className="absolute top-1/2 left-1 -translate-y-1/2 text-[8px] font-mono text-[#00ff88]/40">
                    +1.0
                </div>
                <div className="absolute bottom-1/4 left-1 text-[8px] font-mono text-[#00ff88]/40">
                    -1.0
                </div>

                {/* Status */}
                <div className="absolute bottom-2 right-3 flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-[#00ff88] animate-pulse' : 'bg-[#00ff88]/30'}`} />
                    <span className="text-[10px] font-mono text-[#00ff88]/60">
                        {isActive ? 'LIVE' : 'IDLE'}
                    </span>
                </div>

                {/* Corner brackets */}
                <div className="absolute top-1 left-1 w-2 h-2 border-t border-l border-[#00ff88]/30" />
                <div className="absolute top-1 right-1 w-2 h-2 border-t border-r border-[#00ff88]/30" />
                <div className="absolute bottom-1 left-1 w-2 h-2 border-b border-l border-[#00ff88]/30" />
                <div className="absolute bottom-1 right-1 w-2 h-2 border-b border-r border-[#00ff88]/30" />
            </div>
        </div>
    );
}
