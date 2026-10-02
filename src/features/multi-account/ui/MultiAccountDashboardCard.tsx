'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchAccountsAction,
  registerAccountAction,
  toggleAccountAction,
  deleteAccountAction,
  AccountItem,
} from '../actions';
import { ShieldCheck, Plus, Power, Trash2, AlertCircle, RefreshCw, Key, DollarSign } from 'lucide-react';
import { formatCurrency } from '@/shared';

interface MultiAccountCardProps {
  onAccountSelect?: (accountId: string) => void;
  selectedAccountId?: string;
}

export function MultiAccountDashboardCard({
  onAccountSelect,
  selectedAccountId = 'primary',
}: MultiAccountCardProps) {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Form State
  const [newAccountId, setNewAccountId] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newApiKey, setNewApiKey] = useState('');
  const [newSecretKey, setNewSecretKey] = useState('');
  const [newRiskPct, setNewRiskPct] = useState(2.5);
  const [newDryRun, setNewDryRun] = useState(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchAccountsAction();
      if (res.success && res.data) {
        setAccounts(res.data);
      }
    } catch {
      // Error manejado en Server Action
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setActionMessage(null);

    try {
      const res = await registerAccountAction({
        account_id: newAccountId.trim().toLowerCase(),
        label: newLabel.trim(),
        api_key: newApiKey.trim(),
        secret_key: newSecretKey.trim(),
        risk_pct: newRiskPct / 100,
        max_notional_mult: 5.0,
        dry_run: newDryRun,
      });

      if (res.success) {
        setActionMessage({ text: res.message || 'Cuenta vinculada con éxito.', type: 'success' });
        setShowAddForm(false);
        setNewAccountId('');
        setNewLabel('');
        setNewApiKey('');
        setNewSecretKey('');
        await loadAccounts();
      } else {
        setActionMessage({ text: res.error || 'Error al vincular cuenta.', type: 'error' });
      }
    } catch (err: unknown) {
      setActionMessage({ text: err instanceof Error ? err.message : 'Error inesperado', type: 'error' });
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggle = async (account_id: string, currentEnabled: boolean) => {
    try {
      const res = await toggleAccountAction({ account_id, enabled: !currentEnabled });
      if (res.success) {
        setActionMessage({ text: res.message || 'Estado actualizado', type: 'success' });
        await loadAccounts();
      } else {
        setActionMessage({ text: res.error || 'Fallo al cambiar estado', type: 'error' });
      }
    } catch {
      setActionMessage({ text: 'Error de conexión', type: 'error' });
    }
  };

  const handleDelete = async (account_id: string) => {
    if (!confirm(`¿Estás seguro de eliminar la cuenta "${account_id}"?`)) return;
    try {
      const res = await deleteAccountAction({ account_id });
      if (res.success) {
        setActionMessage({ text: res.message || 'Cuenta eliminada', type: 'success' });
        await loadAccounts();
      } else {
        setActionMessage({ text: res.error || 'Fallo al eliminar cuenta', type: 'error' });
      }
    } catch {
      setActionMessage({ text: 'Error de conexión', type: 'error' });
    }
  };

  const totalBalance = accounts.reduce((acc, a) => acc + (a.current_balance_usdt || 0), 0);
  const activeCount = accounts.filter((a) => a.enabled).length;

  return (
    <div className="w-full bg-[#050B14]/90 border border-slate-700/60 rounded-2xl p-4 sm:p-6 shadow-2xl backdrop-blur-xl flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              DESPACHADOR MULTI-CUENTA BITUNIX
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              AES-256 Fernet En Reposo
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-2 tracking-tight">
            Gestión y Ejecución Paralela Multi-Cuenta
          </h2>
          <p className="text-sm text-slate-300 mt-1">
            Ejecución concurrente con dimensionamiento independiente en dólares (SOP-41) por balance de cuenta.
          </p>
        </div>

        {/* Action Controls con Touch Targets >= 44px */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadAccounts()}
            className="min-h-[44px] min-w-[44px] px-3 bg-slate-900/80 hover:bg-slate-800 border border-slate-700 rounded-xl flex items-center justify-center text-slate-300 hover:text-white transition-colors"
            title="Refrescar cuentas"
            aria-label="Refrescar cuentas"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin text-cyan-400' : ''} />
          </button>

          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="min-h-[44px] px-4 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-2 transition-colors shadow-lg shadow-cyan-500/10"
          >
            <Plus size={16} />
            <span>{showAddForm ? 'Cerrar Formulario' : 'Conectar 2da Cuenta'}</span>
          </button>
        </div>
      </div>

      {/* Alertas */}
      {actionMessage && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between text-xs font-medium ${
            actionMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          <span>{actionMessage.text}</span>
          <button
            onClick={() => setActionMessage(null)}
            className="text-slate-400 hover:text-white min-h-[32px] px-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Formulario de Conexión de Segunda Cuenta (Base 8 grid) */}
      {showAddForm && (
        <form
          onSubmit={handleCreateAccount}
          className="bg-slate-900/90 border border-cyan-500/30 p-4 sm:p-6 rounded-2xl flex flex-col gap-4 shadow-xl"
        >
          <div className="flex items-center gap-2 text-cyan-400 font-bold text-sm">
            <Key size={16} />
            <span>Vincular Nueva Cuenta Secundaria de Bitunix Futures</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="newAccountId" className="text-xs font-semibold text-slate-300">
                ID de Cuenta (Único)
              </label>
              <input
                id="newAccountId"
                type="text"
                placeholder="ej: client_secundaria_2"
                value={newAccountId}
                onChange={(e) => setNewAccountId(e.target.value)}
                required
                className="min-h-[44px] bg-slate-950 border border-slate-700 rounded-xl px-3 text-xs text-white outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="newLabel" className="text-xs font-semibold text-slate-300">
                Etiqueta / Nombre
              </label>
              <input
                id="newLabel"
                type="text"
                placeholder="ej: Cuenta Inversor 2"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                required
                className="min-h-[44px] bg-slate-950 border border-slate-700 rounded-xl px-3 text-xs text-white outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="newApiKey" className="text-xs font-semibold text-slate-300">
                API Key de Bitunix
              </label>
              <input
                id="newApiKey"
                type="password"
                placeholder="Pegar API Key"
                value={newApiKey}
                onChange={(e) => setNewApiKey(e.target.value)}
                required
                className="min-h-[44px] bg-slate-950 border border-slate-700 rounded-xl px-3 text-xs text-white font-mono outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="newSecretKey" className="text-xs font-semibold text-slate-300">
                Secret Key de Bitunix
              </label>
              <input
                id="newSecretKey"
                type="password"
                placeholder="Pegar Secret Key"
                value={newSecretKey}
                onChange={(e) => setNewSecretKey(e.target.value)}
                required
                className="min-h-[44px] bg-slate-950 border border-slate-700 rounded-xl px-3 text-xs text-white font-mono outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="newRiskPct" className="text-xs font-semibold text-slate-300">
                Riesgo por Trade (% del Saldo)
              </label>
              <input
                id="newRiskPct"
                type="number"
                step="0.1"
                min="0.5"
                max="5.0"
                value={newRiskPct}
                onChange={(e) => setNewRiskPct(parseFloat(e.target.value))}
                className="min-h-[44px] bg-slate-950 border border-slate-700 rounded-xl px-3 text-xs text-white outline-none focus:border-cyan-400"
              />
              <span className="text-[11px] text-slate-400">Canónico SOP-41: 2.50%</span>
            </div>

            <div className="flex flex-col justify-center gap-1.5 pt-4">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={newDryRun}
                  onChange={(e) => setNewDryRun(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span>Modo Simulación (Dry Run) para esta cuenta</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-2 mt-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="min-h-[44px] px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-xl"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={formSubmitting}
              className="min-h-[44px] px-6 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg disabled:opacity-50"
            >
              {formSubmitting ? 'Verificando con Bitunix...' : 'Verificar y Guardar Cuenta'}
            </button>
          </div>
        </form>
      )}

      {/* Resumen Superior */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Cuentas Conectadas
          </span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-white">{accounts.length}</span>
            <span className="text-xs text-emerald-400 font-semibold">({activeCount} activas)</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Capital Agregado
          </span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-cyan-300">
              {formatCurrency(totalBalance)}
            </span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Despacho Concurrente
          </span>
          <div className="mt-2 flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-bold text-emerald-300">Paralelo 1:1 Activo</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Aislamiento de Riesgo
          </span>
          <div className="mt-2 flex items-center gap-1.5">
            <ShieldCheck size={16} className="text-cyan-400" />
            <span className="text-xs font-bold text-white">SOP-41 Independiente</span>
          </div>
        </div>
      </div>

      {/* Lista de Cuentas */}
      <div className="flex flex-col gap-3">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Cuentas Registradas en el Pool de Ejecución
        </span>

        {accounts.map((acc) => {
          const isSelected = selectedAccountId === acc.account_id;
          return (
            <div
              key={acc.account_id}
              className={`p-4 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                isSelected
                  ? 'bg-cyan-500/10 border-cyan-500/40 shadow-lg shadow-cyan-500/5'
                  : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm border ${
                    acc.is_primary
                      ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                      : 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                  }`}
                >
                  {acc.is_primary ? 'P' : 'S'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{acc.label}</span>
                    {acc.is_primary && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                        PRINCIPAL (.ENV)
                      </span>
                    )}
                    {acc.dry_run && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        DRY RUN
                      </span>
                    )}
                  </div>
                  <span className="text-xs font-mono text-slate-400 block mt-0.5">
                    ID: {acc.account_id} • API Key: {acc.api_key}
                  </span>
                </div>
              </div>

              {/* Balances y Riesgo */}
              <div className="flex flex-wrap items-center gap-4 sm:gap-6">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">
                    Saldo Disponible
                  </span>
                  <span className="text-sm font-black text-emerald-400">
                    {formatCurrency(acc.current_balance_usdt)}
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">
                    Riesgo por Trade
                  </span>
                  <span className="text-sm font-bold text-white">
                    {(acc.risk_pct * 100).toFixed(2)}% ({formatCurrency(acc.projected_trade_risk_usd)})
                  </span>
                </div>

                {/* Acciones por cuenta con Touch Target >= 44px */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggle(acc.account_id, acc.enabled)}
                    className={`min-h-[44px] px-3 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors ${
                      acc.enabled
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
                    }`}
                    title={acc.enabled ? 'Pausar trading' : 'Activar trading'}
                  >
                    <Power size={14} />
                    <span>{acc.enabled ? 'Activa' : 'Pausada'}</span>
                  </button>

                  {!acc.is_primary && (
                    <button
                      onClick={() => handleDelete(acc.account_id)}
                      className="min-h-[44px] min-w-[44px] bg-slate-800 hover:bg-rose-950 border border-slate-700 hover:border-rose-500/50 rounded-xl flex items-center justify-center text-slate-400 hover:text-rose-400 transition-colors"
                      title="Eliminar cuenta secundaria"
                      aria-label="Eliminar cuenta"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}

                  {onAccountSelect && (
                    <button
                      onClick={() => onAccountSelect(acc.account_id)}
                      className={`min-h-[44px] px-3 rounded-xl text-xs font-bold transition-colors ${
                        isSelected
                          ? 'bg-cyan-500 text-slate-950 font-bold'
                          : 'bg-slate-800 text-slate-300 hover:text-white'
                      }`}
                    >
                      {isSelected ? 'Seleccionada' : 'Ver Detalle'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
