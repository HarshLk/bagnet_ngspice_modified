import os
import subprocess
import glob
import csv
import numpy as np
import scipy.interpolate as interp
import scipy.optimize as sciopt
from pathlib import Path

# Constraints from YAML
CONSTRAINTS = {
    'gain': (300.0, None),
    'ugbw': (10.0e6, None),
    'pm': (60.0, None),
    'tset': (None, 90.0e-9),
    'psrr': (50.0, None),
    'cmrr': (50.0, None),
    'offset_sys': (None, 1.0e-3),
    'ibias': (None, 0.2e-3),
}

METRIC_LABELS = {
    'gain': 'Gain',
    'ugbw': 'UGBW (Unity Gain BW)',
    'pm': 'Phase Margin (PM)',
    'tset': 'Settling Time (Tset)',
    'psrr': 'PSRR',
    'cmrr': 'CMRR',
    'offset_sys': 'Systematic Offset',
    'ibias': 'Bias Current (Ibias)',
}

TARGET_LABELS = {
    'gain': '> 300.0',
    'ugbw': '> 10.00 MHz',
    'pm': '> 60.0°',
    'tset': '< 90.00 ns',
    'psrr': '> 50.0 dB',
    'cmrr': '> 50.0 dB',
    'offset_sys': '< 1.0 mV',
    'ibias': '< 200.0 µA',
}

def get_status(metric, value):
    low, high = CONSTRAINTS.get(metric, (None, None))
    if low is not None and value < low:
        return "⚠️ Near" if value > 0.9 * low else "❌ Fail"
    if high is not None and value > high:
        return "⚠️ Near" if value < 1.1 * high else "❌ Fail"
    return "✅ Pass"

def format_value(metric, value):
    if metric == 'ugbw': return f"{value/1e6:.2f} MHz"
    if metric == 'tset': return f"{value*1e9:.2f} ns"
    if metric == 'offset_sys': return f"{value*1e3:.2f} mV"
    if metric == 'ibias': return f"{value*1e6:.2f} µA"
    if metric == 'pm': return f"{value:.2f}°"
    if metric in ['psrr', 'cmrr', 'gain']: return f"{value:.2f}"
    return str(value)

def _get_best_crossing(xvec, yvec, val):
    interp_fun = interp.InterpolatedUnivariateSpline(xvec, yvec)
    def fzero(x):
        return interp_fun(x) - val
    xstart, xstop = xvec[0], xvec[-1]
    try:
        return sciopt.brentq(fzero, xstart, xstop), True
    except ValueError:
        return xstop, False

def parse_ac_dc(ac_file, dc_file):
    ac_raw = np.genfromtxt(ac_file, skip_header=1)
    dc_raw = np.genfromtxt(dc_file, skip_header=1)
    freq = ac_raw[:, 0]
    vout = ac_raw[:, 1] + 1j*ac_raw[:, 2]
    ibias = -dc_raw[1]
    
    gain_dc = np.abs(vout)[0]
    gain_mag = np.abs(vout)
    ugbw, valid = _get_best_crossing(freq, gain_mag, val=1)
    if not valid: ugbw = freq[0]
    
    phase = np.unwrap(np.angle(vout))
    phase_deg = np.rad2deg(phase)
    phase_fun = interp.interp1d(freq, phase_deg, kind='quadratic')
    if valid:
        p_ugbw = phase_fun(ugbw)
        phm = (-180 + p_ugbw) if p_ugbw > 0 else (180 + p_ugbw)
    else:
        phm = -180
    
    return {'gain': gain_dc, 'ugbw': ugbw, 'pm': phm, 'ibias': ibias}

def parse_cm_ps(file_path):
    raw = np.genfromtxt(file_path, skip_header=1)
    vout = raw[:, 1] + 1j*raw[:, 2]
    return np.abs(vout)[0]

def parse_tran(tran_file, fbck=1.0, tot_err=0.01):
    raw = np.genfromtxt(tran_file, skip_header=1)
    t, vout, vin = raw[:, 0], raw[:, 1], raw[:, 3]
    
    vin_norm = (vin - vin[0]) / (vin[-1] - vin[0])
    ref_value = 1/fbck * vin
    y = (vout - vout[0]) / (ref_value[-1] - ref_value[0])
    
    try:
        last_idx = np.where(y < 1.0 - tot_err)[0][-1]
        last_max_vec = np.where(y > 1.0 + tot_err)[0]
        if last_max_vec.size > 0 and last_max_vec[-1] > last_idx:
            last_idx = last_max_vec[-1]
            last_val = 1.0 + tot_err
        else:
            last_val = 1.0 - tot_err
        
        if last_idx == t.size - 1:
            tset = t[-1]
        else:
            f = interp.InterpolatedUnivariateSpline(t, y - last_val)
            tset = sciopt.brentq(f, t[last_idx], t[last_idx + 1])
    except:
        tset = t[-1]
        
    offset = abs(vout[0] - vin[0] / fbck)
    return {'tset': tset, 'offset_sys': offset}

if __name__ == "__main__":
    good_dir = "outputs/netlists/good"
    netlists = glob.glob(os.path.join(good_dir, "*.cir"))
    ids = sorted(list(set([os.path.basename(n).split('_')[0] for n in netlists])))
    
    summary_rows = []
    
    for dsn_id in ids:
        print(f"Processing design {dsn_id}...")
        results = {}
        
        # Paths
        ol_cir = os.path.join(good_dir, f"{dsn_id}_two_stage_ol.cir")
        cm_cir = os.path.join(good_dir, f"{dsn_id}_two_stage_cm.cir")
        ps_cir = os.path.join(good_dir, f"{dsn_id}_two_stage_ps.cir")
        tran_cir = os.path.join(good_dir, f"{dsn_id}_two_stage_tran.cir")
        
        # We need to run them. Let's redirect outputs to a local temp
        tmp_run = f"tmp_sim_{dsn_id}"
        os.makedirs(tmp_run, exist_ok=True)
        
        # Run
        # To avoid SPICE path issues with spaces/&, we'll use relative paths
        # and set cwd for the subprocess
        for cir, suffix in [(ol_cir, "ol"), (cm_cir, "cm"), (ps_cir, "ps"), (tran_cir, "tran")]:
            with open(cir, 'r') as f:
                content = f.read()
            
            import re
            output_paths = re.findall(r'wrdata (/tmp/ckt_da/[^\s]+)', content)
            for old_path in output_paths:
                # Get relative path from /tmp/ckt_da
                rel_path = os.path.relpath(old_path, "/tmp/ckt_da")
                os.makedirs(os.path.join(tmp_run, os.path.dirname(rel_path)), exist_ok=True)
                # Use relative path in netlist
                content = content.replace(old_path, rel_path)

            tmp_cir_name = os.path.basename(cir)
            tmp_cir_path = os.path.join(tmp_run, tmp_cir_name)
            with open(tmp_cir_path, 'w') as f:
                f.write(content)
            
            # Run NGSpice with cwd=tmp_run
            result = subprocess.run(["ngspice", "-b", tmp_cir_name], cwd=tmp_run, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error running ngspice on {tmp_cir_name}:")
                print(result.stderr)
            
        # Parse
        # Path logic depends on how it was rendered in the original netlist
        # For OL: it used designs_two_stage_ol/two_stage_ol_ID/ac.csv
        ol_path = os.path.join(os.path.abspath(tmp_run), f"designs_two_stage_ol/two_stage_ol_{dsn_id}")
        ol_res = parse_ac_dc(os.path.join(ol_path, "ac.csv"), os.path.join(ol_path, "dc.csv"))
        results.update(ol_res)
        
        cm_path = os.path.join(os.path.abspath(tmp_run), f"designs_two_stage_cm/two_stage_cm_{dsn_id}")
        gain_cm = parse_cm_ps(os.path.join(cm_path, "cm.csv"))
        results['cmrr'] = 20 * np.log10(results['gain'] / gain_cm)
        
        ps_path = os.path.join(os.path.abspath(tmp_run), f"designs_two_stage_ps/two_stage_ps_{dsn_id}")
        gain_ps = parse_cm_ps(os.path.join(ps_path, "ps.csv"))
        results['psrr'] = 20 * np.log10(results['gain'] / gain_ps)
        
        tran_path = os.path.join(os.path.abspath(tmp_run), f"designs_two_stage_tran/two_stage_tran_{dsn_id}")
        tran_res = parse_tran(os.path.join(tran_path, "tran.csv"))
        results.update(tran_res)
        
        # Build Table
        summary_rows.append([f"Design ID: {dsn_id}", "", "", ""])
        for m in ['gain', 'ugbw', 'pm', 'tset', 'psrr', 'cmrr', 'offset_sys', 'ibias']:
            val = results[m]
            summary_rows.append([
                METRIC_LABELS[m],
                format_value(m, val),
                TARGET_LABELS[m],
                get_status(m, val)
            ])
        summary_rows.append(["", "", "", ""])

    # Write to CSV
    with open("good_netlists_metrics.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Result", "Target Constraint", "Status"])
        writer.writerows(summary_rows)

    print("Success! Metrics logged in good_netlists_metrics.csv")
