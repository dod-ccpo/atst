from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY

import atat.models.mixins as mixins
import atat.models.types as types
from atat.models.base import Base


class PermissionSet(Base, mixins.TimestampsMixin):
    __tablename__ = "permission_sets"

    id = types.Id()
    name = Column(String, index=True, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    permissions = Column(ARRAY(String), index=True, server_default="{}", nullable=False)

    def __repr__(self):
        return "<PermissionSet(name='{}', description='{}', permissions='{}', id='{}')>".format(
            self.name, self.description, self.permissions, self.id
        )
