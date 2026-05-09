import { useRef, useMemo } from 'react';
import { useFrame, extend, ReactThreeFiber } from '@react-three/fiber';
import * as THREE from 'three';
import { Html, Float, Sparkles, Stars, shaderMaterial } from '@react-three/drei';

// --- 1. Custom Shader Material ---
const HologramMaterial = shaderMaterial(
    { time: 0, color: new THREE.Color('#00ff88') },
    // Vertex Shader
    `
      varying vec2 vUv;
      varying vec3 vPosition;
      void main() {
        vUv = uv;
        vPosition = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    // Fragment Shader
    `
      uniform float time;
      uniform vec3 color;
      varying vec2 vUv;
      varying vec3 vPosition;
      
      void main() {
        // Scanline effect
        float scanline = sin(vPosition.y * 50.0 - time * 2.0) * 0.5 + 0.5;
        
        // Edge glow (Fresnel)
        vec3 viewDir = normalize(cameraPosition - vPosition);
        float fresnel = pow(1.0 - dot(viewDir, normalize(vPosition)), 3.0);
        
        // Tech Grid Pattern
        float gridX = step(0.98, fract(vUv.x * 20.0));
        float gridY = step(0.98, fract(vUv.y * 20.0));
        float grid = max(gridX, gridY) * 0.3;

        // Combine
        float alpha = scanline * 0.1 + fresnel * 0.6 + grid;
        
        // Pulse effect
        float pulse = sin(time) * 0.1 + 0.9;
        
        gl_FragColor = vec4(color * pulse, alpha * 0.8);
      }
    `
);

// Register the shader material
extend({ HologramMaterial });

// Add type definition for the shader material
declare global {
    namespace JSX {
        interface IntrinsicElements {
            hologramMaterial: ReactThreeFiber.Object3DNode<THREE.ShaderMaterial, typeof HologramMaterial> & { color?: string; time?: number };
        }
    }
}

interface HolographicGlobeProps {
    isScanning: boolean;
    blips?: { symbol: string; score: number; angle: number; distance: number }[];
}

function BlipMarker({ position, symbol, score }: { position: THREE.Vector3; symbol: string; score: number }) {
    const meshRef = useRef<THREE.Mesh>(null);
    const color = score >= 75 ? '#00ff88' : score >= 50 ? '#fbbf24' : '#ef4444';
    const size = score >= 75 ? 0.08 : 0.05;

    useFrame((state) => {
        if (meshRef.current) {
            meshRef.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 5) * 0.2);
        }
    });

    return (
        <group position={position}>
            <mesh ref={meshRef}>
                <sphereGeometry args={[size, 16, 16]} />
                <meshBasicMaterial color={color} transparent opacity={0.9} toneMapped={false} />
            </mesh>
            {/* Connection Line to Core */}
            <line>
                <bufferGeometry>
                    <float32BufferAttribute
                        attach="attributes-position"
                        count={2}
                        array={new Float32Array([0, 0, 0, -position.x, -position.y, -position.z])}
                        itemSize={3}
                    />
                </bufferGeometry>
                <lineBasicMaterial color={color} transparent opacity={0.2} />
            </line>
        </group>
    );
}

export function HolographicGlobe({ isScanning, blips = [] }: HolographicGlobeProps) {
    const globeRef = useRef<THREE.Group>(null);
    const materialRef = useRef<THREE.ShaderMaterial>(null);

    useFrame((state, delta) => {
        if (globeRef.current) {
            globeRef.current.rotation.y += delta * (isScanning ? 0.5 : 0.15);
        }
        if (materialRef.current) {
            materialRef.current.uniforms.time.value = state.clock.elapsedTime;
        }
    });

    // Map blips to 3D Sphere
    const blipElems = useMemo(() => {
        const radius = 2.0;
        return blips.map((blip, i) => {
            const lat = (blip.distance - 0.5) * Math.PI;
            const lon = blip.angle;
            const x = radius * Math.cos(lat) * Math.cos(lon);
            const y = radius * Math.sin(lat);
            const z = radius * Math.cos(lat) * Math.sin(lon);

            return (
                <BlipMarker
                    key={`${blip.symbol}-${i}`}
                    position={new THREE.Vector3(x, y, z)}
                    symbol={blip.symbol}
                    score={blip.score}
                />
            );
        });
    }, [blips]);

    return (
        <group>
            {/* Ambient Environment */}
            <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
            <Sparkles count={150} scale={6} size={4} speed={0.4} opacity={0.5} noise={0.2} color="#00ff88" />

            <Float speed={2} rotationIntensity={0.2} floatIntensity={0.2}>
                <group ref={globeRef}>
                    {/* HOLOGRAPHIC SPHERE */}
                    <mesh>
                        <sphereGeometry args={[2, 64, 64]} />
                        {/* @ts-ignore */}
                        <hologramMaterial ref={materialRef} transparent side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} color="#00ff88" />
                    </mesh>

                    {/* Inner Core */}
                    <mesh>
                        <sphereGeometry args={[1.5, 32, 32]} />
                        <meshBasicMaterial color="#003322" transparent opacity={0.3} wireframe />
                    </mesh>
                    <mesh>
                        <sphereGeometry args={[0.8, 32, 32]} />
                        <meshBasicMaterial color="#00ff88" transparent opacity={0.1} />
                    </mesh>

                    {/* Equatorial Rings */}
                    <mesh rotation={[Math.PI / 2, 0, 0]}>
                        <torusGeometry args={[2.5, 0.01, 16, 100]} />
                        <meshBasicMaterial color="#00ff88" transparent opacity={0.3} />
                    </mesh>
                    <mesh rotation={[Math.PI / 2.2, 0, 0]}>
                        <torusGeometry args={[3, 0.005, 16, 100]} />
                        <meshBasicMaterial color="#00ff88" transparent opacity={0.1} />
                    </mesh>

                    {/* Data Blips */}
                    {blipElems}
                </group>
            </Float>
        </group>
    );
}
