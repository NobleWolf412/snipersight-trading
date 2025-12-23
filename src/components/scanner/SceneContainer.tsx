import { Canvas } from '@react-three/fiber';
import { EffectComposer, Bloom, Noise, ChromaticAberration, Scanline } from '@react-three/postprocessing';
import { BlendFunction } from 'postprocessing';
import { useRef, ReactNode } from 'react';
import * as THREE from 'three';

interface SceneContainerProps {
    children: ReactNode;
    className?: string;
    isScanning?: boolean;
}

export function SceneContainer({ children, className, isScanning = false }: SceneContainerProps) {
    return (
        <div className={`relative w-full h-full overflow-hidden bg-black ${className}`}>

            {/* R3F Canvas */}
            <Canvas
                camera={{ position: [0, 0, 4.5], fov: 45 }}
                gl={{
                    antialias: false, // Performance optimization for post-processing
                    toneMapping: THREE.ReinhardToneMapping,
                    toneMappingExposure: 1.5,
                    alpha: false
                }}
                dpr={[1, 2]} // Clamp pixel ratio for performance
            >
                <color attach="background" args={['#050805']} />

                {/* Scene Content */}
                <group>
                    {children}
                </group>

                {/* Post Processing Effects */}
                <EffectComposer disableNormalPass>
                    {/* 1. Bloom for that neon glow */}
                    <Bloom
                        luminanceThreshold={0.2}
                        mipmapBlur
                        intensity={1.5}
                        radius={0.4}
                    />

                    {/* 2. Chromatic Aberration for holographic glitch feel */}
                    <ChromaticAberration
                        offset={isScanning ? new THREE.Vector2(0.002, 0.002) : new THREE.Vector2(0.0005, 0.0005)}
                        radialModulation={false}
                        modulationOffset={0}
                    />

                    {/* 3. Noise/Grain for texture */}
                    <Noise opacity={0.1} blendFunction={BlendFunction.OVERLAY} />

                    {/* 4. Scanlines (Subtle TV effect) */}
                    <Scanline density={1.5} opacity={0.05} />
                </EffectComposer>

                {/* Basic Lighting */}
                <ambientLight intensity={0.2} />
                <pointLight position={[10, 10, 10]} intensity={1.0} color="#00ff88" />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#0088ff" />

            </Canvas>
        </div>
    );
}
