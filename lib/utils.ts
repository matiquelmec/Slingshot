export function getPrecision(val: number | null): number {
    if (val === null || val === 0) return 2;
    const absVal = Math.abs(val);
    if (absVal < 0.00001) return 8;
    if (absVal < 0.0001) return 7;
    if (absVal < 0.001) return 6;
    if (absVal < 0.01) return 5;
    if (absVal < 1) return 4;
    return 2;
}

export function formatPrice(val: number | null, prefix = '$', dp?: number): string {
    if (val == null) return '—';
    const finalDp = dp !== undefined ? dp : getPrecision(val);
    return prefix + val.toLocaleString('en-US', {
        minimumFractionDigits: finalDp,
        maximumFractionDigits: finalDp
    });
}

export function formatPercent(val: number | null, dp?: number): string {
    if (val === null) return '—';

    let finalDp = dp;
    if (finalDp === undefined) {
        const absVal = Math.abs(val);
        if (absVal === 0) finalDp = 4;
        else if (absVal < 0.0001) finalDp = 8;
        else if (absVal < 0.001) finalDp = 7;
        else if (absVal < 0.01) finalDp = 6;
        else finalDp = 4;
    }

    const sign = val > 0 ? '+' : '';
    return sign + val.toFixed(finalDp) + '%';
}
