import pytest
import time
from pathlib import Path
from engine.core.vault import SlingshotVault

@pytest.mark.asyncio
async def test_vault_trade_milestones_persistence(tmp_path: Path):
    """
    SOP-116: Valida que los hitos de Take Profit / Breakeven se persistan
    atómicamente en SQLite WAL y sobrevivan a reinicios del proceso.
    """
    db_file = tmp_path / "test_vault.db"
    vault = SlingshotVault(db_path=db_file)

    stage_key = "primary_BNBUSDT_pos_12345"
    stage_id = "FAST_BE"

    # 1. Antes de registrar, no debe existir
    assert vault.has_trade_stage_dispatched(stage_key, stage_id) is False

    # 2. Registrar el hito
    vault.record_trade_stage_dispatch(stage_key, stage_id)

    # 3. Debe reportar como ya despachado
    assert vault.has_trade_stage_dispatched(stage_key, stage_id) is True

    # 4. Simular reinicio del proceso instanciando un nuevo Vault sobre la misma DB
    restarted_vault = SlingshotVault(db_path=db_file)
    assert restarted_vault.has_trade_stage_dispatched(stage_key, stage_id) is True

    # 5. Otra etapa no registrada debe retornar False
    assert restarted_vault.has_trade_stage_dispatched(stage_key, "TP3_RUNNER") is False
