"""Write snapshots in the same transaction as the business change."""

import json
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from core.models import AuditEvent


def snapshot(instance):
    return json.loads(json.dumps(model_to_dict(instance), cls=DjangoJSONEncoder))


def record(actor, action, instance, before=None, after=None, summary=""):
    return AuditEvent.objects.create(
        actor=actor,
        actor_name=actor.get_username(),
        action=action,
        resource=instance._meta.model_name,
        object_id=str(instance.pk),
        summary=summary
        or f"{action.replace('_', ' ').title()} {instance._meta.verbose_name} #{instance.pk}",
        before=before or {},
        after=after if after is not None else snapshot(instance),
    )
