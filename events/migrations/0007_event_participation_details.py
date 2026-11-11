from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('events', '0006_annual_observances')]

    operations = [
        migrations.AddField(model_name='event', name='event_category',
            field=models.CharField(blank=True, default='', max_length=12,
                choices=[('general', 'General Events'), ('specific', 'Specific Events')])),
        *[migrations.AddField(model_name=model_name, name='target_audience',
            field=models.TextField(blank=True, max_length=1000, verbose_name='Target Audience'))
          for model_name in ('event', 'annualobservance', 'annualobservancerevision')],
        *[migrations.AddField(model_name=model_name, name='who_may_participate',
            field=models.TextField(blank=True, max_length=2000, verbose_name='Who May Participate'))
          for model_name in ('event', 'annualobservance', 'annualobservancerevision')],
        migrations.AddConstraint(model_name='event',
            constraint=models.CheckConstraint(condition=models.Q(event_category__in=['', 'general', 'specific']),
                                             name='event_public_category')),
    ]
