import { describe, it, expect } from 'vitest';
import { getDriftBadgeStyle } from '../../src/app/components/ui/ForwardTestAuditCard';

describe('SOP-150 ForwardTestAuditCard Drift Status Mapping', () => {
    it('maps all 4 pre-registered drift statuses to institutional WCAG-compliant badges', () => {
        const inLine = getDriftBadgeStyle('IN_LINE');
        expect(inLine.label).toContain('EN LÍNEA');
        expect(inLine.classes).toContain('text-neon-green');

        const warn = getDriftBadgeStyle('WARNING_DRIFT');
        expect(warn.label).toContain('-1.5σ');
        expect(warn.classes).toContain('text-amber-300');

        const crit = getDriftBadgeStyle('CRITICAL_DEGRADATION');
        expect(crit.label).toContain('-2.0σ');
        expect(crit.classes).toContain('text-neon-red');

        const building = getDriftBadgeStyle('SAMPLE_BUILDING');
        expect(building.label).toContain('CONSTRUYENDO');
        expect(building.classes).toContain('text-neon-cyan');
    });
});
