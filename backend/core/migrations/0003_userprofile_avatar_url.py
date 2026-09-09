from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0002_userprofile_otpchallenge')]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar_url',
            field=models.URLField(blank=True),
        ),
    ]