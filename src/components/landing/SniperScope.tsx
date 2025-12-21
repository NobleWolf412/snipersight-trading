/**
 * SniperScope - Animated 3D candlestick scope visualization
 * 
 * Creates a military-style scope overlay with Three.js candlestick chart
 * that slowly rotates with targeting reticle.
 */

import { useEffect, useRef, ReactNode } from 'react';
import * as THREE from 'three';

interface SniperScopeProps {
    className?: string;
    children?: ReactNode; // Content to display in center of reticle
}

export function SniperScope({ className = '', children }: SniperScopeProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!canvasRef.current || !containerRef.current) return;

        const canvas = canvasRef.current;
        const container = containerRef.current;

        // Create Scene
        const scene = new THREE.Scene();
        // scene.fog = new THREE.Fog(0x020405, 4, 14); // Disable fog for clearer bg view

        // Create Camera
        const camera = new THREE.PerspectiveCamera(
            50,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        camera.position.set(0, 0, 5);
        camera.lookAt(0, 0, 0);

        // Create Renderer
        const renderer = new THREE.WebGLRenderer({
            canvas,
            antialias: true,
            alpha: true
        });
        renderer.setClearColor(0x000000, 0); // Transparent background
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Handle resize
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

        const greenCandle = 0x00ff88;
        const redCandle = 0xff3333;

        const chartGroup = new THREE.Group();
        scene.add(chartGroup);

        // Generate candlestick data properly typed
        interface Candle { open: number; high: number; low: number; close: number; bullish: boolean; }

        const generateCandleData = (count: number): Candle[] => {
            const candles: Candle[] = [];
            let price = 100;

            for (let i = 0; i < count; i++) {
                const volatility = 1.5 + Math.random() * 3;
                const direction = Math.random() > 0.42 ? 1 : -1;
                const open = price;
                const close = price + direction * volatility * Math.random();
                const high = Math.max(open, close) + Math.random() * volatility * 0.5;
                const low = Math.min(open, close) - Math.random() * volatility * 0.5;

                candles.push({ open, high, low, close, bullish: close > open });
                price = close;
            }
            return candles;
        };

        const candleData = generateCandleData(28);
        const candleWidth = 0.08;
        const candleSpacing = 0.18;

        const allPrices = candleData.flatMap(c => [c.high, c.low]);
        const minPrice = Math.min(...allPrices);
        const maxPrice = Math.max(...allPrices);
        const priceRange = maxPrice - minPrice;
        const normalize = (price: number) => ((price - minPrice) / priceRange - 0.5) * 2;

        // Create candlesticks
        candleData.forEach((candle, i) => {
            const x = (i - candleData.length / 2) * candleSpacing;
            const z = (i - candleData.length / 2) * 0.08;

            const openY = normalize(candle.open);
            const closeY = normalize(candle.close);
            const highY = normalize(candle.high);
            const lowY = normalize(candle.low);

            const bodyHeight = Math.abs(closeY - openY);
            const bodyY = (openY + closeY) / 2;

            const color = candle.bullish ? greenCandle : redCandle;
            const opacity = 0.95 - ((candleData.length - 1 - i) * 0.02);

            // Body
            const bodyGeom = new THREE.BoxGeometry(candleWidth, Math.max(bodyHeight, 0.015), candleWidth * 0.6);
            const bodyMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity });
            const body = new THREE.Mesh(bodyGeom, bodyMat);
            body.position.set(x, bodyY, z);
            chartGroup.add(body);

            // Glow for recent candles
            if (i >= candleData.length - 6) {
                const glowGeom = new THREE.BoxGeometry(candleWidth * 2.5, Math.max(bodyHeight, 0.015) * 2, candleWidth * 2);
                const glowMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.1 });
                const glow = new THREE.Mesh(glowGeom, glowMat);
                glow.position.set(x, bodyY, z);
                chartGroup.add(glow);
            }

            // Wick
            const wickGeom = new THREE.CylinderGeometry(0.006, 0.006, highY - lowY, 4);
            const wickMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: opacity * 0.6 });
            const wick = new THREE.Mesh(wickGeom, wickMat);
            wick.position.set(x, (highY + lowY) / 2, z);
            chartGroup.add(wick);
        });

        // Grid
        const gridHelper = new THREE.GridHelper(6, 20, 0x00ff88, 0x00ff88);
        gridHelper.material.transparent = true;
        gridHelper.material.opacity = 0.06;
        gridHelper.position.y = -1.2;
        chartGroup.add(gridHelper);

        // Price levels
        for (let i = 0; i < 5; i++) {
            const y = -0.8 + i * 0.4;
            const points = [new THREE.Vector3(-3, y, -1.5), new THREE.Vector3(3, y, 1.5)];
            const geom = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.04 });
            chartGroup.add(new THREE.Line(geom, mat));
        }

        // Order block
        const obGeom = new THREE.BoxGeometry(1, 0.3, 0.3);
        const obMat = new THREE.MeshBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.05 });
        const ob = new THREE.Mesh(obGeom, obMat);
        ob.position.set(0.8, -0.2, 0.6);
        chartGroup.add(ob);

        const obEdges = new THREE.EdgesGeometry(obGeom);
        const obLine = new THREE.LineSegments(obEdges, new THREE.LineBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.25 }));
        obLine.position.copy(ob.position);
        chartGroup.add(obLine);

        // Liquidity sweep line
        const liqY = 0.9;
        const liqPoints: THREE.Vector3[] = [];
        for (let i = 0; i < 30; i += 2) {
            liqPoints.push(new THREE.Vector3(-2.5 + i * 0.15, liqY, -1 + i * 0.06));
            liqPoints.push(new THREE.Vector3(-2.5 + (i + 0.7) * 0.15, liqY, -1 + (i + 0.7) * 0.06));
        }
        const liqGeom = new THREE.BufferGeometry().setFromPoints(liqPoints);
        const liqLine = new THREE.LineSegments(liqGeom, new THREE.LineBasicMaterial({ color: 0xff4444, transparent: true, opacity: 0.4 }));
        chartGroup.add(liqLine);

        // Target on current candle
        const lastCandle = candleData[candleData.length - 1];
        const lastX = (candleData.length - 1 - candleData.length / 2) * candleSpacing;
        const lastZ = (candleData.length - 1 - candleData.length / 2) * 0.08;
        const lastY = normalize(lastCandle.close);

        const targetGroup = new THREE.Group();

        const ringGeom = new THREE.RingGeometry(0.12, 0.15, 24);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.8, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        targetGroup.add(ring);

        const ring2Geom = new THREE.RingGeometry(0.2, 0.22, 24);
        const ring2Mat = new THREE.MeshBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.3, side: THREE.DoubleSide });
        const ring2 = new THREE.Mesh(ring2Geom, ring2Mat);
        targetGroup.add(ring2);

        // Target cross
        [[0.25, 0, 0.1, 0], [-0.25, 0, -0.1, 0], [0, 0.25, 0, 0.1], [0, -0.25, 0, -0.1]].forEach(([x1, y1, x2, y2]) => {
            const pts = [new THREE.Vector3(x1, y1, 0), new THREE.Vector3(x2, y2, 0)];
            const g = new THREE.BufferGeometry().setFromPoints(pts);
            targetGroup.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.9 })));
        });

        targetGroup.position.set(lastX + 0.25, lastY, lastZ + 0.05);
        chartGroup.add(targetGroup);

        // Particles
        const particleCount = 80;
        const particleGeom = new THREE.BufferGeometry();
        const particlePos = new Float32Array(particleCount * 3);
        for (let i = 0; i < particleCount; i++) {
            particlePos[i * 3] = (Math.random() - 0.5) * 12;
            particlePos[i * 3 + 1] = (Math.random() - 0.5) * 6;
            particlePos[i * 3 + 2] = (Math.random() - 0.5) * 10;
        }
        particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
        const particles = new THREE.Points(particleGeom, new THREE.PointsMaterial({ color: 0x00ff88, size: 0.025, transparent: true, opacity: 0.35 }));
        scene.add(particles);

        // Animation loop
        let time = 0;
        let animationId: number;

        const animate = () => {
            animationId = requestAnimationFrame(animate);
            time += 0.004;

            // Gentle rotation
            chartGroup.rotation.y = Math.sin(time * 0.4) * 0.3;
            chartGroup.rotation.x = Math.sin(time * 0.25) * 0.06;

            // Pulse target
            const pulse = Math.sin(time * 10) * 0.15 + 1;
            ring.scale.setScalar(pulse);
            ring.material.opacity = 0.6 + Math.sin(time * 10) * 0.25;
            ring2.scale.setScalar(1 + Math.sin(time * 6) * 0.1);

            // Target always faces camera
            targetGroup.lookAt(camera.position);

            // Particles drift
            particles.rotation.y = time * 0.05;

            // Subtle camera movement
            camera.position.y = Math.sin(time * 0.3) * 0.1;
            camera.position.x = Math.sin(time * 0.2) * 0.15;
            camera.lookAt(0, 0, 0);

            renderer.render(scene, camera);
        };
        animate();

        // Cleanup
        return () => {
            resizeObserver.disconnect();
            cancelAnimationFrame(animationId);

            if (renderer) {
                renderer.dispose();
            }
        };
    }, []);

    return (
        <div ref={containerRef} className={`sniper-scope ${className}`} style={{ position: 'relative', width: '100%', height: '100%' }}>
            <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />

            {/* Scope mask */}
            <div className="scope-mask" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 5 }}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" style={{ width: '100%', height: '100%' }}>
                    <defs>
                        <mask id="scopeMask">
                            <rect width="100" height="100" fill="white" />
                            <circle cx="50" cy="50" r="26" fill="black" />
                        </mask>
                    </defs>
                    <rect width="100" height="100" fill="#000" mask="url(#scopeMask)" />
                    <circle cx="50" cy="50" r="26" fill="none" stroke="#111" strokeWidth="1.5" />
                    <circle cx="50" cy="50" r="26.8" fill="none" stroke="#1a1a1a" strokeWidth="0.3" />
                </svg>
            </div>

            {/* Scope glow */}
            <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '55vmin',
                height: '55vmin',
                borderRadius: '50%',
                boxShadow: 'inset 0 0 60px rgba(0, 255, 136, 0.1), inset 0 0 120px rgba(0, 0, 0, 0.5)',
                pointerEvents: 'none',
                zIndex: 6
            }} />

            {/* Scope reticle */}
            <div className="scope-reticle" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10 }}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" style={{ width: '100%', height: '100%' }}>
                    {/* Crosshairs */}
                    <line x1="50" y1="24" x2="50" y2="42" stroke="#00ff88" strokeWidth="0.2" opacity="0.9" />
                    <line x1="50" y1="58" x2="50" y2="76" stroke="#00ff88" strokeWidth="0.2" opacity="0.9" />
                    <line x1="24" y1="50" x2="42" y2="50" stroke="#00ff88" strokeWidth="0.2" opacity="0.9" />
                    <line x1="58" y1="50" x2="76" y2="50" stroke="#00ff88" strokeWidth="0.2" opacity="0.9" />

                    {/* Center brackets */}
                    <path d="M 46 46 L 46 43 L 43 43" fill="none" stroke="#00ff88" strokeWidth="0.3" opacity="1" />
                    <path d="M 54 46 L 54 43 L 57 43" fill="none" stroke="#00ff88" strokeWidth="0.3" opacity="1" />
                    <path d="M 46 54 L 46 57 L 43 57" fill="none" stroke="#00ff88" strokeWidth="0.3" opacity="1" />
                    <path d="M 54 54 L 54 57 L 57 57" fill="none" stroke="#00ff88" strokeWidth="0.3" opacity="1" />

                    {/* Center dot */}
                    <circle cx="50" cy="50" r="0.4" fill="#00ff88" opacity="0.9" />

                    {/* Rings */}
                    <circle cx="50" cy="50" r="18" fill="none" stroke="#00ff88" strokeWidth="0.1" opacity="0.3" />
                    <circle cx="50" cy="50" r="24" fill="none" stroke="#00ff88" strokeWidth="0.15" opacity="0.4" />

                    {/* Mil-dots */}
                    <circle cx="50" cy="27" r="0.5" fill="#00ff88" opacity="0.6" />
                    <circle cx="50" cy="73" r="0.5" fill="#00ff88" opacity="0.6" />
                    <circle cx="27" cy="50" r="0.5" fill="#00ff88" opacity="0.6" />
                    <circle cx="73" cy="50" r="0.5" fill="#00ff88" opacity="0.6" />
                </svg>
            </div>

            {/* Center content slot - Optional */}
            {children && (
                <div style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    zIndex: 20,
                    pointerEvents: 'auto'
                }}>
                    {children}
                </div>
            )}

            {/* Scan line */}
            <div style={{
                position: 'absolute',
                left: '25%',
                right: '25%',
                height: '1px',
                background: 'linear-gradient(90deg, transparent, rgba(0, 255, 136, 0.3), transparent)',
                animation: 'scopeScanV 5s linear infinite',
                pointerEvents: 'none',
                zIndex: 15
            }} />

            <style>{`
        @keyframes scopeScanV {
          0% { top: 25%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 75%; opacity: 0; }
        }
      `}</style>
        </div>
    );
}

export default SniperScope;
