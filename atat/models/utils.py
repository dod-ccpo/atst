from contextlib import contextmanager
from typing import List

from sqlalchemy import Interval, and_, func, or_, sql

from atat.database import db
from atat.domain.exceptions import ClaimFailedException


@contextmanager
def claim_for_update(resource, minutes=30):
    """
    Claim a mutually exclusive expiring hold on a resource.
    Uses the database as a central source of time in case the server clocks have drifted.

    Args:
        resource:   A SQLAlchemy model instance with a `claimed_until` attribute.
        minutes:    The maximum amount of time, in minutes, to hold the claim.
    """
    model = resource.__class__

    claim_until = func.now() + func.cast(
        sql.functions.concat(minutes, " MINUTES"), Interval
    )

    # Optimistically query for and update the resource in question. If it's
    # already claimed, `rows_updated` will be 0 and we can give up.
    rows_updated = (
        db.session.query(model)
        .filter(
            and_(
                model.id == resource.id,
                or_(model.claimed_until.is_(None), model.claimed_until <= func.now(),),
            )
        )
        .update({"claimed_until": claim_until}, synchronize_session="fetch")
    )
    if rows_updated < 1:
        raise ClaimFailedException(resource)

    # Fetch the claimed resource
    claimed = db.session.query(model).filter_by(id=resource.id).one()

    try:
        # Give the resource to the caller.
        yield claimed
    finally:
        # Release the claim.
        db.session.query(model).filter(model.id == resource.id).filter(
            model.claimed_until != None
        ).update({"claimed_until": None}, synchronize_session="fetch")
        db.session.commit()


@contextmanager
def claim_many_for_update(resources: List, minutes=30):
    """
    Claim a mutually exclusive expiring hold on a group of resources.
    Uses the database as a central source of time in case the server clocks have drifted.

    Args:
        resources:   A list of SQLAlchemy model instances with a `claimed_until` attribute.
        minutes:    The maximum amount of time, in minutes, to hold the claim.
    """
    model = resources[0].__class__

    claim_until = func.now() + func.cast(
        sql.functions.concat(minutes, " MINUTES"), Interval
    )

    ids = tuple(r.id for r in resources)

    # Optimistically query for and update the resources in question. If they're
    # already claimed, `rows_updated` will be 0 and we can give up.
    rows_updated = (
        db.session.query(model)
        .filter(
            and_(
                model.id.in_(ids),
                or_(model.claimed_until.is_(None), model.claimed_until <= func.now(),),
            )
        )
        .update({"claimed_until": claim_until}, synchronize_session="fetch")
    )
    if rows_updated < 1:
        # TODO: Generalize this exception class so it can take multiple resources
        raise ClaimFailedException(resources[0])

    # Fetch the claimed resources
    claimed = db.session.query(model).filter(model.id.in_(ids)).all()

    try:
        # Give the resource to the caller.
        yield claimed
    finally:
        # Release the claim.
        db.session.query(model).filter(model.id.in_(ids)).filter(
            model.claimed_until != None
        ).update({"claimed_until": None}, synchronize_session="fetch")
        db.session.commit()
