/**
 * Centralized UI Feature Flags (FSD Shared Layer)
 *
 * Fail-closed by default: sensitive account/balance views remain hidden unless
 * explicitly enabled via environment variables (`=== 'true'`).
 */

export function parseBooleanFlag(
    rawValue: string | undefined | null,
    defaultValue = false
): boolean {
    if (rawValue === undefined || rawValue === null) {
        return defaultValue;
    }
    const normalized = rawValue.trim().toLowerCase();
    if (normalized === 'true') {
        return true;
    }
    if (normalized === 'false' || normalized === '' || normalized === '0') {
        return false;
    }
    return defaultValue;
}

export function isBitunixCoreVisible(override?: string): boolean {
    const raw = override !== undefined ? override : process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE;
    return parseBooleanFlag(raw, false);
}

export function isFtmoMt5Visible(override?: string): boolean {
    const raw = override !== undefined ? override : process.env.NEXT_PUBLIC_SHOW_FTMO_MT5;
    return parseBooleanFlag(raw, false);
}

export const FEATURE_FLAGS = {
    get showBitunixCore(): boolean {
        return isBitunixCoreVisible();
    },
    get showFtmoMt5(): boolean {
        return isFtmoMt5Visible();
    },
} as const;
