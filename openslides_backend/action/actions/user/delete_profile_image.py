from typing import Any

from ....models.models import User
from ....permissions.management_levels import OrganizationManagementLevel
from ....permissions.permission_helper import has_organization_management_level
from ....shared.exceptions import MissingPermission
from ....shared.patterns import fqid_from_collection_and_id
from ...generics.update import UpdateAction
from ...util.default_schema import DefaultSchema
from ...util.register import register_action
from ..mediafile.delete import MediafileDelete


@register_action("user.delete_profile_image")
class UserDeleteProfileImage(UpdateAction):
    """
    Action to delete a user's profile image.
    """

    model = User()
    schema = DefaultSchema(User()).get_update_schema()

    def check_permissions(self, instance: dict[str, Any]) -> None:
        self.assert_not_anonymous()
        if instance["id"] == self.user_id:
            return
        if has_organization_management_level(
            self.datastore,
            self.user_id,
            OrganizationManagementLevel.SUPERADMIN,
        ):
            return
        raise MissingPermission(OrganizationManagementLevel.SUPERADMIN)

    def get_meeting_id(self, instance: dict[str, Any]) -> int | None:
        # The user is org-wide; no meeting context.
        return None

    def check_for_archived_meeting(self, instance: dict[str, Any]) -> None:
        # Org-wide action: no meeting context, so no archived-meeting check.
        return None

    def update_instance(self, instance: dict[str, Any]) -> dict[str, Any]:
        user_id = instance["id"]
        user = self.datastore.get(
            fqid_from_collection_and_id("user", user_id),
            ["profile_image_id"],
        )
        if old_mediafile_id := user.get("profile_image_id"):
            self.execute_other_action(MediafileDelete, [{"id": old_mediafile_id}])
        instance["profile_image_id"] = None
        return instance
