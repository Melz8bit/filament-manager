from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0003_filamentproduct_spool_diameter_mm_spool_sku'),
    ]

    operations = [
        # Re-create PrintSpool→PrintLog FK with ON DELETE CASCADE
        migrations.RunSQL(
            sql="""
                ALTER TABLE tracker_printspool
                    DROP CONSTRAINT IF EXISTS tracker_printspool_print_log_id_588a00be_fk_tracker_printlog_id;
                ALTER TABLE tracker_printspool
                    ADD CONSTRAINT tracker_printspool_print_log_id_fk
                    FOREIGN KEY (print_log_id) REFERENCES tracker_printlog(id) ON DELETE CASCADE;
            """,
            reverse_sql="""
                ALTER TABLE tracker_printspool DROP CONSTRAINT IF EXISTS tracker_printspool_print_log_id_fk;
                ALTER TABLE tracker_printspool
                    ADD CONSTRAINT tracker_printspool_print_log_id_588a00be_fk_tracker_printlog_id
                    FOREIGN KEY (print_log_id) REFERENCES tracker_printlog(id) DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
        # Re-create PrintSpool→Spool FK with ON DELETE SET NULL
        migrations.RunSQL(
            sql="""
                ALTER TABLE tracker_printspool
                    DROP CONSTRAINT IF EXISTS tracker_printspool_spool_id_54b84470_fk_tracker_spool_id;
                ALTER TABLE tracker_printspool
                    ADD CONSTRAINT tracker_printspool_spool_id_fk
                    FOREIGN KEY (spool_id) REFERENCES tracker_spool(id) ON DELETE SET NULL;
            """,
            reverse_sql="""
                ALTER TABLE tracker_printspool DROP CONSTRAINT IF EXISTS tracker_printspool_spool_id_fk;
                ALTER TABLE tracker_printspool
                    ADD CONSTRAINT tracker_printspool_spool_id_54b84470_fk_tracker_spool_id
                    FOREIGN KEY (spool_id) REFERENCES tracker_spool(id) DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
    ]
