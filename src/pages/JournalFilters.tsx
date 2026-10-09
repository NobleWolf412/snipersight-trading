interface Props {
    symbolInput: string;
    typeFilter: string;
    exitFilter: string;
    startDate: string;
    endDate: string;
    setSymbolInput: (value: string) => void;
    setTypeFilter: (value: string) => void;
    setExitFilter: (value: string) => void;
    setStartDate: (value: string) => void;
    setEndDate: (value: string) => void;
    applyFilters: () => void;
    resetFilters: () => void;
}
export function JournalFilterControls({ symbolInput, typeFilter, exitFilter, startDate, endDate, setSymbolInput, setTypeFilter, setExitFilter, setStartDate, setEndDate, applyFilters, resetFilters }: Props) {
  return <div className="journal-filter-row">
    <label>Symbol<input value={symbolInput} onChange={e=>setSymbolInput(e.target.value.toUpperCase())} /></label>
    <label>Trade type<select value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="">All types</option><option value="scalp">SCALP</option><option value="intraday">INTRADAY</option><option value="swing">SWING</option></select></label>
    <label>Exit reason<select value={exitFilter} onChange={e=>setExitFilter(e.target.value)}><option value="">All exits</option><option value="target">TARGET</option><option value="stop_loss">STOP</option><option value="stagnation">STALE</option><option value="manual">MANUAL</option></select></label>
    <label>From date<input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} /></label>
    <label>To date<input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)} /></label>
    <button className="btn btn-cyan" onClick={applyFilters}>Apply</button><button className="btn" onClick={resetFilters}>Reset</button>
  </div>;
}
