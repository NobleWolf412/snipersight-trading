import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Html } from '@react-three/drei';

interface HolographicGlobeProps {
    isScanning: boolean;
    blips?: { symbol: string; score: number; angle: number; distance: number }[];
}

function BlipMarker({ position, symbol, score, isScanning }: { position: THREE.Vector3; symbol: string; score: number; isScanning: boolean }) {
    const meshRef = useRef<THREE.Mesh>(null);

    // Pulse animation for high scores or active scanning
    useFrame((state) => {
        if (meshRef.current) {
            const t = state.clock.getElapsedTime();
            const scale = 1 + Math.sin(t * 5) * 0.3; // Pulse
            meshRef.current.scale.setScalar(scale);
        }
    });

    const color = score >= 75 ? '#00ff88' : score >= 50 ? '#fbbf24' : '#ef4444';
    const size = score >= 75 ? 0.08 : 0.05;

    return (
        <group position={position}>
            <mesh ref={meshRef}>
                <sphereGeometry args={[size, 16, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.8} />
            </mesh>
            {/* Halo */}
            <mesh>
                <sphereGeometry args={[size * 2, 16, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.2} wireframe />
            </mesh>

            {/* Label (HTML Overlay) - Only show for high priority items or when few items exist to avoid clutter */}
            {(score >= 70 || !isScanning) && (
                <Html distanceFactor={10}>
                    <div className="pointer-events-none select-none">
                        <div className="bg-black/80 border border-white/20 px-1 py-0.5 rounded text-[8px] font-mono text-[#00ff88] whitespace-nowrap backdrop-blur-sm">
                            {symbol} <span className={score >= 75 ? "text-[#00ff88]" : "text-yellow-400"}>{score}%</span>
                        </div>
                    </div>
                </Html>
            )}
        </group>
    );
}

export function HolographicGlobe({ isScanning, blips = [] }: HolographicGlobeProps) {
    const globeRef = useRef<THREE.Group>(null);
    const coreRef = useRef<THREE.Mesh>(null);

    // Rotate globe constantly, faster when scanning
    useFrame((state, delta) => {
        if (globeRef.current) {
            globeRef.current.rotation.y += delta * (isScanning ? 0.5 : 0.1);
        }
        // Pulse the core
        if (coreRef.current) {
            const pulse = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.05;
            coreRef.current.scale.setScalar(pulse);
        }
    });

    // Convert 2D blip data (angle/distance) to 3D sphere coordinates
    // Map distance (0-1) to latitude (equator to pole), angle to longitude
    const blipElems = useMemo(() => {
        const radius = 2.0;
        return blips.map((blip, i) => {
            // Simple mapping: 
            // angle -> longitude (0 to 2PI)
            // distance -> latitude (spread out from equator)

            const phi = Math.acos(-1 + (2 * i) / blips.length); // Golden spiral distribution for better coverage or just use random/mapped
            // Let's stick to the input angle/distance for consistency with the 2D radar logic if possible, 
            // OR re-map them to a sphere surface.
            // Input: angle (radians), distance (0-1)

            // Map distance to latitude variation (center 0 -> equator)
            const lat = (blip.distance - 0.5) * Math.PI; // -PI/2 to PI/2
            const lon = blip.angle;

            // Spherical to Cartesian
            const x = radius * Math.cos(lat) * Math.cos(lon);
            const y = radius * Math.sin(lat);
            const z = radius * Math.cos(lat) * Math.sin(lon);

            return (
                <BlipMarker
                    key={`${blip.symbol}-${i}`}
                    position={new THREE.Vector3(x, y, z)}
                    symbol={blip.symbol}
                    score={blip.score}
                    isScanning={isScanning}
                />
            );
        });
    }, [blips, isScanning]);

    return (
        <group ref={globeRef}>
            {/* Wireframe Globe */}
            <mesh>
                <icosahedronGeometry args={[2, 2]} />
                <meshBasicMaterial
                    color="#00ff88"
                    wireframe
                    transparent
                    opacity={0.15}
                />
            </mesh>

            {/* Inner Core (The "Singularity") */}
            <mesh ref={coreRef}>
                <sphereGeometry args={[1.0, 32, 32]} />
                <meshBasicMaterial
                    color="#002211"
                    transparent
                    opacity={0.8}
                />
            </mesh>

            {/* Equatorial Ring */}
            <mesh rotation={[Math.PI / 2, 0, 0]}>
                <torusGeometry args={[2.2, 0.02, 16, 100]} />
                <meshBasicMaterial color="#00ff88" opacity={0.4} transparent />
            </mesh>

            {/* Blips */}
            {blipElems}
        </group>
    );
}
