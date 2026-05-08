import pandas as pd
import numpy as np
import unittest
from datetime import datetime, timezone, timedelta
from engine.core.confluence import ConfluenceManager

class TestConfluenceManager(unittest.TestCase):
    def setUp(self):
        self.manager = ConfluenceManager()
        # Crear un DataFrame sintético con las columnas requeridas para v10.2.0
        self.df = pd.DataFrame([{
            "timestamp": datetime.now(timezone.utc),
            "close": 85000.0,
            "volume": 1200.0,
            "high": 85050.0,
            "low": 84950.0,
            "open": 84980.0,
            "market_regime": "MARKUP" # Narrativa alineada
        }])

    def test_ob_confluence_bonus(self):
        """Prueba que la presencia de un Order Block (OB) suma puntos."""
        # Inyectar OB en la vela actual del DataFrame
        self.df["ob_bullish"] = True
        
        signal_long = {"type": "LONG", "price": 85000.0}
        
        result = self.manager.evaluate_signal(
            self.df,
            signal_long
        )
        score = result["score"]
        checklist = result["checklist"]
        
        # En v10.2.0 el factor es "Zonas POI"
        self.assertTrue(any(item['factor'] == "Zonas POI" and item['status'] in ("CONFIRMADO", "PARCIAL") for item in checklist))
        self.assertGreaterEqual(score, 5) 

    def test_htf_veto_logic(self):
        """Prueba que el HTF Bias opuesto veta la señal."""
        signal_long = {"type": "LONG", "price": 85000.0}
        now = datetime.now(timezone.utc)
        
        # Evento macro a 10 mins (inminente < 30m para Veto Macro News)
        economic_events = [{
            "title": "FED BLACK SWAN",
            "impact": "High",
            "date": (now + timedelta(minutes=10)).isoformat()
        }]
        
        # Sincronizar DF con 'now'
        self.df["timestamp"] = now
        
        result = self.manager.evaluate_signal(
            self.df,
            signal_long, 
            economic_events=economic_events
        )
        
        checklist = result["checklist"]
        # En v10.2.0, el veto macro es "Veto Macro News" con status "DENEGADO"
        self.assertTrue(any(item['factor'] == "Veto Macro News" and item['status'] == "DENEGADO" for item in checklist))
        self.assertEqual(result["conviction"], "VETADA")

    def test_news_divergence_penalty(self):
        """Prueba que las noticias opuestas restan puntos al score."""
        signal_long = {"type": "LONG", "price": 85000.0}
        # Noticia reciente (hace 2 min) Bearish
        news_items = [{
            "sentiment": "BEARISH", 
            "weight": 1.0, 
            "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        }]
        
        # Necesitamos un impacto reciente para activar la lógica de penalización por divergencia (Línea 265)
        economic_events = [{
            "title": "Old News",
            "impact": "High",
            "date": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        }]
        
        result = self.manager.evaluate_signal(
            self.df,
            signal_long,
            news_items=news_items,
            economic_events=economic_events
        )
        checklist = result["checklist"]
        
        # En v10.2.0 la penalización por divergencia de noticias se registra como "Macro" / "DIVERGENTE"
        self.assertTrue(any(item['factor'] == "Macro" and item['status'] == "DIVERGENTE" for item in checklist))

    def test_score_clamping(self):
        """Prueba que el score final se mantiene entre 0 y 100."""
        signal = {"type": "LONG"}
        result = self.manager.evaluate_signal(
            self.df,
            signal,
            onchain_bias="BEARISH_WARNING" # Penalización fuerte
        )
        score = result["score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

if __name__ == '__main__':
    unittest.main()
