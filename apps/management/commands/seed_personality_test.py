# apps/management/commands/seed_personality_test.py

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.models import PersonalityTestQuestion, PersonalityTestChoice

# Configure logging
logger = logging.getLogger(__name__)

# Holland Codes (RIASEC) Questions
# Sourced and adapted from various public domain RIASEC assessments.
QUESTIONS_DATA = [
    {
        "text": "I enjoy working with my hands or using tools to build or repair things.",
        "choices": [
            {"text": "Strongly Agree", "code": "R"},
            {"text": "Somewhat Agree", "code": "R"},
            {"text": "Neutral", "code": "C"},
            {"text": "Disagree", "code": "A"},
        ]
    },
    {
        "text": "I am fascinated by scientific or mathematical problems.",
        "choices": [
            {"text": "Definitely", "code": "I"},
            {"text": "Sometimes", "code": "I"},
            {"text": "Rarely", "code": "S"},
            {"text": "Not at all", "code": "E"},
        ]
    },
    {
        "text": "I express myself best through creative activities like writing, music, or art.",
        "choices": [
            {"text": "Absolutely", "code": "A"},
            {"text": "Often", "code": "A"},
            {"text": "Occasionally", "code": "S"},
            {"text": "Not really", "code": "C"},
        ]
    },
    {
        "text": "I feel fulfilled when I'm helping or teaching others.",
        "choices": [
            {"text": "That's me!", "code": "S"},
            {"text": "I enjoy it", "code": "S"},
            {"text": "It's okay", "code": "E"},
            {"text": "I prefer working alone", "code": "I"},
        ]
    },
    {
        "text": "I am a natural leader and enjoy persuading or influencing people.",
        "choices": [
            {"text": "Yes, I lead projects", "code": "E"},
            {"text": "I can take charge", "code": "E"},
            {"text": "I'd rather follow", "code": "S"},
            {"text": "I avoid the spotlight", "code": "I"},
        ]
    },
    {
        "text": "I am highly organized and enjoy working with data, records, or procedures.",
        "choices": [
            {"text": "Love it", "code": "C"},
            {"text": "I'm good at it", "code": "C"},
            {"text": "I prefer less structure", "code": "A"},
            {"text": "Not my strength", "code": "R"},
        ]
    },
    {
        "text": "Which activity sounds most appealing?",
        "choices": [
            {"text": "Building a computer", "code": "R"},
            {"text": "Conducting a lab experiment", "code": "I"},
            {"text": "Designing a website", "code": "A"},
            {"text": "Organizing a charity event", "code": "S"},
        ]
    },
    {
        "text": "In a team project, I am most likely to...",
        "choices": [
            {"text": "Manage the schedule and tasks", "code": "C"},
            {"text": "Present our findings to the group", "code": "E"},
            {"text": "Brainstorm creative ideas", "code": "A"},
            {"text": "Research the background information", "code": "I"},
        ]
    },
]


class Command(BaseCommand):
    help = 'Seeds the database with personality test questions and choices.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('[PersonalityTest] Deleting existing test data...'))
        PersonalityTestQuestion.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('[PersonalityTest] Seeding new questions...'))

        for i, q_data in enumerate(QUESTIONS_DATA):
            question = PersonalityTestQuestion.objects.create(
                text=q_data['text'],
                order=i + 1
            )
            for choice_data in q_data['choices']:
                PersonalityTestChoice.objects.create(
                    question=question,
                    text=choice_data['text'],
                    personality_code=choice_data['code']
                )
            print(f"  - Created Question {question.order}: {question.text}")

        total_questions = PersonalityTestQuestion.objects.count()
        self.stdout.write(self.style.SUCCESS(f'[PersonalityTest] Successfully seeded {total_questions} questions.'))