import { Compass } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import sniperLogo from '@/assets/images/1000016768.png';
// import { SniperScope } from './SniperScope';

export function HeroSection() {
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
      {/* Background Effect - Green Vignette */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-accent/10 via-background to-background" />
      </div>

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

          {/* Logo */}
          <div className="relative inline-block">
            <div className="absolute inset-0 bg-accent/30 blur-[80px] rounded-full" />
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

          {/* CTA Button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3, ease: "easeOut" }}
            className="flex items-center justify-center pt-4"
          >
            <Link
              to="/intel"
              className="group flex items-center gap-3 px-8 py-4 glass-card glow-border-green hover:bg-accent/10 transition-all duration-300"
            >
              <Compass size={24} weight="bold" className="text-accent" />
              <span className="text-lg font-bold tracking-wider text-foreground group-hover:text-accent transition-colors">
                View Intel
              </span>
              <span className="text-accent group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </motion.div>
        </motion.div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent z-20" />
    </section>
  );
}
