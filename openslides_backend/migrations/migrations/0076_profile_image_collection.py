from datastore.migrations import BaseModelMigration
from datastore.reader.core.requests import GetManyRequestPart
from datastore.writer.core.write_request import (
    BaseRequestEvent,
    RequestCreateEvent,
    RequestUpdateEvent,
)

from openslides_backend.shared.filters import And, FilterOperator
from openslides_backend.shared.patterns import fqid_from_collection_and_id


class Migration(BaseModelMigration):
    """
    This migration replaces user/profile_image_id mediafile references with
    profile_image entries.
    """

    target_migration_index = 77

    def migrate_models(self) -> list[BaseRequestEvent]:
        events: list[BaseRequestEvent] = []
        users = self.reader.filter(
            "user",
            And(
                FilterOperator("profile_image_id", "!=", None),
                FilterOperator("meta_deleted", "!=", True),
            ),
            ["profile_image_id"],
        )
        if not users:
            return events

        mediafile_ids = {user["profile_image_id"] for user in users.values()}
        mediafiles = self.reader.get_many(
            [
                GetManyRequestPart(
                    "mediafile", list(mediafile_ids), ["create_timestamp"]
                )
            ]
        ).get("mediafile", {})

        next_profile_image_id = 1
        for user_id_str, user in users.items():
            user_id = int(user_id_str)
            mediafile_id = user["profile_image_id"]
            create_timestamp = None
            if mediafile := mediafiles.get(str(mediafile_id)):
                create_timestamp = mediafile.get("create_timestamp")

            profile_image_fields = {
                "id": next_profile_image_id,
                "user_id": user_id,
                "mediafile_id": mediafile_id,
            }
            if create_timestamp is not None:
                profile_image_fields["create_timestamp"] = create_timestamp

            events.append(
                RequestCreateEvent(
                    fqid_from_collection_and_id("profile_image", next_profile_image_id),
                    profile_image_fields,
                )
            )
            events.append(
                RequestUpdateEvent(
                    fqid_from_collection_and_id("user", user_id),
                    {"profile_image_id": next_profile_image_id},
                )
            )
            next_profile_image_id += 1

        return events
