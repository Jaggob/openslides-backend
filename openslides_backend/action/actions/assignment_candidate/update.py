from typing import Any

from ....models.models import AssignmentCandidate
from ....services.datastore.commands import GetManyRequest
from ....shared.exceptions import ActionException
from ....shared.patterns import fqid_from_collection_and_id
from ....shared.schema import id_list_schema
from ...generics.update import UpdateAction
from ...util.default_schema import DefaultSchema
from ...util.register import register_action
from ...util.typing import ActionData
from ..meeting_mediafile.attachment_mixin import AttachmentMixin
from .mixins import PermissionMixin


@register_action("assignment_candidate.update")
class AssignmentCandidateUpdate(PermissionMixin, AttachmentMixin, UpdateAction):
    """
    Action to update a assignment_candidate's data.
    """

    model = AssignmentCandidate()
    schema = DefaultSchema(AssignmentCandidate()).get_update_schema(
        optional_properties=["application", "weight"],
        additional_optional_fields={"attachment_mediafile_ids": id_list_schema},
    )

    def prefetch(self, action_data: ActionData) -> None:
        self.datastore.get_many(
            [
                GetManyRequest(
                    "assignment_candidate",
                    list({instance["id"] for instance in action_data if instance.get("id")}),
                    ["assignment_id"],
                )
            ]
        )

    def update_instance(self, instance: dict[str, Any]) -> dict[str, Any]:
        instance = super().update_instance(instance)
        if not self.internal and "weight" in instance:
            raise ActionException("It is not permitted to change candidate sorting via update.")

        assignment_candidate = self.datastore.get(
            fqid_from_collection_and_id(self.model.collection, instance["id"]),
            ["assignment_id"],
        )
        assignment = self.datastore.get(
            fqid_from_collection_and_id("assignment", assignment_candidate["assignment_id"]),
            ["phase", "meeting_id"],
            lock_result=False,
        )
        if assignment.get("phase") == "finished" and not self.is_meeting_deleted(
            assignment.get("meeting_id", 0)
        ):
            raise ActionException(
                "It is not permitted to edit a candidate in a finished assignment!"
            )
        return instance
