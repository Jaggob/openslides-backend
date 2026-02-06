from typing import Any

from ....models.models import ProfileImage
from ...generics.delete import DeleteAction
from ...util.action_type import ActionType
from ...util.default_schema import DefaultSchema
from ...util.register import register_action


@register_action("profile_image.delete", action_type=ActionType.BACKEND_INTERNAL)
class ProfileImageDelete(DeleteAction):
    """Action to delete a profile image entry."""

    model = ProfileImage()
    schema = DefaultSchema(ProfileImage()).get_delete_schema()

    def get_meeting_id(self, instance: dict[str, Any]) -> int | None:
        # Profile images are org-wide; no meeting context.
        return None

    def check_for_archived_meeting(self, instance: dict[str, Any]) -> None:
        # Org-wide action: no meeting context, so no archived-meeting check.
        return None
