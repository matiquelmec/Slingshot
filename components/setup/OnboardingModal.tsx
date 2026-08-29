'use client';

import React, { useState, useEffect } from 'react';
import { Shield, Key, Send, CheckCircle2, AlertTriangle, Play, RefreshCw, Lock } from 'lucide-react';

interface SetupStatus {
  is_configured: boolean;
  has_bitunix: boolean;
  has_binance: boolean;
  has_telegram: boolean;
  live_trading: boolean;
  account_balance: number;
  max_risk_pct: number;
}

export default function OnboardingModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [step, setStep] = useState(1);

  // Form State
  const [bitunixApiKey, setBitunixApiKey] = useState('');
  const [bitunixSecretKey, setBitunixSecretKey] = useState('');
  const [telegramBotToken, setTelegramBotToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [enableLiveTrading, setEnableLiveTrading] = useState(true);
  const [accountBalance, setAccountBalance] = useState(1000);
  const [maxRiskPct, setMaxRiskPct] = useState(0.02);

  // Testing States
  const [testingBitunix, setTestingBitunix] = useState(false);
  const [bitunixStatus, setBitunixStatus] = useState<{ valid?: boolean; message?: string } | null>(null);

  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState<{ valid?: boolean; message?: string } | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    async function checkStatus() {
      try {
        const res = await fetch('http://localhost:8000/api/v1/setup/status');
        if (res.ok) {
          const data: SetupStatus = await res.json();
          if (!data.is_configured) {
            setIsOpen(true);
          }
        }
      } catch (err) {
        console.debug('Error comprobando estado de setup:', err);
      } finally {
        setIsLoading(false);
      }
    }
    checkStatus();
  }, []);

  const handleTestBitunix = async () => {
    if (!bitunixApiKey || !bitunixSecretKey) {
      setBitunixStatus({ valid: false, message: 'Por favor ingresa la API Key y Secret Key' });
      return;
    }
    setTestingBitunix(true);
    setBitunixStatus(null);
    try {
      const res = await fetch('http://localhost:8000/api/v1/setup/test-bitunix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: bitunixApiKey, secret_key: bitunixSecretKey })
      });
      const data = await res.json();
      setBitunixStatus(data);
    } catch (err: any) {
      setBitunixStatus({ valid: false, message: 'Error conectando con el servidor' });
    } finally {
      setTestingBitunix(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!telegramBotToken || !telegramChatId) {
      setTelegramStatus({ valid: false, message: 'Por favor ingresa el Bot Token y Chat ID' });
      return;
    }
    setTestingTelegram(true);
    setTelegramStatus(null);
    try {
      const res = await fetch('http://localhost:8000/api/v1/setup/test-telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_token: telegramBotToken, chat_id: telegramChatId })
      });
      const data = await res.json();
      setTelegramStatus(data);
    } catch (err: any) {
      setTelegramStatus({ valid: false, message: 'Error conectando con el servidor' });
    } finally {
      setTestingTelegram(false);
    }
  };

  const handleSaveAndLaunch = async () => {
    setSaving(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/setup/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bitunix_api_key: bitunixApiKey,
          bitunix_secret_key: bitunixSecretKey,
          telegram_bot_token: telegramBotToken,
          telegram_chat_id: telegramChatId,
          enable_live_trading: enableLiveTrading,
          account_balance: accountBalance,
          max_risk_pct: maxRiskPct
        })
      });
      const data = await res.json();
      if (data.success) {
        setSaveSuccess(true);
        setTimeout(() => {
          setIsOpen(false);
          window.location.reload();
        }, 1500);
      }
    } catch (err) {
      console.error('Error guardando configuración:', err);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || isLoading) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="relative w-full max-w-2xl bg-zinc-950 border border-cyan-500/30 rounded-2xl shadow-[0_0_50px_rgba(6,182,212,0.15)] overflow-hidden">
        {/* Header Cyberpunk */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
              <Shield className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-wider text-white">SLINGSHOT APEX SOVEREIGN</h2>
              <p className="text-xs text-zinc-400 font-mono">ASISTENTE DE CONFIGURACIÓN INICIAL (ONBOARDING)</p>
            </div>
          </div>
          <div className="flex items-center gap-1 font-mono text-xs text-cyan-400 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20">
            PASO {step} DE 3
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          {/* PASO 1: BITUNIX FUTURES */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-cyan-400">
                <Key className="w-5 h-5" />
                <h3 className="font-semibold text-sm uppercase tracking-wider">Credenciales de Bitunix (Futuros)</h3>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Ingresa tus API Keys de Bitunix para la ejecución automática y el blindaje de Stop Loss en vivo.
                (Solo se requieren permisos de <b>Lectura</b> y <b>Trading de Futuros</b>. Retiros prohibidos).
              </p>

              <div className="space-y-3 font-mono text-xs">
                <div>
                  <label className="block text-zinc-300 mb-1">BITUNIX API KEY</label>
                  <input
                    type="password"
                    value={bitunixApiKey}
                    onChange={(e) => setBitunixApiKey(e.target.value)}
                    placeholder="Ingresa tu API Key..."
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
                <div>
                  <label className="block text-zinc-300 mb-1">BITUNIX SECRET KEY</label>
                  <input
                    type="password"
                    value={bitunixSecretKey}
                    onChange={(e) => setBitunixSecretKey(e.target.value)}
                    placeholder="Ingresa tu Secret Key..."
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              {/* Botón de Test Bitunix */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={handleTestBitunix}
                  disabled={testingBitunix}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-mono text-cyan-300 border border-zinc-700 transition"
                >
                  {testingBitunix ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                  Probar Conexión en Vivo
                </button>

                {bitunixStatus && (
                  <div className={`text-xs font-mono flex items-center gap-1.5 ${bitunixStatus.valid ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {bitunixStatus.valid ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                    {bitunixStatus.message}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PASO 2: TELEGRAM ALERTS */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-cyan-400">
                <Send className="w-5 h-5" />
                <h3 className="font-semibold text-sm uppercase tracking-wider">Alertas en Telegram (Móvil)</h3>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Recibe notificaciones instantáneas de ejecuciones, Stop Loss asegurados y estados de Breakeven en tu celular.
              </p>

              <div className="space-y-3 font-mono text-xs">
                <div>
                  <label className="block text-zinc-300 mb-1">TELEGRAM BOT TOKEN</label>
                  <input
                    type="password"
                    value={telegramBotToken}
                    onChange={(e) => setTelegramBotToken(e.target.value)}
                    placeholder="Ej: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz..."
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
                <div>
                  <label className="block text-zinc-300 mb-1">TELEGRAM CHAT ID</label>
                  <input
                    type="text"
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                    placeholder="Ej: 123456789"
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              {/* Botón de Test Telegram */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={handleTestTelegram}
                  disabled={testingTelegram}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-mono text-cyan-300 border border-zinc-700 transition"
                >
                  {testingTelegram ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Enviar Alerta de Prueba
                </button>

                {telegramStatus && (
                  <div className={`text-xs font-mono flex items-center gap-1.5 ${telegramStatus.valid ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {telegramStatus.valid ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                    {telegramStatus.message}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PASO 3: PARÁMETROS DE RIESGO */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-cyan-400">
                <Shield className="w-5 h-5" />
                <h3 className="font-semibold text-sm uppercase tracking-wider">Parámetros de Riesgo & Live Trading</h3>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Configura la gestión de capital y el modo de operación de Slingshot.
              </p>

              <div className="grid grid-cols-2 gap-4 font-mono text-xs">
                <div>
                  <label className="block text-zinc-300 mb-1">BALANCE VIRTUAL ($ USD)</label>
                  <input
                    type="number"
                    value={accountBalance}
                    onChange={(e) => setAccountBalance(parseFloat(e.target.value) || 1000)}
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
                <div>
                  <label className="block text-zinc-300 mb-1">RIESGO POR TRADE (2%)</label>
                  <input
                    type="number"
                    step="0.005"
                    value={maxRiskPct}
                    onChange={(e) => setMaxRiskPct(parseFloat(e.target.value) || 0.02)}
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              <div className="p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-white">Modo Live Trading (Bitunix Real)</div>
                  <div className="text-xs text-zinc-400">Ejecuta órdenes reales en tu cuenta de Bitunix Futuros.</div>
                </div>
                <button
                  type="button"
                  onClick={() => setEnableLiveTrading(!enableLiveTrading)}
                  className={`w-12 h-6 rounded-full transition-colors relative ${enableLiveTrading ? 'bg-cyan-500' : 'bg-zinc-700'}`}
                >
                  <div className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-1 ${enableLiveTrading ? 'left-7' : 'left-1'}`} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-zinc-800 bg-zinc-900/50">
          <button
            onClick={() => setStep(Math.max(1, step - 1))}
            disabled={step === 1 || saving}
            className="px-4 py-2 rounded-lg text-xs font-mono text-zinc-400 hover:text-white disabled:opacity-30 transition"
          >
            Atrás
          </button>

          <div className="flex items-center gap-3">
            {step < 3 ? (
              <button
                onClick={() => setStep(step + 1)}
                className="px-5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-bold text-xs font-mono transition shadow-[0_0_20px_rgba(6,182,212,0.4)]"
              >
                Siguiente Paso
              </button>
            ) : (
              <button
                onClick={handleSaveAndLaunch}
                disabled={saving || saveSuccess}
                className="flex items-center gap-2 px-6 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-emerald-500 hover:opacity-90 text-zinc-950 font-bold text-xs font-mono transition shadow-[0_0_25px_rgba(16,185,129,0.4)]"
              >
                {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                {saveSuccess ? '¡Configuración Guardada!' : 'Guardar y Arrancar Terminal'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
