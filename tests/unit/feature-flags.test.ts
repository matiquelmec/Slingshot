import { describe, it, expect, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
    parseBooleanFlag,
    isBitunixCoreVisible,
    isFtmoMt5Visible,
    FEATURE_FLAGS,
} from '@/shared';

describe('UI Privacy Feature Flags (Bitunix Core & FTMO MT5)', () => {
    const originalBitunixEnv = process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE;
    const originalFtmoEnv = process.env.NEXT_PUBLIC_SHOW_FTMO_MT5;

    afterEach(() => {
        if (originalBitunixEnv === undefined) {
            delete process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE;
        } else {
            process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE = originalBitunixEnv;
        }
        if (originalFtmoEnv === undefined) {
            delete process.env.NEXT_PUBLIC_SHOW_FTMO_MT5;
        } else {
            process.env.NEXT_PUBLIC_SHOW_FTMO_MT5 = originalFtmoEnv;
        }
    });

    it('defaults fail-closed (false) for undefined, empty, false, or invalid values', () => {
        expect(parseBooleanFlag(undefined)).toBe(false);
        expect(parseBooleanFlag(null)).toBe(false);
        expect(parseBooleanFlag('')).toBe(false);
        expect(parseBooleanFlag('false')).toBe(false);
        expect(parseBooleanFlag('FALSE')).toBe(false);
        expect(parseBooleanFlag('0')).toBe(false);
        expect(parseBooleanFlag('yes')).toBe(false);
    });

    it('enables only when explicitly set to true (case-insensitive, trimmed)', () => {
        expect(parseBooleanFlag('true')).toBe(true);
        expect(parseBooleanFlag('TRUE')).toBe(true);
        expect(parseBooleanFlag('  True  ')).toBe(true);
    });

    it('keeps Bitunix Core and FTMO MT5 hidden by default when env vars are unset', () => {
        delete process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE;
        delete process.env.NEXT_PUBLIC_SHOW_FTMO_MT5;

        expect(isBitunixCoreVisible()).toBe(false);
        expect(isFtmoMt5Visible()).toBe(false);
        expect(FEATURE_FLAGS.showBitunixCore).toBe(false);
        expect(FEATURE_FLAGS.showFtmoMt5).toBe(false);
    });

    it('supports independent toggling of Bitunix Core and FTMO MT5', () => {
        process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE = 'true';
        process.env.NEXT_PUBLIC_SHOW_FTMO_MT5 = 'false';

        expect(isBitunixCoreVisible()).toBe(true);
        expect(isFtmoMt5Visible()).toBe(false);

        process.env.NEXT_PUBLIC_SHOW_BITUNIX_CORE = 'false';
        process.env.NEXT_PUBLIC_SHOW_FTMO_MT5 = 'true';

        expect(isBitunixCoreVisible()).toBe(false);
        expect(isFtmoMt5Visible()).toBe(true);
    });

    it('enforces server-side route guards on /bitunix and /ftmo via @/shared barrel export', () => {
        const root = process.cwd();
        const bitunixPage = fs.readFileSync(
            path.join(root, 'src/app/(dashboard)/bitunix/page.tsx'),
            'utf8'
        );
        const ftmoPage = fs.readFileSync(
            path.join(root, 'src/app/(dashboard)/ftmo/page.tsx'),
            'utf8'
        );

        expect(bitunixPage).toContain("from '@/shared'");
        expect(bitunixPage).toContain('isBitunixCoreVisible');
        expect(bitunixPage).toContain("redirect('/')");

        expect(ftmoPage).toContain("from '@/shared'");
        expect(ftmoPage).toContain('isFtmoMt5Visible');
        expect(ftmoPage).toContain("redirect('/')");
    });
});
