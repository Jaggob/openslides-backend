import base64
from time import time
from typing import Any

import magic as python_magic

from ....models.models import User
from ....permissions.management_levels import OrganizationManagementLevel
from ....permissions.permission_helper import has_organization_management_level
from ....shared.exceptions import ActionException, MissingPermission
from ....shared.patterns import KEYSEPARATOR, fqid_from_collection_and_id
from ....shared.schema import optional_id_schema
from ....shared.util import ONE_ORGANIZATION_ID
from ...generics.update import UpdateAction
from ...util.default_schema import DefaultSchema
from ...util.register import register_action
from ..mediafile.upload import MediafileUploadAction
from ..profile_image.create import ProfileImageCreate
from ..profile_image.delete import ProfileImageDelete

MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


@register_action("user.set_profile_image")
class UserSetProfileImage(UpdateAction):
    """
    Action to set or replace a user's profile image.
    """

    model = User()
    schema = DefaultSchema(User()).get_update_schema(
        additional_required_fields={
            "file": {"type": "string"},
            "filename": {"type": "string"},
        },
        additional_optional_fields={
            "published_to_meetings_in_organization_id": optional_id_schema,
        },
    )

    def validate_instance(self, instance: dict[str, Any]) -> None:
        super().validate_instance(instance)
        file_b64 = instance.get("file")
        filename = instance.get("filename")
        if not filename:
            raise ActionException("Filename must not be empty.")
        try:
            decoded_file = base64.b64decode(file_b64)
        except Exception as err:
            raise ActionException("Cannot decode base64 file.") from err
        if len(decoded_file) > MAX_PROFILE_IMAGE_SIZE:
            raise ActionException("Profile image exceeds maximum size of 5 MB.")
        mimetype = python_magic.from_buffer(decoded_file, mime=True)
        if not mimetype.startswith("image/"):
            raise ActionException("Uploaded file is not an image.")

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
        file_b64 = instance.pop("file")
        filename = instance.pop("filename")
        published_to_meetings_in_organization_id = instance.pop(
            "published_to_meetings_in_organization_id", None
        )

        user = self.datastore.get(
            fqid_from_collection_and_id("user", user_id),
            ["profile_image_id"],
        )
        if old_profile_image_id := user.get("profile_image_id"):
            self.execute_other_action(
                ProfileImageDelete, [{"id": old_profile_image_id}]
            )

        title = f"profile-image-user-{user_id}-{int(time())}"
        owner_id = f"organization{KEYSEPARATOR}{ONE_ORGANIZATION_ID}"
        publish_id = (
            published_to_meetings_in_organization_id
            if published_to_meetings_in_organization_id is not None
            else ONE_ORGANIZATION_ID
        )
        upload_payload = {
            "title": title,
            "owner_id": owner_id,
            "filename": filename,
            "file": file_b64,
            "published_to_meetings_in_organization_id": publish_id,
        }
        result = self.execute_other_action(
            MediafileUploadAction, [upload_payload]
        )
        if not result:
            raise ActionException("Failed to upload profile image.")
        new_mediafile_id = result[0]["id"]

        create_timestamp = int(time())
        result = self.execute_other_action(
            ProfileImageCreate,
            [
                {
                    "user_id": user_id,
                    "mediafile_id": new_mediafile_id,
                    "create_timestamp": create_timestamp,
                }
            ],
        )
        if not result:
            raise ActionException("Failed to create profile image entry.")
        new_profile_image_id = result[0]["id"]

        instance["profile_image_id"] = new_profile_image_id
        return instance
