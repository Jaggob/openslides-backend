from typing import Any

from ....models.models import AssignmentCandidate
from ....services.datastore.commands import GetManyRequest
from ....permissions.permission_helper import has_perm
from ....permissions.permissions import Permissions
from ....shared.exceptions import ActionException, MissingPermission
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

    def check_permissions(self, instance: dict[str, Any]) -> None:
        super().check_permissions(instance)
        if self.internal:
            return
        if "application" not in instance and "attachment_mediafile_ids" not in instance:
            return

        assignment_candidate = self.datastore.get(
            fqid_from_collection_and_id(self.model.collection, instance["id"]),
            ["meeting_user_id", "assignment_id"],
            lock_result=False,
        )
        assignment = self.datastore.get(
            fqid_from_collection_and_id("assignment", assignment_candidate["assignment_id"]),
            ["meeting_id"],
            lock_result=False,
        )
        meeting_id = assignment["meeting_id"]

        if has_perm(self.datastore, self.user_id, Permissions.Assignment.CAN_MANAGE, meeting_id):
            return

        user = self.datastore.get(
            fqid_from_collection_and_id("user", self.user_id), ["meeting_user_ids"]
        )
        meeting_user_id = assignment_candidate.get("meeting_user_id")
        meeting_user_ids = user.get("meeting_user_ids") or []
        is_self_candidate = meeting_user_id in meeting_user_ids
        if not is_self_candidate and meeting_user_id:
            meeting_user = self.datastore.get(
                fqid_from_collection_and_id("meeting_user", meeting_user_id),
                ["user_id"],
                lock_result=False,
            )
            is_self_candidate = meeting_user.get("user_id") == self.user_id
        if is_self_candidate and has_perm(
            self.datastore, self.user_id, Permissions.Assignment.CAN_NOMINATE_SELF, meeting_id
        ):
            return

        raise MissingPermission(Permissions.Assignment.CAN_MANAGE)

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
        meeting = self.datastore.get(
            fqid_from_collection_and_id("meeting", assignment["meeting_id"]),
            ["assignments_enable_candidate_applications"],
            lock_result=False,
        )
        if (
            not meeting.get("assignments_enable_candidate_applications")
            and ("application" in instance or "attachment_mediafile_ids" in instance)
        ):
            raise ActionException("Candidate applications are disabled in this meeting.")
        if assignment.get("phase") == "finished" and not self.is_meeting_deleted(
            assignment.get("meeting_id", 0)
        ):
            raise ActionException(
                "It is not permitted to edit a candidate in a finished assignment!"
            )
        return instance
