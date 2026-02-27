import pandas as pd

for s in ['BTC', 'ETH', 'SOL']:
    df = pd.read_csv('cycle_audit_results/' + s + '_cycle_audit.csv')
    n = len(df)

    f1 = int(df['FLAG_early_dcl'].sum()) if 'FLAG_early_dcl' in df.columns else -1
    f2_cd = int(df['cd_wcl_failed'].sum()) if 'cd_wcl_failed' in df.columns else -1
    f2_sc = int(df['sc_wcl_failed'].sum()) if 'sc_wcl_failed' in df.columns else -1
    f3 = int(df['FLAG_disagree'].sum()) if 'FLAG_disagree' in df.columns else -1
    f_silent = int(df['FLAG_wcl_silent'].sum()) if 'FLAG_wcl_silent' in df.columns else -1
    in_dcl = int(df['cd_in_dcl_zone'].sum()) if 'cd_in_dcl_zone' in df.columns else -1

    phase_dist = df['cd_phase'].value_counts().to_dict() if 'cd_phase' in df.columns else {}
    trans_dist = df['cd_translation'].value_counts().to_dict() if 'cd_translation' in df.columns else {}
    dcl_status = df['cd_dcl_status'].value_counts().to_dict() if 'cd_dcl_status' in df.columns else {}
    bias_cd = df['cd_trade_bias'].value_counts().to_dict() if 'cd_trade_bias' in df.columns else {}
    bias_sc = df['sc_overall_bias'].value_counts().to_dict() if 'sc_overall_bias' in df.columns else {}

    early_days = []
    if 'FLAG_early_dcl' in df.columns and f1 > 0 and 'cd_dcl_days' in df.columns:
        early = df[df['FLAG_early_dcl'] == True]
        early_days = list(early['cd_dcl_days'].dropna().astype(int))[:10]

    print('--- ' + s + ' ---')
    print('Bars: ' + str(n))
    pct1 = round(f1/n*100, 1) if f1 >= 0 else 'N/A'
    print('Early DCL confirmations: ' + str(f1) + ' (' + str(pct1) + '%)')
    print('Early DCL day values: ' + str(early_days))
    pct2c = round(f2_cd/n*100, 1) if f2_cd >= 0 else 'N/A'
    pct2s = round(f2_sc/n*100, 1) if f2_sc >= 0 else 'N/A'
    print('WCL failed cd: ' + str(f2_cd) + ' (' + str(pct2c) + '%)')
    print('WCL failed sc: ' + str(f2_sc) + ' (' + str(pct2s) + '%)')
    print('Silent WCL fails (no SHORT): ' + str(f_silent))
    pct3 = round(f3/n*100, 1) if f3 >= 0 else 'N/A'
    print('Detector disagree: ' + str(f3) + ' (' + str(pct3) + '%)')
    pct_dcl = round(in_dcl/n*100, 1) if in_dcl >= 0 else 'N/A'
    print('In DCL zone bars: ' + str(in_dcl) + ' (' + str(pct_dcl) + '%)')
    print('Phase dist: ' + str(phase_dist))
    print('Translation dist: ' + str(trans_dist))
    print('DCL status dist: ' + str(dcl_status))
    print('Bias cd: ' + str(bias_cd))
    print('Bias sc: ' + str(bias_sc))

    # WCL failure bias breakdown
    if 'sc_wcl_failed' in df.columns and f2_sc > 0 and 'sc_overall_bias' in df.columns:
        failed_rows = df[df['sc_wcl_failed'] == True]
        bias_on_fail = failed_rows['sc_overall_bias'].value_counts().to_dict()
        print('Bias when WCL failed: ' + str(bias_on_fail))

    # Recent 5 bars
    recent_cols = ['date', 'close', 'cd_phase', 'cd_translation', 'cd_trade_bias',
                   'cd_dcl_days', 'cd_dcl_status', 'cd_dcl_failed', 'cd_wcl_failed', 'sc_overall_bias']
    avail = [c for c in recent_cols if c in df.columns]
    print('Recent 5 bars:')
    print(df[avail].tail(5).to_string(index=False))
    print()
