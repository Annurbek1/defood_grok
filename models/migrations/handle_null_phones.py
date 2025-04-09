from django.db import migrations
from django.utils import timezone

def generate_phone_for_null_users(apps, schema_editor):
    CustomUser = apps.get_model('models', 'CustomUser')
    # Get all users with null phone numbers
    null_phone_users = CustomUser.objects.filter(phone_number__isnull=True)
    
    for user in null_phone_users:
        # Generate a unique temporary phone number based on user id and timestamp
        timestamp = int(timezone.now().timestamp())
        user.phone_number = f"temp_{user.id}_{timestamp}"
        user.save()

class Migration(migrations.Migration):
    dependencies = [
        ('models', '0002_remove_order_courier_remove_order_delivery_fee_and_more'),
    ]

    operations = [
        migrations.RunPython(generate_phone_for_null_users),
    ]
