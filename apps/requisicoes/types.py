"""Tipos do seam forms/formsets ↔ services em requisicoes."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LinhaAtendimento:
    item_id: int
    quantidade_entregue: Decimal
    justificativa: str
