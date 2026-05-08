import { Signal } from '../../types/signal';

import { STORAGE_KEY, CACHE_DURATION_MS } from './constants';

const getUtcTime = (ts: string) => {
    if (ts.includes('Z') || ts.includes('+')) return new Date(ts).getTime();
    return new Date(ts.replace(' ', 'T') + 'Z').getTime();
};

export const loadSignalHistory = (): { data: Record<string, Signal>, ids: string[] } => {
    if (typeof window === 'undefined') return { data: {}, ids: [] };
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return { data: {}, ids: [] };
        const parsed = JSON.parse(raw);
        const data = parsed.data || {};
        const ids = parsed.ids || [];

        const now = Date.now();
        const validIds = ids.filter((id: string) => {
            const s = data[id];
            if (!s) return false;
            const age = now - getUtcTime(s.timestamp);
            return age < CACHE_DURATION_MS;
        });

        const validData: Record<string, Signal> = {};
        validIds.forEach((id: string) => {
            validData[id] = data[id];
        });

        return { data: validData, ids: validIds };
    } catch {
        return { data: {}, ids: [] };
    }
};

export const saveSignalHistory = (data: Record<string, Signal>, ids: string[]) => {
    if (typeof window === 'undefined') return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ data, ids }));
    } catch { /* quota exceeded */ }
};

export const mergeSignals = (
    prevData: Record<string, Signal>, 
    prevIds: string[], 
    incoming: Signal[]
): { data: Record<string, Signal>, ids: string[] } => {
    let newData = { ...prevData };
    let newIds = [...prevIds];
    let hasChanged = false;

    incoming.forEach(sig => {
        const id = sig.id || `${sig.timestamp}-${sig.asset}`;
        
        if (!sig.asset || !sig.price || sig.price <= 0) return;

        if (!newData[id] || JSON.stringify(newData[id]) !== JSON.stringify({ ...sig, id })) {
            if (!newData[id]) {
                newIds.unshift(id);
            }
            newData[id] = { ...sig, id };
            hasChanged = true;
        }
    });

    if (!hasChanged) return { data: prevData, ids: prevIds };

    const now = Date.now();
    const finalIds = newIds.filter(id => {
        const s = newData[id];
        return s && (now - getUtcTime(s.timestamp) < CACHE_DURATION_MS);
    }).slice(0, 100);

    const finalData: Record<string, Signal> = {};
    finalIds.forEach(id => { finalData[id] = newData[id]; });
    
    saveSignalHistory(finalData, finalIds);
    return { data: finalData, ids: finalIds };
};
