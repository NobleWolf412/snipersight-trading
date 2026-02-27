import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface TacticalRadarProps {
    isScanning: boolean;
    blips?: { symbol: string; score: number; angle: number; distance: number }[];
    className?: string;
}

// Radar sweep line
function SweepLine({ isScanning }: { isScanning: boolean }) {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current && isScanning) {
            meshRef.current.rotation.z -= 0.02;
        }
    });

    return (
        <mesh ref={meshRef} position={[0, 0, 0.01]}>
            <planeGeometry args={[0.02, 2, 1, 1]} />
            <meshBasicMaterial
                color="#00ff88"
                transparent
                opacity={0.8}
                side={THREE.DoubleSide}
            />
        </mesh>
    );
}

// Sweep trail effect
function SweepTrail({ isScanning }: { isScanning: boolean }) {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame(() => {
        if (meshRef.current && isScanning) {
            meshRef.current.rotation.z -= 0.02;
        }
    });

    const trailGeometry = useMemo(() => {
        const shape = new THREE.Shape();
        shape.moveTo(0, 0);
        shape.lineTo(0, 2);
        shape.absarc(0, 0, 2, Math.PI / 2, Math.PI / 2 - 0.5, true);
        shape.lineTo(0, 0);
        return new THREE.ShapeGeometry(shape);
    }, []);

    return (
        <mesh ref={meshRef} geometry={trailGeometry} position={[0, 0, 0.005]} rotation={[0, 0, Math.PI / 2]}>
            <meshBasicMaterial
                color="#00ff88"
                transparent
                opacity={0.15}
                side={THREE.DoubleSide}
            />
        </mesh>
    );
}

// Concentric radar rings
function RadarRings() {
    const rings = [0.5, 1.0, 1.5, 2.0];

    return (
        <group>
            {rings.map((radius, i) => (
                <mesh key={i} position={[0, 0, 0]}>
                    <ringGeometry args={[radius - 0.01, radius, 64]} />
                    <meshBasicMaterial
                        color="#00ff88"
                        transparent
                        opacity={0.2 - i * 0.03}
                        side={THREE.DoubleSide}
                    />
                </mesh>
            ))}
        </group>
    );
}

// Crosshair lines
function CrosshairLines() {
    return (
        <group>
            {/* Horizontal line */}
            <mesh position={[0, 0, 0.001]}>
                <planeGeometry args={[4, 0.005]} />
                <meshBasicMaterial color="#00ff88" transparent opacity={0.15} />
            </mesh>
            {/* Vertical line */}
            <mesh position={[0, 0, 0.001]}>
                <planeGeometry args={[0.005, 4]} />
                <meshBasicMaterial color="#00ff88" transparent opacity={0.15} />
            </mesh>
            {/* Diagonal lines */}
            <mesh position={[0, 0, 0.001]} rotation={[0, 0, Math.PI / 4]}>
                <planeGeometry args={[4, 0.003]} />
                <meshBasicMaterial color="#00ff88" transparent opacity={0.08} />
            </mesh>
            <mesh position={[0, 0, 0.001]} rotation={[0, 0, -Math.PI / 4]}>
                <planeGeometry args={[4, 0.003]} />
                <meshBasicMaterial color="#00ff88" transparent opacity={0.08} />
            </mesh>
        </group>
    );
}

// Individual radar blip
function Blip({ position, intensity, isNew }: { position: [number, number, number]; intensity: number; isNew: boolean }) {
    const meshRef = useRef<THREE.Mesh>(null);
    const glowRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current) {
            // Pulse effect
            const pulse = Math.sin(state.clock.elapsedTime * 4) * 0.1 + 1;
            meshRef.current.scale.setScalar(isNew ? pulse * 1.2 : pulse);
        }
        if (glowRef.current) {
            const glowPulse = Math.sin(state.clock.elapsedTime * 3) * 0.2 + 0.5;
            (glowRef.current.material as THREE.MeshBasicMaterial).opacity = glowPulse * intensity;
        }
    });

    const color = intensity > 0.7 ? '#00ff88' : intensity > 0.5 ? '#ffaa00' : '#ff4444';

    return (
        <group position={position}>
            {/* Glow */}
            <mesh ref={glowRef}>
                <circleGeometry args={[0.08, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.3} />
            </mesh>
            {/* Core */}
            <mesh ref={meshRef} position={[0, 0, 0.01]}>
                <circleGeometry args={[0.04, 16]} />
                <meshBasicMaterial color={color} />
            </mesh>
        </group>
    );
}

// Radar blips container
function RadarBlips({ blips, isScanning }: { blips: TacticalRadarProps['blips']; isScanning: boolean }) {
    if (!blips || blips.length === 0) return null;

    return (
        <group>
            {blips.map((blip, i) => {
                const x = Math.cos(blip.angle) * blip.distance * 1.8;
                const y = Math.sin(blip.angle) * blip.distance * 1.8;
                return (
                    <Blip
                        key={`${blip.symbol}-${i}`}
                        position={[x, y, 0.02]}
                        intensity={blip.score / 100}
                        isNew={i === blips.length - 1 && isScanning}
                    />
                );
            })}
        </group>
    );
}

// Main radar scene
function RadarScene({ isScanning, blips }: { isScanning: boolean; blips?: TacticalRadarProps['blips'] }) {
    return (
        <>
            {/* Background */}
            <mesh position={[0, 0, -0.01]}>
                <circleGeometry args={[2.1, 64]} />
                <meshBasicMaterial color="#0a0f0a" />
            </mesh>

            <RadarRings />
            <CrosshairLines />
            <SweepTrail isScanning={isScanning} />
            <SweepLine isScanning={isScanning} />
            <RadarBlips blips={blips} isScanning={isScanning} />

            {/* Center dot */}
            <mesh position={[0, 0, 0.03]}>
                <circleGeometry args={[0.03, 16]} />
                <meshBasicMaterial color="#00ff88" />
            </mesh>
        </>
    );
}

export function TacticalRadar({ isScanning, blips = [], className = '' }: TacticalRadarProps) {
    return (
        <div className={`relative ${className}`}>
            {/* Radar container with glow effect */}
            <div className="absolute inset-0 rounded-full bg-[#00ff88]/5 blur-xl" />

            <Canvas
                camera={{ position: [0, 0, 3], fov: 50 }}
                style={{ background: 'transparent' }}
                gl={{ alpha: true, antialias: true }}
            >
                <RadarScene isScanning={isScanning} blips={blips} />
            </Canvas>

            {/* HUD Overlay */}
            <div className="absolute inset-0 pointer-events-none">
                {/* Corner decorations */}
                <div className="absolute top-2 left-2 w-4 h-4 border-t-2 border-l-2 border-[#00ff88]/50" />
                <div className="absolute top-2 right-2 w-4 h-4 border-t-2 border-r-2 border-[#00ff88]/50" />
                <div className="absolute bottom-2 left-2 w-4 h-4 border-b-2 border-l-2 border-[#00ff88]/50" />
                <div className="absolute bottom-2 right-2 w-4 h-4 border-b-2 border-r-2 border-[#00ff88]/50" />

                {/* Status indicators */}
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${isScanning ? 'bg-[#00ff88] animate-pulse' : 'bg-[#00ff88]/30'}`} />
                    <span className="text-[10px] font-mono text-[#00ff88]/70 tracking-widest">
                        {isScanning ? 'SCANNING' : 'STANDBY'}
                    </span>
                </div>

                {/* Blip count */}
                {blips.length > 0 && (
                    <div className="absolute top-4 right-4 text-[10px] font-mono text-[#00ff88]/70">
                        TARGETS: {blips.length}
                    </div>
                )}
            </div>
        </div>
    );
}
