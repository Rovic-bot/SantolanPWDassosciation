from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('assistance', '0005_referral_ticket_subject')]

    operations = [migrations.AddField(
        model_name='referralsettings', name='gmail_password_encrypted',
        field=models.TextField(blank=True, default='', editable=False),
    )]
