# Generated starter migration for assignment submission.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('canonical_name', models.CharField(max_length=120, unique=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
            ],
        ),
        migrations.CreateModel(
            name='ExpenseGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_filename', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('PROCESSING', 'Processing'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PROCESSING', max_length=20)),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('posted_rows', models.PositiveIntegerField(default=0)),
                ('review_rows', models.PositiveIntegerField(default=0)),
                ('skipped_rows', models.PositiveIntegerField(default=0)),
                ('report_json', models.JSONField(blank=True, default=dict)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imports', to='expenses.expensegroup')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_row_number', models.PositiveIntegerField(blank=True, null=True)),
                ('date', models.DateField()),
                ('description', models.CharField(max_length=255)),
                ('normalized_description', models.CharField(db_index=True, max_length=255)),
                ('amount_original', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(default='INR', max_length=3)),
                ('fx_rate_to_inr', models.DecimalField(decimal_places=4, default=1, max_digits=12)),
                ('amount_inr', models.DecimalField(decimal_places=2, max_digits=14)),
                ('split_type', models.CharField(choices=[('equal', 'Equal'), ('unequal', 'Unequal'), ('percentage', 'Percentage'), ('share', 'Share')], max_length=20)),
                ('split_with_raw', models.TextField(blank=True)),
                ('split_details_raw', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('POSTED', 'Posted'), ('REVIEW_REQUIRED', 'Review required'), ('SKIPPED', 'Skipped')], default='POSTED', max_length=20)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenses', to='expenses.expensegroup')),
                ('import_batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expenses', to='expenses.importbatch')),
                ('paid_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expenses_paid', to='expenses.person')),
            ],
            options={'ordering': ['date', 'id']},
        ),
        migrations.CreateModel(
            name='Settlement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_row_number', models.PositiveIntegerField(blank=True, null=True)),
                ('date', models.DateField()),
                ('amount_original', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(default='INR', max_length=3)),
                ('fx_rate_to_inr', models.DecimalField(decimal_places=4, default=1, max_digits=12)),
                ('amount_inr', models.DecimalField(decimal_places=2, max_digits=14)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('POSTED', 'Posted'), ('REVIEW_REQUIRED', 'Review required'), ('SKIPPED', 'Skipped')], default='POSTED', max_length=20)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='settlements', to='expenses.expensegroup')),
                ('import_batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='settlements', to='expenses.importbatch')),
                ('paid_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='settlements_paid', to='expenses.person')),
                ('paid_to', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='settlements_received', to='expenses.person')),
            ],
            options={'ordering': ['date', 'id']},
        ),
        migrations.CreateModel(
            name='GroupMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('starts_on', models.DateField()),
                ('ends_on', models.DateField(blank=True, null=True)),
                ('role', models.CharField(default='member', max_length=50)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='expenses.expensegroup')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='expenses.person')),
            ],
            options={'ordering': ['starts_on', 'person__name']},
        ),
        migrations.CreateModel(
            name='ExpenseSplit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amount_owed_inr', models.DecimalField(decimal_places=2, max_digits=14)),
                ('basis', models.CharField(blank=True, max_length=255)),
                ('expense', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='splits', to='expenses.expense')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expense_splits', to='expenses.person')),
            ],
            options={'unique_together': {('expense', 'person')}},
        ),
        migrations.CreateModel(
            name='ImportAnomaly',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('row_number', models.PositiveIntegerField(blank=True, null=True)),
                ('code', models.CharField(db_index=True, max_length=80)),
                ('severity', models.CharField(choices=[('INFO', 'Info'), ('WARNING', 'Warning'), ('ERROR', 'Error')], max_length=20)),
                ('message', models.TextField()),
                ('policy', models.TextField()),
                ('action_taken', models.TextField()),
                ('requires_review', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('NOT_REQUIRED', 'Not required'), ('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='NOT_REQUIRED', max_length=20)),
                ('suggested_payload', models.JSONField(blank=True, default=dict)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='anomalies', to='expenses.importbatch')),
                ('expense', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='anomalies', to='expenses.expense')),
                ('settlement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='anomalies', to='expenses.settlement')),
            ],
            options={'ordering': ['row_number', 'id']},
        ),
    ]
