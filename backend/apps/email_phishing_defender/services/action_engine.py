import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class ActionEngine:
    """Determine and execute actions on emails based on phishing-detection scores."""

    def __init__(self, graph_service):
        self.graph = graph_service

    @staticmethod
    def determine_action(score):
        if score > 80:
            return "quarantine"
        if score >= 50:
            return "label_suspicious"
        return "no_action"

    def execute(self, detection, mailbox):
        from apps.email_phishing_defender.models import Action

        action_type = self.determine_action(detection.score)

        action = Action.objects.create(
            detection=detection,
            action_type=action_type,
            status="pending",
        )

        if action_type == "no_action":
            action.status = "success"
            action.executed_at = timezone.now()
            action.save()
            return action

        try:
            message = detection.message
            user_id = mailbox.ms_user_id
            msg_id = message.ms_message_id

            if action_type == "quarantine":
                self.graph.move_message(user_id, msg_id, "junkemail")
            elif action_type == "label_suspicious":
                self.graph.apply_category(user_id, msg_id, ["Suspicious"])

            action.status = "success"
            action.executed_at = timezone.now()
        except Exception as exc:
            logger.error("Action execution failed: %s", exc)
            action.status = "failed"
            action.error_message = str(exc)
            action.retry_count += 1

        action.save()
        return action
