# 🕵️ AUDIT PLAN V10.5: Navigation Data Integrity

## 1. Problem Statement
The system fails to hydrate session data (Asia, London, NY rows) for some assets upon navigation, despite the backend possessing the correct state on disk. The UI displays "ESPERANDO DATOS DE SESIÓN..." indicating that the `sessions` object is missing or malformed in the store.

## 2. Investigative Vectors

### 2.1. Backend Serialization (The Stringify Trap)
- **Symptom**: `sanitize_for_json` might be failing on complex nested objects, triggering the `str(obj)` fallback.
- **Check**: Verify if `sessions_info` in `SessionManager.py` contains any hidden non-serializable types (e.g. `numpy` scalars that escaped previous checks).
- **Action**: Add explicit type casting to `float` or `int` for all session levels.

### 2.2. Frontend Race Condition (The "Null Override")
- **Symptom**: `doConnect` resets `sessionData` to `null`. If a message arrives during this transition, it might be ignored or partially applied.
- **Check**: Log the `activeConnectionId` vs. message connection ID in the frontend.
- **Action**: Implement a "Hydration Lock" that prevents clearing state if a valid update is already in progress for the same symbol.

### 2.3. Symbol Mismatch (The Slash/Space Gap)
- **Symptom**: `LatticeScanner` sends `ETH / USDT`, but backend sends `ETHUSDT`.
- **Check**: My `isSameSymbol` should handle this, but we need to verify if `state.activeSymbol` is being updated *after* the first message arrives.
- **Action**: Normalize `activeSymbol` immediately in the store to a "System Format" (clean) while keeping a "Display Format" for the UI.

## 3. Implementation Steps (Platinum Fix v10.5)

### Phase 1: Backend Hardening
- Cast all `high`, `low`, `pdh`, `pdl` values to `float` explicitly in `_build_payload`.
- Ensure `asset` is always present in all broadcast paths (Fast Path, Slow Path, Bootstrap).

### Phase 2: Store Hardening
- Update `TelemetryStore` to store symbols in a normalized format.
- Add a `lastReceivedSymbol` flag to detect and reject cross-asset pollution more aggressively.

### Phase 3: UI Resilience
- Modify `SessionClock.tsx` to show a "Syncing..." state instead of "Waiting..." if at least the symbol is matched.
- Add a "Manual Refresh" trigger that requests the current state via REST if WS is silent.

---
**Status**: IN_AUDIT
**Next Action**: Verify serialization of `ETHUSDT` payload.
