import csv
import io

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Contact, Lead, Unsubscribe


def parse_contact_rows(text: str):
    rows = []
    sample = (text or "").lstrip("\ufeff").strip()
    if not sample:
        return rows
    try:
        dialect = csv.Sniffer().sniff(sample.splitlines()[0] + "\n", delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
        if reader.fieldnames:
            reader.fieldnames = [((f or "").strip().lower()) for f in reader.fieldnames]
            for raw in reader:
                email = (raw.get("email") or raw.get("e-mail") or "").strip()
                if not email:
                    values = [v for v in raw.values() if v]
                    email = (values[0] if values else "").strip()
                rows.append(
                    {
                        "email": email,
                        "name": (raw.get("name") or raw.get("full_name") or "").strip(),
                        "company": (raw.get("company") or raw.get("organization") or "").strip(),
                        "phone": (raw.get("phone") or raw.get("mobile") or "").strip(),
                        "job_title": (raw.get("job_title") or raw.get("title") or "").strip(),
                        "source": (raw.get("source") or "").strip(),
                        "status": (raw.get("status") or "").strip().lower(),
                        "notes": (raw.get("notes") or raw.get("note") or "").strip(),
                    }
                )
            return rows
    except csv.Error:
        pass

    for line in sample.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.replace(";", ",").split(",")]
        rows.append(
            {
                "email": parts[0],
                "name": parts[1] if len(parts) > 1 else "",
                "company": parts[2] if len(parts) > 2 else "",
                "phone": parts[3] if len(parts) > 3 else "",
                "job_title": "",
                "source": "",
                "status": "",
                "notes": "",
            }
        )
    return rows


def import_contacts(chunks):
    added = 0
    skipped = 0
    existing = set(Contact.objects.values_list("email", flat=True))
    for chunk in chunks:
        try:
            rows = parse_contact_rows(chunk)
        except Exception:
            rows = [{"email": line.strip(), "name": "", "company": ""} for line in chunk.splitlines() if line.strip()]
        for row in rows:
            email = (row.get("email") or "").strip().lower()
            if not email or email in {"email", "e-mail"}:
                continue
            try:
                validate_email(email)
            except ValidationError:
                skipped += 1
                continue
            if email in existing:
                skipped += 1
                continue
            Contact.objects.create(
                email=email,
                name=row.get("name") or "",
                company=row.get("company") or "",
                phone=row.get("phone") or "",
                job_title=row.get("job_title") or "",
                notes=row.get("notes") or "",
                source=row.get("source") or "csv",
            )
            existing.add(email)
            added += 1
    return added, skipped


def import_leads(chunks, default_source="csv"):
    added = 0
    skipped = 0
    existing = set(Lead.objects.values_list("email", flat=True))
    valid_status = {choice[0] for choice in Lead.Status.choices}
    for chunk in chunks:
        try:
            rows = parse_contact_rows(chunk)
        except Exception:
            rows = [{"email": line.strip(), "name": "", "company": ""} for line in chunk.splitlines() if line.strip()]
        for row in rows:
            email = (row.get("email") or "").strip().lower()
            if not email or email in {"email", "e-mail"}:
                continue
            try:
                validate_email(email)
            except ValidationError:
                skipped += 1
                continue
            if email in existing:
                skipped += 1
                continue
            status = row.get("status") or Lead.Status.NEW
            if status not in valid_status:
                status = Lead.Status.NEW
            Lead.objects.create(
                email=email,
                name=row.get("name") or "",
                company=row.get("company") or "",
                phone=row.get("phone") or "",
                job_title=row.get("job_title") or "",
                notes=row.get("notes") or "",
                source=row.get("source") or default_source,
                status=status,
            )
            existing.add(email)
            added += 1
    return added, skipped


def add_contacts_to_campaign(campaign, contacts):
    added = 0
    skipped = 0
    unsub = set(Unsubscribe.objects.values_list("email", flat=True))
    existing = set(campaign.recipients.values_list("email", flat=True))
    from .models import Recipient

    for contact in contacts:
        email = contact.email.strip().lower()
        if email in existing or email in unsub:
            skipped += 1
            continue
        Recipient.objects.create(
            campaign=campaign,
            email=email,
            name=contact.name,
            company=contact.company,
        )
        existing.add(email)
        added += 1
    return added, skipped
