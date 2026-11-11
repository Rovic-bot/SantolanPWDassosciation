from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('announcements', '0004_preserve_result_source_content')]

    operations = [
        migrations.AddField(
            model_name='announcement', name='source_office',
            field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(
            model_name='announcement', name='linked_program',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='information_announcements', to='programs.program')),
        migrations.AddConstraint(
            model_name='announcement',
            constraint=models.CheckConstraint(
                condition=models.Q(program__isnull=True) | models.Q(linked_program__isnull=True),
                name='announcement_single_program_link')),
    ]
