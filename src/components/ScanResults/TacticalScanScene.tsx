import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera, Environment } from '@react-three/drei';
import { EffectComposer, Bloom, ChromaticAberration, Scanline, Noise, Vignette } from '@react-three/postprocessing';
import { BlendFunction } from 'postprocessing';
import { HolographicGlobe } from '@/components/scanner/HolographicGlobe';
import { Suspense } from 'react';

interface TacticalScanSceneProps {
    blips?: any[];
}

export function TacticalScanScene({ blips = [] }: TacticalScanSceneProps) {
    return (
        <div className="absolute inset-0 z-0 pointer-events-none">
            <Canvas dpr={[1, 2]} gl={{ antialias: false, alpha: true }}>
                <Suspense fallback={null}>
                    {/* Camera */}
                    <PerspectiveCamera makeDefault position={[0, 0, 7]} fov={45} />

                    {/* Lighting & Environment */}
                    <Environment preset="city" />
                    <ambientLight intensity={0.5} />
                    <pointLight position={[10, 10, 5]} intensity={1} color="#00ff88" />

                    {/* The Main Event: Holographic Globe */}
                    <HolographicGlobe isScanning={true} blips={blips} />

                    {/* Post-Processing Pipeline */}
                    <EffectComposer disableNormalPass>
                        {/* 1. Bloom for that neon glow */}
                        <Bloom
                            intensity={0.5}
                            luminanceThreshold={0.5}
                            luminanceSmoothing={0.9}
                            blendFunction={BlendFunction.SCREEN}
                        />

                        {/* 2. Chromatic Aberration for glitchy tech feel */}
                        <ChromaticAberration
                            offset={[0.001, 0.001]} // x, y
                            blendFunction={BlendFunction.NORMAL}
                        />

                        {/* 3. Scanlines for CRT monitor look */}
                        <Scanline
                            density={1.5}
                            opacity={0.05}
                            blendFunction={BlendFunction.OVERLAY}
                        />

                        {/* 4. Film Noise for texture */}
                        <Noise
                            opacity={0.02}
                            blendFunction={BlendFunction.SOFT_LIGHT}
                        />

                        {/* 5. Vignette to focus center */}
                        <Vignette
                            darkness={0.6}
                            offset={0.2}
                        />
                    </EffectComposer>
                </Suspense>
            </Canvas>
        </div>
    );
}
