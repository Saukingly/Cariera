# apps/management/commands/send_whatsapp_digest.py

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.urls import reverse  # <-- Add this import
from django.contrib.sites.models import Site  # <-- Add this import
from twilio.rest import Client
from apps.models import UserProfile, Opportunity, InterviewSession, ActionPlan, CareerJourney

logger = logging.getLogger(__name__)


def send_digest_to_user(user, client):
    """
    Composes and sends a more useful, multi-faceted digest with direct links.
    """
    profile = user.profile
    if not (profile.whatsapp_subscribed and profile.phone_number):
        return False, f"User {user.username} is not subscribed."

    one_week_ago = datetime.now() - timedelta(days=7)

    # --- NEW: Get current site for building full URLs ---
    current_site = Site.objects.get_current()
    domain = current_site.domain
    scheme = 'https' if not settings.DEBUG else 'http'

    # Start composing message parts
    message_parts = []
    updates_found = False

    # 1. Progress Summary
    recent_interviews = InterviewSession.objects.filter(user=user, status='completed',
                                                        end_time__gte=one_week_ago).select_related('result')
    if recent_interviews.exists():
        updates_found = True
        # Ensure result exists before trying to access score
        valid_scores = [iv.result.overall_score for iv in recent_interviews if hasattr(iv, 'result')]
        if valid_scores:
            avg_score = sum(valid_scores) / len(valid_scores)
            message_parts.append(
                f"*Progress Update:*\nYou completed {len(valid_scores)} interview(s) this week with an average score of {avg_score:.0f}/100. Keep up the great work!")

    # 2. New Opportunities
    user_action_plans = ActionPlan.objects.filter(user=user).prefetch_related('career')
    user_career_ids = [plan.career.id for plan in user_action_plans]
    new_opportunities = Opportunity.objects.filter(action_plan__career__id__in=user_career_ids,
                                                   found_at__gte=one_week_ago)
    if new_opportunities.exists():
        updates_found = True
        # Build the full URL to the opportunities page
        opportunities_url = f"{scheme}://{domain}{reverse('apps:my_opportunities')}"
        message_parts.append(
            f"*New Opportunities:*\nWe found {new_opportunities.count()} new opportunities matching your career goals. See them here: {opportunities_url}")

    # 3. Task Reminders
    tracked_opportunities = Opportunity.objects.filter(action_plan__user=user, is_tracked=True)
    if tracked_opportunities.exists():
        updates_found = True
        message_parts.append(
            f"*Reminders:*\nYou are tracking {tracked_opportunities.count()} opportunities. This is a great time to work on your applications!")

    # 4. Journey Engagement with Direct Link
    latest_journey = CareerJourney.objects.filter(user=user).order_by('-updated_at').first()
    if latest_journey:
        updates_found = True
        # --- NEW: Build the full, absolute URL to the chat ---
        journey_url = f"{scheme}://{domain}{reverse('apps:career_coach.chat', args=[latest_journey.id])}"
        message_parts.append(
            f"*Career Journey:*\nReady to continue your '{latest_journey.title}' journey? Pick up where you left off here: {journey_url}")

    # Assemble and send the final message
    if updates_found:
        greeting = f"Hey {user.first_name or user.username}! Here's your weekly career digest from Cariera:\n\n"
        final_message = greeting + "\n\n".join(message_parts)
    else:
        final_message = f"Hey {user.first_name or user.username}! Just checking in from Cariera. No major updates for your career digest this week, but we're here whenever you're ready to continue your journey!"

    try:
        message = client.messages.create(
            body=final_message,
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=profile.phone_number
        )
        return True, f"Successfully sent digest to {user.username} ({profile.phone_number})"
    except Exception as e:
        return False, f"Failed to send message to {user.username}: {e}"


class Command(BaseCommand):
    help = 'Sends a weekly career digest to subscribed WhatsApp users.'

    def handle(self, *args, **options):
        self.stdout.write("Starting to send WhatsApp digests...")
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        except Exception as e:
            self.stderr.write(f"Failed to initialize Twilio client: {e}")
            return

        subscribed_profiles = UserProfile.objects.filter(whatsapp_subscribed=True).exclude(
            phone_number__isnull=True).select_related('user')
        if not subscribed_profiles:
            self.stdout.write("No subscribed users found.")
            return

        for profile in subscribed_profiles:
            success, message = send_digest_to_user(profile.user, client)
            if success:
                self.stdout.write(self.style.SUCCESS(message))
            else:
                self.stderr.write(message)

        self.stdout.write(self.style.SUCCESS("Finished sending all WhatsApp digests."))