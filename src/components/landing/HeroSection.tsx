import { Compass } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import sniperLogo from '@/assets/images/1000016768.png';

export function HeroSection() {
  return (
    <section className="relative min-h-[75vh] flex items-center justify-center overflow-hidden">
      {/* Background - Clean Grid or subtle noise could go here later */}
      <div className="absolute inset-0 z-0 bg-background" />

      {/* Content */}
      <div className="relative z-10 text-center px-4 max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="space-y-8"
        >
          {/* Status badge */}
          <div className="inline-flex items-center gap-3 px-4 py-2 glass-card-subtle glow-border-green">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse shadow-[0_0_8px_rgba(0,255,170,0.8)]" />
            <span className="text-xs tracking-[0.3em] text-accent/80 uppercase">System Online</span>
          </div>

          {/* Logo with Background Halo Ring */}
          <div className="relative inline-block">
            {/* The Green Ring Vignette (Behind Logo) */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full pointer-events-none"
              style={{
                width: '180%',   // Larger than logo
                height: '180%',  // Larger than logo
                zIndex: -1,      // Behind logo
                background: 'radial-gradient(circle, transparent 30%, rgba(0, 255, 136, 0.25) 50%, rgba(0, 255, 136, 0.1) 70%, transparent 80%)',
                filter: 'blur(20px)', // Soften the ring
              }}
            />
            {/* Optional: Inner intense glow for core */}
            <div className="absolute inset-0 bg-accent/20 blur-[50px] rounded-full z-[-1]" />

            <img
              src={sniperLogo}
              alt="SniperSight"
              className="relative h-24 md:h-32 lg:h-40 w-auto drop-shadow-[0_0_30px_rgba(0,255,170,0.4)]"
            />
          </div>

          {/* Headline */}
          <h1 className="display-headline text-foreground">
            Precision Market
            <span className="block text-accent">Intelligence</span>
          </h1>

          {/* Subheadline */}
          <p className="display-subheadline max-w-2xl mx-auto">
            Crypto reconnaissance • Confluence scoring • Risk control
          </p>


        </motion.div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent z-20" />
    </section>
  );
}
