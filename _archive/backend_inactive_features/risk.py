import pandas as pd
import os

class RiskManager:
    """
    Nivel 4: El Escudo Protector (Paul Perdices Risk Math).
    Obliga al sistema a nunca arriesgar más del 1% del capital y
    asegura que toda entrada tenga un Ratio Beneficio/Riesgo (R:R) mínimo de 3:1.
    """
    
    def __init__(
        self,
        account_balance: float = float(os.getenv('ACCOUNT_BALANCE', '1000.0')),
        max_risk_pct: float = float(os.getenv('MAX_RISK_PCT', '0.01')),
        min_rr: float = float(os.getenv('MIN_RR', '3.0'))
    ):
        self.account_balance = account_balance
        self.max_risk_pct = max_risk_pct     # 1% por trade
        self.min_rr = min_rr                 # 3:1 de ganancia obligatoria
        self.risk_amount = self.account_balance * self.max_risk_pct
        
    def calculate_position(self, entry_price: float, stop_loss: float) -> dict:
        """
        Calcula el tamaño de la posición basado en el riesgo ($10 si la cuenta es de $1000)
        y la distancia porcentual al Stop Loss.
        """
        if entry_price <= 0 or stop_loss <= 0 or entry_price == stop_loss:
            return {"valid": False, "reason": "Precios inválidos o SL igual al Entry"}
            
        # Distancia al Stop Loss (Riesgo real de la operación por unidad)
        sl_distance = abs(entry_price - stop_loss)
        sl_pct = sl_distance / entry_price
        
        # Tamaño de la posición (Position Size)
        # Tamaño = Capital a Arriesgar / Distancia al SL %
        # Ejemplo: Arriesgamos $10. Si el SL está a 5% de distancia: $10 / 0.05 = Tamaño Total $200
        position_size_usd = self.risk_amount / sl_pct
        
        # Cantidad de monedas a comprar (Quantity)
        quantity = position_size_usd / entry_price
        
        # Determinar dirección para calcular el Take Profit
        direction = "LONG" if entry_price > stop_loss else "SHORT"
        
        # Calcular el Take Profit obligado (3 veces la distancia del SL)
        if direction == "LONG":
            take_profit_3r = entry_price + (sl_distance * self.min_rr)
            breakeven_trigger = entry_price + sl_distance # Cuando llegue a 1:1
        else:
            take_profit_3r = entry_price - (sl_distance * self.min_rr)
            breakeven_trigger = entry_price - sl_distance
            
        return {
            "valid": True,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": round(take_profit_3r, 4),
            "breakeven_trigger": round(breakeven_trigger, 4),
            "risk_usd": self.risk_amount,
            "position_size_usd": round(position_size_usd, 2),
            "quantity": round(quantity, 6),
            "sl_distance_pct": round(sl_pct * 100, 2)
        }

if __name__ == "__main__":
    # Prueba del Escudo Protector
    rm = RiskManager(account_balance=1000.0) # Cuenta hipotética de $1000 USD
    
    print("🛡️ Nivel 4: Motor de Riesgo Militarizado Activo")
    print(f"Capital: ${rm.account_balance} | Riesgo Máximo: {rm.max_risk_pct*100}% (${rm.risk_amount}) | R:R Exigido: {rm.min_rr}:1\n")
    
    # Simulemos una señal SMC perfecta (Long en BTC apoyado en un Order Block)
    btc_entry = 95000.0
    btc_sl = 94500.0 # Stop Loss ajustado debajo del Order Block
    
    print("Simulando Señal SMC (LONG Bitcoin):")
    print(f"Entrada: ${btc_entry} | Stop Loss: ${btc_sl}")
    
    trade = rm.calculate_position(btc_entry, btc_sl)
    
    if trade["valid"]:
        print("\n✅ Trade Aprobado por Gestión de Riesgo:")
        print(f"💰 Tamaño de Posición (Apalancamiento): ${trade['position_size_usd']}")
        print(f"🪙 Cantidad a comprar: {trade['quantity']} BTC")
        print(f"🎯 Take Profit Obligatorio (3:1): ${trade['take_profit']}")
        print(f"🛡️ Nivel de Breakeven Automático (1:1): ${trade['breakeven_trigger']}")
        print(f"💥 Si sale mal, perderemos EXACTAMENTE: ${trade['risk_usd']}")
    else:
        print(f"❌ Trade Rechazado: {trade['reason']}")
