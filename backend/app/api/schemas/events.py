"""Interaction events as the server stores them (§5.6.1).

The request body of POST /api/events is the contract `InteractionEventBatch`
(app/contracts/interaction.py); this is what the developer endpoint lists back.
"""

from pydantic import AwareDatetime, PositiveInt

from app.api.schemas.common import Schema
from app.contracts import InteractionEvent


class LoggedEvent(Schema):
    student_id: PositiveInt
    received_at: AwareDatetime
    event: InteractionEvent
