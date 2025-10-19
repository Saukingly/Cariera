# filename: apps/management/commands/import_json.py

import os
import json
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

# Import all your models
from apps.models import (
    CrmContact, CrmCompany, CrmLead, JobApplication,
    EcommerceOrder, EcommerceCustomer, TicketList
)

# --- Configuration ---
# Set the path to your JSON files relative to the project's root directory.
JSON_FOLDER = 'src/json'

class Command(BaseCommand):
    help = 'Imports data from JSON files into the database based on predefined Django models.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting JSON data import process ---"))

        # A mapping of your JSON filenames to the Django model and a function to process them
        file_to_model_map = {
            'contact-list.json': (CrmContact, self.process_crm_contact),
            'company-list.json': (CrmCompany, self.process_crm_company),
            'leads-list.json': (CrmLead, self.process_crm_lead),
            'application-list.json': (JobApplication, self.process_job_application),
            'orders-list.init.json': (EcommerceOrder, self.process_ecommerce_order),
            'customer-list.json': (EcommerceCustomer, self.process_ecommerce_customer),
            'support-tickets-list.json': (TicketList, self.process_ticket_list),
        }

        for file_name, (model, processor_func) in file_to_model_map.items():
            self.stdout.write(f"\nProcessing {file_name} for model {model.__name__}...")

            # Clear existing data in the table to avoid duplicates on re-run
            model.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"  - Cleared all existing records from {model.__name__}."))

            file_path = os.path.join(settings.BASE_DIR, JSON_FOLDER, file_name)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Some files might have data nested under a key
                    records = data[0]['primary'] if file_name == 'mail-list.init.json' else data

                    count = 0
                    for record in records:
                        processor_func(record)
                        count += 1
                    self.stdout.write(self.style.SUCCESS(f"  - Successfully imported {count} records."))
            except FileNotFoundError:
                self.stdout.write(self.style.ERROR(f"  - File not found: {file_path}. Skipping."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  - An error occurred while processing {file_name}: {e}"))
        
        self.stdout.write(self.style.SUCCESS("\n--- Data import process completed successfully! ---"))

    def parse_date(self, date_str, fmt):
        """Helper to parse dates safely."""
        return datetime.strptime(date_str, fmt).date()

    def parse_datetime(self, date_str, fmt):
        """Helper to parse datetimes safely."""
        return datetime.strptime(date_str, fmt)

    # --- Processor functions for each model ---

    def process_crm_contact(self, record):
        CrmContact.objects.create(
            # The JSON stores the image path and name in a list
            profile_pic=record['name'][0] if record['name'][0] else None,
            name=record['name'][1],
            company_name=record['company_name'],
            designation=record['designation'],
            email_id=record['email_id'],
            phone=record['phone'],
            lead_score=int(record['lead_score']),
            tags=record.get('tags', [])
        )

    def process_crm_company(self, record):
        CrmCompany.objects.create(
            logo=record.get('image_src'),
            name=record['name'],
            owner_name=record['owner'],
            industry_type=record['industry_type'],
            rating=record['star_value'],
            location=record['location'],
            employee=record['employee'],
            website=record['website'],
            contact_email=record['contact_email'],
            since=int(record['since'])
        )
        
    def process_crm_lead(self, record):
        CrmLead.objects.create(
            profile_pic=record.get('image_src'),
            name=record['name'],
            company_name=record['company_name'],
            lead_score=int(record['leads_score']),
            phone=record['phone'],
            location=record['location'],
            tags=record.get('tags', []),
            create_date=self.parse_date(record['date'], '%d %b, %Y')
        )
        
    def process_job_application(self, record):
        JobApplication.objects.create(
            profile_pic=record['company'][0] if record['company'][0] else None,
            company_name=record['company'][1],
            designation=record['designation'],
            apply_date=self.parse_date(record['date'], '%d %b, %Y'),
            contact=record['contacts'],
            status=record['status'],
            type=record['type']
        )
        
    def process_ecommerce_order(self, record):
        EcommerceOrder.objects.create(
            name=record['customer_name'],
            product=record['product_name'],
            order_date=self.parse_datetime(record['date'], '%Y-%m-%dT%H:%M'),
            amount=record['amount'].replace('$', ''), # Remove currency symbol
            payment_method=record['payment'],
            status=record['status']
        )
        
    def process_ecommerce_customer(self, record):
        EcommerceCustomer.objects.create(
            name=record['customer_name'],
            email_id=record['email'],
            phone=record['phone'],
            joining_date=self.parse_date(record['date'], '%d %b, %Y'),
            status=record['status']
        )
        
    def process_ticket_list(self, record):
        TicketList.objects.create(
            title=record['tasks_name'],
            client_name=record['client_name'],
            assign_to=record['assignedto'],
            create_date=self.parse_date(record['create_date'], '%Y-%m-%d'),
            due_date=self.parse_date(record['due_date'], '%Y-%m-%d'),
            status=record['status'],
            priority=record['priority']
        )
