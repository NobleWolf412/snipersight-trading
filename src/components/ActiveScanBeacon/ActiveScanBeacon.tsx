import { useScanner } from '@/context/ScannerContext';
import { Link,useLocation } from 'react-router-dom';
import './ActiveScanBeacon.css';
export function ActiveScanBeacon() {
  const { isScanning, isBotActive, isPaperBotActive } = useScanner();
  const { pathname } = useLocation();
  const active = [
    { running: isBotActive, route: '/bot/status', label: 'Bot running' },
    { running: isPaperBotActive, route: '/training/range', label: 'Paper session running' },
    { running: isScanning, route: '/scanner', label: 'Scan running' },
  ].filter(item => item.running && !pathname.startsWith(item.route));
  if (!active.length) return null;
  return <nav className="active-scan-beacon" aria-label="Running tasks">
    {active.map(item => <Link key={item.route} className="btn" to={item.route}>{item.label} →</Link>)}
  </nav>;
}
