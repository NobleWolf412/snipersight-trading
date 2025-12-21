import { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface ArsenalVisualsProps {
    activeTab: string;
}

export function ArsenalVisuals({ activeTab }: ArsenalVisualsProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        if (!containerRef.current || !canvasRef.current) return;

        const container = containerRef.current;
        const canvas = canvasRef.current;

        // SETUP
        const scene = new THREE.Scene();
        // scene.visible = false; // Fade in?

        const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100);
        camera.position.z = 5;

        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // GROUP
        const contentGroup = new THREE.Group();
        scene.add(contentGroup);

        // -- SCENE BUILDERS --

        // 1. SCANNER: Radar Sweep
        const buildScanner = () => {
            // Radar Grid
            const grid = new THREE.PolarGridHelper(2, 8, 8, 64, 0x00ff88, 0x00ff88);
            grid.rotation.x = 0;//Face camera? No, flat.
            // Rotate grid to face camera
            grid.rotation.x = Math.PI / 2;
            contentGroup.add(grid);

            // Sweep Line
            const lineGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, 2, 0)
            ]);
            const lineMat = new THREE.LineBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.8 });
            const sweep = new THREE.Line(lineGeo, lineMat);
            // Center is at 0,0,0. Radar lies on XY plane if we rotate grid?
            // PolarGrid lies on XZ plane by default. 
            // Let's use XZ plane logic.
            grid.rotation.x = 0; // Flat
            // Camera at (0,3,5) looking at 0,0,0?
            camera.position.set(0, 3, 4);
            camera.lookAt(0, 0, 0);

            // Sweep geometry on XZ
            const sweepGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, 0, 2) // Length 2
            ]);
            const sweepLine = new THREE.Line(sweepGeo, lineMat);
            contentGroup.add(sweepLine);

            // Blips
            const blipGeo = new THREE.CircleGeometry(0.05, 8);
            const blipMat = new THREE.MeshBasicMaterial({ color: 0xff3333 });
            const blip = new THREE.Mesh(blipGeo, blipMat);
            blip.rotation.x = -Math.PI / 2;
            blip.position.set(1, 0, 1);
            contentGroup.add(blip);

            return {
                update: (t: number) => {
                    sweepLine.rotation.y = -t * 2;
                    // Blink blip
                    blip.material.opacity = Math.sin(t * 10) > 0 ? 1 : 0.2;
                    blip.material.transparent = true;

                    // Rotate grid slowly
                    grid.rotation.y = t * 0.1;
                }
            };
        };

        // 2. BOT: Neural Network / AI Core
        const buildBot = () => {
            camera.position.set(0, 0, 5);
            camera.lookAt(0, 0, 0);

            // Particles
            const count = 40;
            const geo = new THREE.BufferGeometry();
            const pos = new Float32Array(count * 3);
            const vel: { x: number, y: number, z: number }[] = [];

            for (let i = 0; i < count * 3; i++) {
                pos[i] = (Math.random() - 0.5) * 4;
            }
            geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));

            for (let i = 0; i < count; i++) {
                vel.push({
                    x: (Math.random() - 0.5) * 0.01,
                    y: (Math.random() - 0.5) * 0.01,
                    z: (Math.random() - 0.5) * 0.01
                });
            }

            const mat = new THREE.PointsMaterial({ color: 0x0088ff, size: 0.1 });
            const points = new THREE.Points(geo, mat);
            contentGroup.add(points);

            // Connections (raycast or distance check ideally, but simplified visual)
            const linesGeo = new THREE.BufferGeometry();
            const linesMat = new THREE.LineBasicMaterial({ color: 0x0088ff, transparent: true, opacity: 0.2 });
            const lines = new THREE.LineSegments(linesGeo, linesMat);
            contentGroup.add(lines);

            return {
                update: (t: number) => {
                    contentGroup.rotation.y = t * 0.1;

                    // Update positions
                    const positions = (points.geometry.attributes.position as THREE.BufferAttribute).array as Float32Array;
                    for (let i = 0; i < count; i++) {
                        positions[i * 3] += vel[i].x;
                        positions[i * 3 + 1] += vel[i].y;
                        positions[i * 3 + 2] += vel[i].z;

                        // Bounds check
                        if (Math.abs(positions[i * 3]) > 2) vel[i].x *= -1;
                        if (Math.abs(positions[i * 3 + 1]) > 2) vel[i].y *= -1;
                        if (Math.abs(positions[i * 3 + 2]) > 2) vel[i].z *= -1;
                    }
                    points.geometry.attributes.position.needsUpdate = true;

                    // Update lines (connect close points)
                    const linePos: number[] = [];
                    for (let i = 0; i < count; i++) {
                        for (let j = i + 1; j < count; j++) {
                            const dx = positions[i * 3] - positions[j * 3];
                            const dy = positions[i * 3 + 1] - positions[j * 3 + 1];
                            const dz = positions[i * 3 + 2] - positions[j * 3 + 2];
                            const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
                            if (dist < 1.2) {
                                linePos.push(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
                                linePos.push(positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2]);
                            }
                        }
                    }
                    lines.geometry.setAttribute('position', new THREE.Float32BufferAttribute(linePos, 3));
                }
            };
        };

        // 3. INTEL: Wireframe Globe
        const buildIntel = () => {
            camera.position.set(0, 0, 4.5);
            camera.lookAt(0, 0, 0);

            const geo = new THREE.IcosahedronGeometry(2, 2);
            const mat = new THREE.MeshBasicMaterial({ color: 0x4444ff, wireframe: true, transparent: true, opacity: 0.3 });
            const globe = new THREE.Mesh(geo, mat);
            contentGroup.add(globe);

            // Data spikes
            const spikes = new THREE.Group();
            for (let i = 0; i < 10; i++) {
                const h = 0.5 + Math.random() * 0.5;
                const spike = new THREE.Mesh(new THREE.BoxGeometry(0.05, h, 0.05), new THREE.MeshBasicMaterial({ color: 0x00ffff }));
                // Random pos on sphere surface? 
                const phi = Math.random() * Math.PI * 2;
                const theta = Math.random() * Math.PI;
                const r = 2;
                spike.position.setFromSphericalCoords(r + h / 2, theta, phi);
                spike.lookAt(0, 0, 0);
                spikes.add(spike);
            }
            globe.add(spikes);

            return {
                update: (t: number) => {
                    globe.rotation.y = t * 0.2;
                    globe.rotation.x = Math.sin(t * 0.5) * 0.1;
                }
            };
        };

        // 4. TRAINING: Target Practice
        const buildTraining = () => {
            camera.position.set(0, 0, 5);
            camera.lookAt(0, 0, 0);

            // Target Rings
            const r1 = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.6, 32), new THREE.MeshBasicMaterial({ color: 0xffaa00, side: THREE.DoubleSide }));
            const r2 = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.3, 32), new THREE.MeshBasicMaterial({ color: 0xffaa00, side: THREE.DoubleSide }));
            const r3 = new THREE.Mesh(new THREE.RingGeometry(1.9, 2.0, 32), new THREE.MeshBasicMaterial({ color: 0xffaa00, side: THREE.DoubleSide }));
            contentGroup.add(r1, r2, r3);

            // Crosshair
            const ch = new THREE.Group();
            const l1 = new THREE.Mesh(new THREE.BoxGeometry(4, 0.05, 0.05), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
            const l2 = new THREE.Mesh(new THREE.BoxGeometry(0.05, 4, 0.05), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
            ch.add(l1, l2);
            contentGroup.add(ch);

            return {
                update: (t: number) => {
                    // Rings pulsate
                    r1.scale.setScalar(1 + Math.sin(t * 4) * 0.05);
                    r2.scale.setScalar(1 + Math.sin(t * 4 + 1) * 0.05);
                    r3.scale.setScalar(1 + Math.sin(t * 4 + 2) * 0.05);

                    // Crosshair moves
                    ch.position.x = Math.sin(t) * 1;
                    ch.position.y = Math.cos(t * 1.5) * 1;
                    ch.rotation.z = Math.sin(t) * 0.1;
                }
            };
        };

        // SELECT BUILDER
        let updater: { update: (t: number) => void } | null = null;

        if (activeTab === 'scanner') updater = buildScanner();
        else if (activeTab === 'bot') updater = buildBot();
        else if (activeTab === 'intel') updater = buildIntel();
        else if (activeTab === 'training') updater = buildTraining();

        // ANIMATION LOOP
        let animId: number;
        let time = 0;

        const animate = () => {
            animId = requestAnimationFrame(animate);
            time += 0.01;

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
            renderer.dispose();
            // In full prod, dispose all geometries
            contentGroup.clear();
        };

    }, [activeTab]);

    return (
        <div ref={containerRef} className="w-full h-full min-h-[300px] relative">
            <canvas ref={canvasRef} className="w-full h-full" />

            {/* Overlay Gradient for Text Readability if needed, though we put text on Left */}
            <div className="absolute inset-0 bg-gradient-to-l from-transparent via-transparent to-background/10 pointer-events-none" />
        </div>
    );
}
