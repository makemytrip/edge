# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-05-19 08:09
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActionInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('servers', models.TextField()),
                ('config', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('task_start_time', models.DateTimeField(default=None, null=True)),
                ('task_end_time', models.DateTimeField(default=None, null=True)),
                ('task_ids', models.CharField(blank=True, default=None, max_length=1000, null=True)),
                ('script_file_name', models.CharField(default=None, max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='ActionQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('servers', models.TextField()),
                ('config', models.TextField()),
                ('retries', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='ActionStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('BUILDING', 'BUILDING'), ('SCHEDULED', 'SCHEDULED'), ('INPROGRESS', 'INPROGRESS'), ('FAILED', 'FAILED'), ('REVOKED', 'REVOKED'), ('COMPLETED', 'COMPLETED'), ('WAITING', 'WAITING'), ('MANUAL_FAILED', 'MANUAL_FAILED')], max_length=20, unique=True)),
                ('order', models.SmallIntegerField(default=-1)),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='Configs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50, unique=True)),
                ('value', models.CharField(max_length=300)),
                ('is_expression', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Application Properties',
            },
        ),
        migrations.CreateModel(
            name='Dendrogram',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server', models.CharField(db_index=True, max_length=30)),
                ('version', models.CharField(db_index=True, max_length=300)),
            ],
        ),
        migrations.CreateModel(
            name='Env',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, unique=True)),
                ('script_file_name', models.CharField(default=None, max_length=50)),
                ('config', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalActionInfo',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('servers', models.TextField()),
                ('config', models.TextField()),
                ('timestamp', models.DateTimeField(blank=True, editable=False)),
                ('task_start_time', models.DateTimeField(default=None, null=True)),
                ('task_end_time', models.DateTimeField(default=None, null=True)),
                ('task_ids', models.CharField(blank=True, default=None, max_length=1000, null=True)),
                ('script_file_name', models.CharField(default=None, max_length=50)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical action info',
            },
        ),
        migrations.CreateModel(
            name='HistoricalConfigs',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=50)),
                ('value', models.CharField(max_length=300)),
                ('is_expression', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Application Properties',
            },
        ),
        migrations.CreateModel(
            name='HistoricalEnv',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=30)),
                ('script_file_name', models.CharField(default=None, max_length=50)),
                ('config', models.TextField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical env',
            },
        ),
        migrations.CreateModel(
            name='HistoricalProject',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=110)),
                ('config', models.TextField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('env', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='space.Env')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical project',
            },
        ),
        migrations.CreateModel(
            name='HistoricalSpace',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=30)),
                ('admin_dl', models.CharField(default=None, max_length=500, verbose_name='DL(s) for admin access to space')),
                ('operator_dl', models.CharField(default=None, max_length=500, verbose_name='DL(s) for read access to space')),
                ('nav_color', models.CharField(blank=True, max_length=20, verbose_name='Theme color for space')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical space',
            },
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default=None, max_length=20)),
                ('method_list', models.CharField(default=None, max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=110, unique=True)),
                ('config', models.TextField(blank=True, null=True)),
                ('env', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='space.Env', verbose_name='Infra enviornment')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectConfigs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100)),
                ('value', models.CharField(max_length=200)),
                ('project_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Project')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectTale',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(db_index=True, max_length=30)),
                ('timestamp', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Project')),
            ],
        ),
        migrations.CreateModel(
            name='Space',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, unique=True)),
                ('admin_dl', models.CharField(default=None, max_length=500, verbose_name='DL(s) for admin access to space')),
                ('operator_dl', models.CharField(default=None, max_length=500, verbose_name='DL(s) for read access to space')),
                ('nav_color', models.CharField(blank=True, max_length=20, verbose_name='Theme color for space')),
            ],
        ),
        migrations.AddField(
            model_name='project',
            name='space',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='space.Space', verbose_name='associated space'),
        ),
        migrations.AlterUniqueTogether(
            name='plan',
            unique_together=set([('name',)]),
        ),
        migrations.AddField(
            model_name='historicalproject',
            name='space',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='space.Space'),
        ),
        migrations.AddField(
            model_name='historicalactioninfo',
            name='action',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='space.Plan'),
        ),
        migrations.AddField(
            model_name='historicalactioninfo',
            name='history_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='historicalactioninfo',
            name='project',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='space.Project'),
        ),
        migrations.AddField(
            model_name='historicalactioninfo',
            name='status',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='space.ActionStatus'),
        ),
        migrations.AddField(
            model_name='historicalactioninfo',
            name='user',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dendrogram',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Project'),
        ),
        migrations.AddField(
            model_name='dendrogram',
            name='user',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='actionqueue',
            name='action',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Plan'),
        ),
        migrations.AddField(
            model_name='actionqueue',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Project'),
        ),
        migrations.AddField(
            model_name='actionqueue',
            name='space',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Space'),
        ),
        migrations.AddField(
            model_name='actionqueue',
            name='user',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='actioninfo',
            name='action',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Plan'),
        ),
        migrations.AddField(
            model_name='actioninfo',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.Project'),
        ),
        migrations.AddField(
            model_name='actioninfo',
            name='status',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='space.ActionStatus'),
        ),
        migrations.AddField(
            model_name='actioninfo',
            name='user',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='projectconfigs',
            unique_together=set([('project_id', 'key')]),
        ),
        migrations.AlterUniqueTogether(
            name='dendrogram',
            unique_together=set([('project', 'server')]),
        ),
        migrations.AlterUniqueTogether(
            name='actionqueue',
            unique_together=set([('project', 'action')]),
        ),
        migrations.AlterUniqueTogether(
            name='actioninfo',
            unique_together=set([('project', 'timestamp')]),
        ),
    ]
