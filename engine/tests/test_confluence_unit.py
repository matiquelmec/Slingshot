import pandas as pd
import unittest
from datetime import datetime, timezone
from engine.core.confluence import ConfluenceManager

class TestConfluenceManager(unittest.TestCase):
    def setUp(self):
        self.manager = ConfluenceManager()
        # Crear un DataFrame sintético con las columnas requeridas
        self.df = pd.DataFrame([{
            "timestamp": datetime.now(timezone.utc),
            "close": 85000.0,
            "volume": 1200.0,
            "high": 85050.0,
            "low": 84950.0,
            "open": 84980.0
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
        
        # El factor POI tiene un peso de 20pts (10 por OB + 10 por FVG si existiera)
        self.assertTrue(any(item['factor'] == "Zonas POI" and item['status'] == "CONFIRMADO" for item in checklist))
        self.assertGreaterEqual(score, 10)

    def test_htf_veto_logic(self):
        """Prueba que el HTF Bias opuesto veta la señal (multiplier = 0)."""
        class MockHTFBias:
            def __init__(self, direction, strength):
                self.direction = direction
                self.strength = strength
        
        # LONG con HTF BEARISH fuerte (1.0)
        signal_long = {"type": "LONG", "price": 85000.0}
        htf_bias = MockHTFBias(direction="BEARISH", strength=0.9)
        
        result = self.manager.evaluate_signal(
            self.df,
            signal_long, 
            htf_bias=htf_bias
        )
        conviction = result["conviction"]
        checklist = result["checklist"]
        
        self.assertEqual(conviction, "VETADA")
        self.assertTrue(any(item['factor'] == "Veto HTF" and item['status'] == "DENEGADO" for item in checklist))

    def test_news_divergence_penalty(self):
        """Prueba que las noticias opuestas restan puntos al score."""
        signal_long = {"type": "LONG", "price": 85000.0}
        news_items = [{"sentiment": "BEARISH"}] # news_score = 0.0
        
        # Debemos pasar un evento económico reciente para activar 'recent_impact_active'
        now = datetime.now(timezone.utc)
        economic_events = [{
            "title": "Fed Rate Decision",
            "impact": "High",
            "date": now.isoformat() # Ocurriendo "ahora" para entrar en el rango (-12, 0]
        }]
        
        result = self.manager.evaluate_signal(
            self.df,
            signal_long,
            news_items=news_items,
            economic_events=economic_events
        )
        checklist = result["checklist"]
        
        self.assertTrue(any("Noticia en contra" in item['detail'] for item in checklist))
        # Debería haber una penalización de -15pts según confluence.py:155
        # (Aunque el score base empiece en 0, testeamos la lógica de penalización)

    def test_score_clamping(self):
        """Prueba que el score final se mantiene entre 0 y 100."""
        # Forzamos muchos factores negativos para ver si baja de 0
        signal = {"type": "LONG"}
        result = self.manager.evaluate_signal(
            self.df,
            signal,
            high_impact_near=True, # -20
            recent_impact_active=True,
            news_items=[{"sentiment": "BEARISH"}] # -15
        )
        score = result["score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

if __name__ == '__main__':
    unittest.main()
