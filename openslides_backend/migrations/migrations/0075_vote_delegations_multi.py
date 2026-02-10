from typing import Any

from datastore.migrations import BaseModelMigration
from datastore.writer.core import BaseRequestEvent, RequestUpdateEvent

from openslides_backend.shared.patterns import fqid_from_collection_and_id

from ...shared.filters import And, FilterOperator


class Migration(BaseModelMigration):
    """
    Migrate meeting_user.vote_delegated_to_id -> vote_delegated_to_ids (list)
    and add meeting.users_vote_delegations_max_amount default.
    """

    target_migration_index = 76

    def migrate_models(self) -> list[BaseRequestEvent]:
        events: list[BaseRequestEvent] = []

        meeting_users = self.reader.filter(
            "meeting_user",
            And(
                FilterOperator("vote_delegated_to_id", "!=", None),
                FilterOperator("meta_deleted", "!=", True),
            ),
            ["vote_delegated_to_id", "vote_delegated_to_ids"],
        )
        for id_, model in meeting_users.items():
            old_id = model.get("vote_delegated_to_id")
            new_list = list(model.get("vote_delegated_to_ids") or [])
            if old_id is not None and old_id not in new_list:
                new_list.append(old_id)
            events.append(
                RequestUpdateEvent(
                    fqid_from_collection_and_id("meeting_user", id_),
                    {
                        "vote_delegated_to_ids": new_list,
                        "vote_delegated_to_id": None,
                    },
                )
            )

        meetings = self.reader.get_all("meeting")
        for id_, model in meetings.items():
            update: dict[str, Any] = {}
            if "users_vote_delegations_max_amount" not in model:
                update["users_vote_delegations_max_amount"] = 0
            if update:
                events.append(
                    RequestUpdateEvent(
                        fqid_from_collection_and_id("meeting", id_), update
                    )
                )

        return events
