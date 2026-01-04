// Placeholder - Fresh Redesign Coming
import { useNavigate } from 'react-router-dom';
import { TacticalBackground } from '@/components/ui/TacticalBackground';
import { NavigationRail } from '@/components/layout/NavigationRail';

export function ScanResults() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#030504] text-white relative overflow-hidden">
      <TacticalBackground variant="grid" />
      <NavigationRail />

      <div className="flex items-center justify-center h-screen">
        <div className="text-center space-y-6">
          <div className="text-6xl">🚧</div>
          <h1 className="text-3xl font-bold text-[#00ff88]">Redesign In Progress</h1>
          <p className="text-zinc-400 max-w-md">
            This page is being rebuilt from scratch.
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-3 bg-[#00ff88]/10 border border-[#00ff88]/50 rounded-lg text-[#00ff88] hover:bg-[#00ff88]/20 transition-all"
          >
            Back to Scanner
          </button>
        </div>
      </div>
    </div>
  );
}

export default ScanResults;
