export interface ToggleProps {
  label: string;
  value: boolean;
  onChange?: (value: boolean) => void;
  hint?: string;
  disabled?: boolean;
}

export function Toggle({label, value, onChange, hint, disabled}: ToggleProps) {
  return <button type="button" role="switch" aria-checked={value} aria-label={label}
    className="execution-toggle" disabled={disabled} onClick={()=>onChange?.(!value)}>
    <span><strong>{label}</strong>{hint && <span className="execution-toggle__hint">{hint}</span>}</span>
    <span className="mono" style={{color:value?'var(--green-soft)':'var(--fg-3)'}}>{value?'ON':'OFF'}</span>
  </button>;
}
