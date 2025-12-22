import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Binoculars, Lightning, Crosshair, Ghost } from '@phosphor-icons/react';

interface ModeVisualsProps {
    activeMode: string;
}

// Mode color configurations
const MODE_COLORS = {
    overwatch: { primary: 0x00ffcc, secondary: 0x00aa88, accent: 0x66ffdd },
    strike: { primary: 0xffaa00, secondary: 0xff6600, accent: 0xffdd44 },
    surgical: { primary: 0xaa66ff, secondary: 0x8844cc, accent: 0xcc99ff },
    stealth: { primary: 0x8866ff, secondary: 0x6644cc, accent: 0xaa88ff },
};

export function ModeVisuals({ activeMode }: ModeVisualsProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [hasWebGLError, setHasWebGLError] = useState(false);

    useEffect(() => {
        if (!containerRef.current || !canvasRef.current) return;
        if (hasWebGLError) return;

        const container = containerRef.current;
        const canvas = canvasRef.current;
        const colors = MODE_COLORS[activeMode as keyof typeof MODE_COLORS] || MODE_COLORS.overwatch;

        // SETUP
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100);
        camera.position.z = 5;

        let renderer: THREE.WebGLRenderer;
        try {
            renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        } catch (e) {
            console.warn("WebGL not supported, falling back to 2D mode", e);
            setHasWebGLError(true);
            return;
        }

        // Handle WebGL context loss gracefully
        const handleContextLost = (event: Event) => {
            event.preventDefault();
            console.warn('[ModeVisuals] WebGL context lost, switching to fallback');
            setHasWebGLError(true);
        };
        canvas.addEventListener('webglcontextlost', handleContextLost);

        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); // Reduce pixel ratio to save GPU memory

        const contentGroup = new THREE.Group();
        scene.add(contentGroup);

        // OVERWATCH: Orbiting surveillance satellites around a globe
        const buildOverwatch = () => {
            camera.position.set(0, 2, 5);
            camera.lookAt(0, 0, 0);

            // Globe wireframe
            const globeGeo = new THREE.IcosahedronGeometry(1.5, 2);
            const globeMat = new THREE.MeshBasicMaterial({
                color: colors.primary,
                wireframe: true,
                transparent: true,
                opacity: 0.3
            });
            const globe = new THREE.Mesh(globeGeo, globeMat);
            contentGroup.add(globe);

            // Orbit rings
            const ringGeo = new THREE.TorusGeometry(2.2, 0.02, 8, 64);
            const ringMat = new THREE.MeshBasicMaterial({ color: colors.secondary, transparent: true, opacity: 0.5 });
            const ring1 = new THREE.Mesh(ringGeo, ringMat);
            ring1.rotation.x = Math.PI / 2;
            contentGroup.add(ring1);

            const ring2 = new THREE.Mesh(ringGeo.clone(), ringMat.clone());
            ring2.rotation.x = Math.PI / 3;
            ring2.rotation.y = Math.PI / 4;
            contentGroup.add(ring2);

            // Satellites (small spheres)
            const satGeo = new THREE.SphereGeometry(0.08, 8, 8);
            const satMat = new THREE.MeshBasicMaterial({ color: colors.accent });
            const satellites: THREE.Mesh[] = [];

            for (let i = 0; i < 3; i++) {
                const sat = new THREE.Mesh(satGeo, satMat.clone());
                satellites.push(sat);
                contentGroup.add(sat);
            }

            // Scan beam
            const beamGeo = new THREE.ConeGeometry(0.3, 1.5, 8);
            const beamMat = new THREE.MeshBasicMaterial({ color: colors.primary, transparent: true, opacity: 0.2 });
            const beam = new THREE.Mesh(beamGeo, beamMat);
            contentGroup.add(beam);

            return {
                update: (t: number) => {
                    globe.rotation.y = t * 0.2;
                    ring1.rotation.z = t * 0.1;
                    ring2.rotation.z = -t * 0.15;

                    // Orbit satellites
                    satellites.forEach((sat, i) => {
                        const angle = t + (i * Math.PI * 2 / 3);
                        const radius = 2.2;
                        sat.position.x = Math.cos(angle) * radius;
                        sat.position.z = Math.sin(angle) * radius * 0.5;
                        sat.position.y = Math.sin(angle * 2) * 0.3;
                    });

                    // Animate scan beam
                    beam.position.copy(satellites[0].position);
                    beam.position.y -= 0.75;
                    beam.rotation.x = Math.PI;
                    beam.material.opacity = 0.15 + Math.sin(t * 3) * 0.1;
                }
            };
        };

        // STRIKE: Aggressive lightning and energy particles
        const buildStrike = () => {
            camera.position.set(0, 0, 5);
            camera.lookAt(0, 0, 0);

            // Central energy sphere
            const coreGeo = new THREE.SphereGeometry(0.5, 16, 16);
            const coreMat = new THREE.MeshBasicMaterial({ color: colors.primary });
            const core = new THREE.Mesh(coreGeo, coreMat);
            contentGroup.add(core);

            // Energy rings
            const rings: THREE.Mesh[] = [];
            for (let i = 0; i < 3; i++) {
                const rGeo = new THREE.TorusGeometry(0.8 + i * 0.4, 0.02, 8, 32);
                const rMat = new THREE.MeshBasicMaterial({ color: colors.accent, transparent: true, opacity: 0.6 - i * 0.15 });
                const ring = new THREE.Mesh(rGeo, rMat);
                rings.push(ring);
                contentGroup.add(ring);
            }

            // Fast particles
            const particleCount = 60;
            const particleGeo = new THREE.BufferGeometry();
            const positions = new Float32Array(particleCount * 3);
            const velocities: { x: number; y: number; z: number; speed: number }[] = [];

            for (let i = 0; i < particleCount; i++) {
                const angle = Math.random() * Math.PI * 2;
                const radius = 1 + Math.random() * 2;
                positions[i * 3] = Math.cos(angle) * radius;
                positions[i * 3 + 1] = (Math.random() - 0.5) * 3;
                positions[i * 3 + 2] = Math.sin(angle) * radius;
                velocities.push({
                    x: (Math.random() - 0.5) * 0.05,
                    y: (Math.random() - 0.5) * 0.05,
                    z: (Math.random() - 0.5) * 0.05,
                    speed: 0.02 + Math.random() * 0.03
                });
            }
            particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            const particleMat = new THREE.PointsMaterial({ color: colors.secondary, size: 0.08 });
            const particles = new THREE.Points(particleGeo, particleMat);
            contentGroup.add(particles);

            return {
                update: (t: number) => {
                    // Pulsing core
                    const pulse = 1 + Math.sin(t * 8) * 0.15;
                    core.scale.setScalar(pulse);

                    // Spinning rings with different speeds
                    rings.forEach((ring, i) => {
                        ring.rotation.x = t * (2 - i * 0.3);
                        ring.rotation.y = t * (1.5 + i * 0.2);
                        ring.scale.setScalar(1 + Math.sin(t * 4 + i) * 0.1);
                    });

                    // Animate particles outward
                    const pos = particles.geometry.attributes.position.array as Float32Array;
                    for (let i = 0; i < particleCount; i++) {
                        pos[i * 3] += velocities[i].x;
                        pos[i * 3 + 1] += velocities[i].y;
                        pos[i * 3 + 2] += velocities[i].z;

                        // Reset if too far
                        const dist = Math.sqrt(pos[i * 3] ** 2 + pos[i * 3 + 1] ** 2 + pos[i * 3 + 2] ** 2);
                        if (dist > 3) {
                            pos[i * 3] = 0;
                            pos[i * 3 + 1] = 0;
                            pos[i * 3 + 2] = 0;
                        }
                    }
                    particles.geometry.attributes.position.needsUpdate = true;
                }
            };
        };

        // SURGICAL: Precision targeting grid with crosshair
        const buildSurgical = () => {
            camera.position.set(0, 0, 4);
            camera.lookAt(0, 0, 0);

            // Targeting grid
            const gridHelper = new THREE.GridHelper(4, 20, colors.secondary, colors.secondary);
            gridHelper.rotation.x = Math.PI / 2;
            gridHelper.material.opacity = 0.15;
            gridHelper.material.transparent = true;
            contentGroup.add(gridHelper);

            // Concentric target rings
            const targetRings: THREE.Mesh[] = [];
            for (let i = 1; i <= 4; i++) {
                const rGeo = new THREE.RingGeometry(i * 0.35 - 0.02, i * 0.35, 32);
                const rMat = new THREE.MeshBasicMaterial({
                    color: colors.primary,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: 0.5 - i * 0.1
                });
                const ring = new THREE.Mesh(rGeo, rMat);
                targetRings.push(ring);
                contentGroup.add(ring);
            }

            // Crosshair lines
            const crossMat = new THREE.MeshBasicMaterial({ color: colors.accent });
            const hLine = new THREE.Mesh(new THREE.BoxGeometry(3, 0.02, 0.02), crossMat);
            const vLine = new THREE.Mesh(new THREE.BoxGeometry(0.02, 3, 0.02), crossMat);
            contentGroup.add(hLine, vLine);

            // Center dot
            const dotGeo = new THREE.CircleGeometry(0.08, 16);
            const dotMat = new THREE.MeshBasicMaterial({ color: colors.primary });
            const dot = new THREE.Mesh(dotGeo, dotMat);
            contentGroup.add(dot);

            // Targeting lock indicators
            const brackets: THREE.Group[] = [];
            for (let i = 0; i < 4; i++) {
                const bracket = new THREE.Group();
                const b1 = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.02, 0.02), crossMat.clone());
                const b2 = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.2, 0.02), crossMat.clone());
                b1.position.set(0.1, 0, 0);
                b2.position.set(0, 0.1, 0);
                bracket.add(b1, b2);
                bracket.rotation.z = i * Math.PI / 2;
                brackets.push(bracket);
                contentGroup.add(bracket);
            }

            return {
                update: (t: number) => {
                    // Pulsing rings
                    targetRings.forEach((ring, i) => {
                        ring.scale.setScalar(1 + Math.sin(t * 2 + i * 0.5) * 0.05);
                    });

                    // Rotating grid
                    gridHelper.rotation.z = t * 0.1;

                    // Pulsing center dot
                    dot.scale.setScalar(1 + Math.sin(t * 4) * 0.2);

                    // Lock-on brackets animation
                    const lockOffset = 0.8 + Math.sin(t * 2) * 0.1;
                    brackets.forEach((bracket, i) => {
                        const angle = i * Math.PI / 2;
                        bracket.position.x = Math.cos(angle) * lockOffset;
                        bracket.position.y = Math.sin(angle) * lockOffset;
                    });
                }
            };
        };

        // STEALTH: Ghost particles with stealth radar sweep
        const buildStealth = () => {
            camera.position.set(0, 2, 4);
            camera.lookAt(0, 0, 0);

            // Radar grid (flat)
            const radarGrid = new THREE.PolarGridHelper(2, 8, 6, 32, colors.secondary, colors.secondary);
            radarGrid.material.opacity = 0.2;
            radarGrid.material.transparent = true;
            contentGroup.add(radarGrid);

            // Sweep line with glow
            const sweepGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, 0, 2)
            ]);
            const sweepMat = new THREE.LineBasicMaterial({ color: colors.primary, transparent: true, opacity: 0.8 });
            const sweep = new THREE.Line(sweepGeo, sweepMat);
            contentGroup.add(sweep);

            // Ghost particles (fade in/out)
            const ghostCount = 25;
            const ghosts: { mesh: THREE.Mesh; baseOpacity: number; phase: number }[] = [];
            const ghostGeo = new THREE.SphereGeometry(0.05, 8, 8);

            for (let i = 0; i < ghostCount; i++) {
                const ghostMat = new THREE.MeshBasicMaterial({
                    color: colors.accent,
                    transparent: true,
                    opacity: 0
                });
                const ghost = new THREE.Mesh(ghostGeo, ghostMat);
                const angle = Math.random() * Math.PI * 2;
                const radius = 0.3 + Math.random() * 1.7;
                ghost.position.x = Math.cos(angle) * radius;
                ghost.position.z = Math.sin(angle) * radius;
                ghost.position.y = Math.random() * 0.5;
                ghosts.push({
                    mesh: ghost,
                    baseOpacity: 0.3 + Math.random() * 0.4,
                    phase: Math.random() * Math.PI * 2
                });
                contentGroup.add(ghost);
            }

            // Stealth silhouette (wireframe figure)
            const figureGeo = new THREE.ConeGeometry(0.3, 0.8, 4);
            const figureMat = new THREE.MeshBasicMaterial({
                color: colors.primary,
                wireframe: true,
                transparent: true,
                opacity: 0.4
            });
            const figure = new THREE.Mesh(figureGeo, figureMat);
            figure.position.y = 0.5;
            contentGroup.add(figure);

            return {
                update: (t: number) => {
                    // Rotating sweep
                    sweep.rotation.y = -t * 1.5;

                    // Ghost particles flicker
                    ghosts.forEach((g) => {
                        const flicker = Math.sin(t * 3 + g.phase) * 0.5 + 0.5;
                        (g.mesh.material as THREE.MeshBasicMaterial).opacity = g.baseOpacity * flicker;
                        g.mesh.position.y = 0.1 + Math.sin(t + g.phase) * 0.1;
                    });

                    // Figure hover and pulse
                    figure.position.y = 0.5 + Math.sin(t * 2) * 0.1;
                    figure.rotation.y = t * 0.5;
                    (figure.material as THREE.MeshBasicMaterial).opacity = 0.3 + Math.sin(t * 4) * 0.1;

                    // Slow grid rotation
                    radarGrid.rotation.y = t * 0.05;
                }
            };
        };

        // SELECT BUILDER
        let updater: { update: (t: number) => void } | null = null;

        if (activeMode === 'overwatch') updater = buildOverwatch();
        else if (activeMode === 'strike') updater = buildStrike();
        else if (activeMode === 'surgical') updater = buildSurgical();
        else if (activeMode === 'stealth') updater = buildStealth();
        else updater = buildOverwatch(); // Default fallback

        // ANIMATION LOOP
        let animId: number;
        let time = 0;

        const animate = () => {
            animId = requestAnimationFrame(animate);
            time += 0.016; // ~60fps

            if (updater && updater.update) updater.update(time);

            renderer.render(scene, camera);
        };
        animate();

        // RESIZE
        const resizeObserver = new ResizeObserver(() => {
            if (!container) return;
            const width = container.clientWidth;
            const height = container.clientHeight;
            if (width === 0 || height === 0) return;
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
            renderer.setSize(width, height);
        });
        resizeObserver.observe(container);

        return () => {
            resizeObserver.disconnect();
            cancelAnimationFrame(animId);
            canvas.removeEventListener('webglcontextlost', handleContextLost);
            renderer.dispose();
            contentGroup.clear();
        };

    }, [activeMode, hasWebGLError]);

    // Fallback icon for current mode
    const FallbackIcon = {
        overwatch: Binoculars,
        strike: Lightning,
        surgical: Crosshair,
        stealth: Ghost,
    }[activeMode] || Binoculars;

    const fallbackColor = {
        overwatch: 'text-cyan-400',
        strike: 'text-amber-400',
        surgical: 'text-purple-400',
        stealth: 'text-violet-400',
    }[activeMode] || 'text-cyan-400';

    if (hasWebGLError) {
        return (
            <div ref={containerRef} className="w-full h-full min-h-[250px] relative flex items-center justify-center bg-black/40 rounded-xl">
                <div className="text-center space-y-4">
                    <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full bg-black/40 border border-white/10 ${fallbackColor} animate-pulse`}>
                        <FallbackIcon size={40} weight="duotone" />
                    </div>
                    <div className="font-mono text-muted-foreground text-xs tracking-widest uppercase">
                        {activeMode.toUpperCase()} MODE
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full h-full min-h-[250px] lg:min-h-[350px] relative rounded-xl overflow-hidden">
            <canvas ref={canvasRef} className="w-full h-full" />

            {/* HUD Overlay */}
            <div className="absolute inset-0 pointer-events-none">
                {/* Top bar */}
                <div className="absolute top-0 left-0 right-0 h-8 border-b border-white/10 bg-gradient-to-b from-black/40 to-transparent flex items-center justify-between px-4">
                    <span className="text-[10px] font-mono text-white/40 tracking-widest">MODE.VISUAL</span>
                    <div className="flex gap-1">
                        <div className="w-1 h-1 bg-white/30 rounded-full" />
                        <div className="w-1 h-1 bg-white/30 rounded-full" />
                        <div className="w-1 h-1 bg-white/30 rounded-full" />
                    </div>
                </div>

                {/* Corner brackets */}
                <div className="absolute top-4 left-4 w-3 h-3 border-t border-l border-white/20" />
                <div className="absolute top-4 right-4 w-3 h-3 border-t border-r border-white/20" />
                <div className="absolute bottom-4 left-4 w-3 h-3 border-b border-l border-white/20" />
                <div className="absolute bottom-4 right-4 w-3 h-3 border-b border-r border-white/20" />

                {/* Status indicator */}
                <div className="absolute bottom-3 right-3 px-2 py-1 border border-white/10 rounded-full bg-black/60 backdrop-blur text-[10px] font-mono text-emerald-500 flex items-center gap-1.5">
                    <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
                    ACTIVE
                </div>
            </div>
        </div>
    );
}
