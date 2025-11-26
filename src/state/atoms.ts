import { atom } from 'jotai';

export type Timeframe = '1W' | '1D' | '4H' | '1H' | '15m' | '5m';

export const selectedSymbolAtom = atom<string>('BTC/USDT');
export const timeframeAtom = atom<Timeframe>('1H');
export const confidenceFilterAtom = atom<number>(0);

// Derived example: show only high-conviction results
export const highConvictionOnlyAtom = atom<boolean>((get) => get(confidenceFilterAtom) >= 70);
