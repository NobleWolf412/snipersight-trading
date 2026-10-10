import { useScanner } from '@/context/ScannerContext';
import { Link, useLocation } from 'react-router-dom';
import './ActiveScanBeacon.css';
export function ActiveScanBeacon() {
  const { isScanning, isBotActive, isPaperBotActive } = useScanner();
  const { pathname } = useLocation();
  const active = [
    { kind: 'bot', running: isBotActive, route: '/bot/status', label: 'Bot running', code: 'BOT' },
    { kind: 'paper', running: isPaperBotActive, route: '/training/range#status', label: 'Paper session running', code: 'PAPER' },
    { kind: 'scan', running: isScanning, route: '/scanner', label: 'Scan running', code: 'SCAN' },
  ].filter(item => item.running && (
    item.kind === 'paper' || !pathname.startsWith(item.route)
  ));
  if (!active.length) return null;
  return (
    <nav className="active-scan-beacon" aria-label="Running tasks" data-count={active.length}>
      {active.map(item => (
        <Link
          key={item.kind}
          className={`active-scan-beacon__link active-scan-beacon__link--${item.kind}`}
          to={item.route}
          aria-label={`${item.label}, open status`}
        >
          <span className="active-scan-beacon__radar" aria-hidden="true">
            <span className="active-scan-beacon__core" />
          </span>
          <span className="active-scan-beacon__text">
            <span className="active-scan-beacon__code">{item.code}</span>
            <span className="active-scan-beacon__state">{item.label}</span>
          </span>
          <span className="active-scan-beacon__arrow" aria-hidden="true">↗</span>
        </Link>
      ))}
    </nav>
  );
}
