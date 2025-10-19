from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone


# ==============================================================================
# Cariera.AI - USER PROFILE & PERSONALITY TEST MODELS
# ==============================================================================

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, default='avatars/default.jpg')
    personality_type = models.CharField(max_length=10, blank=True, null=True,
                                        help_text="User's 3-letter Holland Code (e.g., RIA, SEC)")


    # --- THE FIX IS ON THIS LINE: Increased max_length from 20 to 30 ---
    phone_number = models.CharField(max_length=30, blank=True, null=True, unique=True,
                                    help_text="Must be in E.164 format, e.g., +14155238886")

    whatsapp_subscribed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class PersonalityTestQuestion(models.Model):
    text = models.CharField(max_length=512)
    order = models.PositiveIntegerField(default=0, help_text="Order in which the question appears.")

    def __str__(self):
        return f"Q{self.order}: {self.text}"

    class Meta:
        ordering = ['order']


class PersonalityTestChoice(models.Model):
    PERSONALITY_TYPES = (
        ('R', 'Realistic'), ('I', 'Investigative'), ('A', 'Artistic'),
        ('S', 'Social'), ('E', 'Enterprising'), ('C', 'Conventional'),
    )
    question = models.ForeignKey(PersonalityTestQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    personality_code = models.CharField(max_length=1, choices=PERSONALITY_TYPES)

    def __str__(self):
        return f"{self.text} ({self.get_personality_code_display()})"


class UserPersonalityTestAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_answers')
    question = models.ForeignKey(PersonalityTestQuestion, on_delete=models.CASCADE)
    choice = models.ForeignKey(PersonalityTestChoice, on_delete=models.CASCADE)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')


# ==============================================================================
# Cariera.AI - CAREER & CHAT MODELS
# ==============================================================================

class Career(models.Model):
    name = models.CharField(max_length=255, unique=True)
    keywords = models.TextField(help_text="Comma-separated list of keywords, skills, and interests related to this career.")
    holland_code = models.CharField(max_length=3, blank=True, null=True, help_text="Primary 3-letter Holland Code for this career.")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class JourneyFolder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="journey_folders")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0, help_text="Order of the folder in the user's list.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Folder '{self.name}' for {self.user.username}"

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('user', 'name')


class CareerJourney(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="career_journeys")
    folder = models.ForeignKey(JourneyFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name="journeys")
    title = models.CharField(max_length=200, default="New Career Journey")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    class Meta:
        ordering = ['-updated_at']


class ChatMessage(models.Model):
    SENDER_CHOICES = (('user', 'User'), ('ai', 'AI'))
    journey = models.ForeignKey(CareerJourney, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=4, choices=SENDER_CHOICES, default='user')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.journey.id} ({self.sender_type}): {self.message[:50]}'

    class Meta:
        ordering = ['timestamp']


class ActionPlan(models.Model):
    """
    Connects a user to a specific career they are planning for.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="action_plans")
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name="action_plans")

    # --- ADD THIS NEW FIELD ---
    roadmap_content = models.TextField(blank=True, null=True,
                                       help_text="AI-generated step-by-step plan for this career.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Action Plan for {self.user.username} - {self.career.name}"

    class Meta:
        unique_together = ('user', 'career')


class Opportunity(models.Model):
    """
    Stores a single job, scholarship, or other opportunity found by the AI agent.
    """
    OPPORTUNITY_TYPES = (
        ('JOB', 'Job'),
        ('SCHOLARSHIP', 'Scholarship'),
        ('INTERNSHIP', 'Internship'),
        ('GRANT', 'Grant'),
        ('OTHER', 'Other'),
    )
    is_tracked = models.BooleanField(default=False, help_text="User has marked this as a high-priority opportunity.")
    action_plan = models.ForeignKey(ActionPlan, on_delete=models.CASCADE, related_name="opportunities")
    title = models.CharField(max_length=255)
    opportunity_type = models.CharField(max_length=20, choices=OPPORTUNITY_TYPES, default='JOB')
    organization_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    source_url = models.URLField(max_length=512)
    found_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_opportunity_type_display()}: {self.title}"

    class Meta:
        ordering = ['-found_at']

# ==============================================================================
# AI INTERVIEW MODELS
# ==============================================================================

class InterviewSession(models.Model):
    # ... (This model is unchanged) ...
    DIFFICULTY_CHOICES = [('simple', 'Simple'), ('standard', 'Standard'), ('hard', 'Hard')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interview_sessions')
    title = models.CharField(max_length=255, blank=True, null=True, help_text="A user-editable title for the session.")
    context = models.TextField(blank=True, null=True, help_text="The user-provided context for the interview (e.g., job role, scholarship type).")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='standard')
    duration_minutes = models.IntegerField(default=3, help_text="The user-selected duration for the interview.")
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('ongoing', 'Ongoing'), ('completed', 'Completed')], default='ongoing')
    def __str__(self):
        if self.title: return self.title
        return f"Interview for {self.user.username} on {self.start_time.strftime('%Y-%m-%d')}"
    def save(self, *args, **kwargs):
        if not self.title:
            local_start_time = timezone.localtime(self.start_time)
            self.title = f"Interview on {local_start_time.strftime('%B %d, %Y at %I:%M %p')}"
        super().save(*args, **kwargs)

class InterviewTurn(models.Model):
    # ... (This model is unchanged) ...
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='turns')
    speaker = models.CharField(max_length=10, choices=[('user', 'User'), ('ai', 'AI')])
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.speaker.title()} at {self.timestamp.strftime('%H:%M:%S')}"

# --- NEW MODEL ---
class InterviewAnalysisPoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='analysis_points')
    timestamp = models.DateTimeField(auto_now_add=True)
    # --- This is the correct final state ---
    person_detected = models.BooleanField(default=False)


class InterviewResult(models.Model):
    session = models.OneToOneField(InterviewSession, on_delete=models.CASCADE, related_name='result')
    overall_score = models.IntegerField(help_text="A score from 0 to 100.")
    confidence_score = models.IntegerField(help_text="A score from 0 to 100 reflecting vocal confidence.")
    clarity_score = models.IntegerField(help_text="A score from 0 to 100 for speech clarity.")
    
    # --- This is the correct final state ---
    camera_presence_score = models.IntegerField(default=0, help_text="A score from 0 to 100 based on camera presence.")

    feedback_summary = models.TextField(help_text="AI-generated summary and suggestions for improvement.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.session}"
