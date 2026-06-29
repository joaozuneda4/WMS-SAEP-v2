"""Tipos do seam estoque ↔ outros domínios."""

from decimal import Decimal
from typing import TypedDict


class ItemReservaEstoque(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal


class ItemLiberacaoReserva(TypedDict):
    material_id: int
    quantidade_reservada: Decimal


class ItemAtendimentoSaldo(TypedDict):
    material_id: int
    quantidade_autorizada: Decimal
    quantidade_entregue: Decimal
