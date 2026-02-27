import sys
sys.path.insert(0, '.')

with open('backend/strategy/confluence/scorer.py', 'r', encoding='utf-8') as f:
    content = f.read()

results = {
    'Mode-aware threshold': 'mode_threshold = float(getattr(config' in content,
    'Continuous mediocre span': 'span = max((T - 5) - 45.0' in content,
    'Poor zone dampen': '6.0 - extra_dampen' in content,
    'Old DISABLED comment gone': 'TEMPORARILY DISABLED' not in content,
    'UTC kill zone': 'datetime.now(timezone.utc)' in content,
    'Data-driven ltf check': 'not any(tf.lower() in' in content,
    'HTF inflection decay': '100.0 - (dist * 25.0)' in content,
}

for label, passed in results.items():
    status = 'PASS' if passed else 'FAIL'
    print(f'{status}: {label}')

print()
print('Curve simulation per mode:')
def curve(r, T):
    span = max((T-5)-45.0, 1.0)
    if r >= T+3:
        return min(100.0, r+3.0)
    if r >= T-5:
        boost = (r-(T-5))*0.8 if r < T else 5.0-(r-T)*(2.0/3.0)
        return min(100.0, r+boost)
    if r >= 45.0:
        t = (r-45.0)/span
        return r - 6.0*(1.0-t)
    return max(0.0, r - 6.0 - (45.0-r)*0.6)

modes = [('Surgical', 65.0), ('Strike', 70.0), ('Stealth', 72.0), ('Overwatch', 78.0)]
for name, T in modes:
    print(f'  {name:10} T={T:.0f}: raw=T-5={curve(T-5,T):.1f}  raw=T={curve(T,T):.1f}  raw=T+5={curve(T+5,T):.1f}  raw=50={curve(50,T):.1f}  raw=30={curve(30,T):.1f}')

all_pass = all(results.values())
print()
print('ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED')
