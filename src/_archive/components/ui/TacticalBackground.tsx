/**
 * TacticalBackground - Parallax Night Vision Background System
 * 
 * A reusable 4-layer animated background that creates depth and
 * a surveillance/intelligence aesthetic across all pages.
 * 
 * Layers (back to front):
 * 1. Base darkness gradient
 * 2. Film grain noise
 * 3. Ambient glow zones
 * 4. Scan lines
 * 5. Tactical micro-grid
 */

interface TacticalBackgroundProps {
    /** Show/hide scan lines layer */
    showScanlines?: boolean;
    /** Show/hide grain texture */
    showGrain?: boolean;
    /** Show/hide ambient glow */
    showGlow?: boolean;
    /** Show/hide micro-grid */
    showGrid?: boolean;
}

export function TacticalBackground({
    showScanlines = true,
    showGrain = true,
    showGlow = true,
    showGrid = true,
}: TacticalBackgroundProps) {
    return (
        <div aria-hidden="true" className="tactical-background-container">
            {/* Layer 1: Base darkness */}
            <div className="tactical-bg-base" />

            {/* Layer 2: Film grain noise */}
            {showGrain && <div className="tactical-bg-grain" />}

            {/* Layer 3: Ambient glow zones */}
            {showGlow && <div className="tactical-bg-glow" />}

            {/* Layer 4: Scan lines */}
            {showScanlines && <div className="tactical-bg-scanlines" />}

            {/* Layer 5: Tactical micro-grid */}
            {showGrid && <div className="tactical-bg-grid" />}
        </div>
    );
}
