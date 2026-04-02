import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'
django.setup()

from apps.email_phishing_defender.models import Tenant, Mailbox
from apps.email_phishing_defender.services.microsoft_graph import MicrosoftGraphService
from django.utils import timezone

t = Tenant.objects.first()
g = MicrosoftGraphService(t)

# 1. Fetch org name
try:
    name = g.fetch_org_name()
    print(f"Org name: {name}")
    if name and not t.name:
        t.name = name
        t.save(update_fields=["name"])
except Exception as e:
    print(f"Org name error: {e}")

# 2. Fetch users
try:
    users = g.fetch_users()
    print(f"Found {len(users)} users")
    for u in users[:10]:
        email = u.get("mail") or u.get("userPrincipalName", "")
        dn = u.get("displayName", "")
        print(f"  {email} ({dn})")

        if email and "@" in email:
            Mailbox.objects.update_or_create(
                tenant=t,
                ms_user_id=u["id"],
                defaults={"email": email, "display_name": dn, "is_active": True},
            )

    t.last_synced_at = timezone.now()
    t.save(update_fields=["last_synced_at"])
    print(f"\nSynced! Total mailboxes: {t.mailboxes.count()}")
except Exception as e:
    print(f"User fetch error: {type(e).__name__}: {e}")
