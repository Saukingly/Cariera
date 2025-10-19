from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Prefetch
from django.db import transaction
from django.contrib import messages
from django.conf import settings
from twilio.rest import Client
import json
import random
from collections import Counter
import logging
import re
import math
import os
import requests
import re
from .models import InterviewSession, InterviewResult

from .forms import WhatsAppSubscribeForm
from .models import UserProfile
# Import the reusable function from your management command
from .management.commands.send_whatsapp_digest import send_digest_to_user

from io import BytesIO

from .forms import WhatsAppSubscribeForm
from .models import UserProfile
# Import the reusable function from your management command
from .management.commands.send_whatsapp_digest import send_digest_to_user

# Azure SDK Imports
from django.conf import settings
# --- STABLE SDK IMPORTS ---
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
# These are the correct imports for the stable, compatible library
from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import FaceAttributeType, DetectionModel
from msrest.authentication import CognitiveServicesCredentials

# NEW SDK for Computer Vision (Emotions)
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures



# --- LOCAL APP IMPORTS ---
from .models import (
    CareerJourney, ChatMessage, Career, UserProfile,
    PersonalityTestQuestion, UserPersonalityTestAnswer, JourneyFolder, ActionPlan, Opportunity,
    InterviewSession, InterviewTurn, InterviewResult, InterviewAnalysisPoint
)
from .forms import UserUpdateForm, ProfileUpdateForm, WhatsAppSubscribeForm
from .management.commands.send_whatsapp_digest import send_digest_to_user

logger = logging.getLogger(__name__)



def remove_emojis(text):
    # --- THIS FUNCTION IS NOW FIXED ---
    # The error was using invalid \U{...} syntax. Corrected to \Uxxxxxxxx and \uxxxx.
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\u2702-\u27B0"
        u"\u24C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)


# Helper dictionary for expanding Holland Codes
HOLLAND_CODE_MAP = {
    'R': 'Realistic', 'I': 'Investigative', 'A': 'Artistic',
    'S': 'Social', 'E': 'Enterprising', 'C': 'Conventional'
}


@login_required
def career_coach_chat_view(request, journey_id):
    """
    Handles the main chat interface.

    UPDATED: Features smarter, AI-driven auto-categorization for new journeys
    and robust error handling for the chat response.
    """
    journey = get_object_or_404(CareerJourney, id=journey_id, user=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_text = data.get('message')
            if not message_text:
                return JsonResponse({'status': 'error', 'message': 'Message cannot be empty.'}, status=400)

            ChatMessage.objects.create(journey=journey, message=message_text, sender_type='user')

            # --- Fetch User Personality Profile for AI Context ---
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                personality_code = user_profile.personality_type
                if personality_code:
                    full_personality_description = ", ".join(
                        [HOLLAND_CODE_MAP.get(char, '') for char in personality_code])
                    personality_context = (
                        f"IMPORTANT: The user has a Holland Code personality profile of: "
                        f"**{personality_code} ({full_personality_description})**. "
                        f"You MUST tailor your career advice and suggestions to align with these traits."
                    )
                else:
                    personality_context = "The user has not yet completed their personality assessment."
            except UserProfile.DoesNotExist:
                personality_context = "The user has not yet completed their personality assessment."

            # --- Define the main system prompt for the AI Career Coach ---
            system_prompt = (
                "You are Cariera.ai, an expert career coach. Be encouraging, insightful, and helpful. "
                "Please format your responses using Markdown for clarity. "
                f"{personality_context}"
            )

            client = AzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
                api_key=settings.AZURE_OPENAI_AGENT_KEY,
                api_version="2024-02-01"
            )

            # --- Build Conversation History ---
            conversation_history = [{"role": "system", "content": system_prompt}]
            for msg in journey.messages.all().order_by('timestamp'):
                role = "assistant" if msg.sender_type == 'ai' else "user"
                conversation_history.append({"role": role, "content": msg.message})

            # --- Get the Main Chat Response ---
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
                messages=conversation_history,
                temperature=0.7,
                max_tokens=800,
            )
            ai_response_text = remove_emojis(response.choices[0].message.content)
            ai_message_obj = ChatMessage.objects.create(journey=journey, message=ai_response_text, sender_type='ai')
            journey.save()

            # --- AI Naming and Smart Sorting Logic ---
            # This logic runs only once for a new journey to give it a name and folder.
            if journey.title == "New Career Journey" and journey.messages.count() <= 2:
                try:
                    # Step 1: Get a list of the user's existing folders to provide as context.
                    folder_names = list(JourneyFolder.objects.filter(user=request.user).values_list('name', flat=True))
                    folder_list_str = ", ".join(folder_names) if folder_names else "None"

                    # Step 2: Create a specific, structured prompt for the AI.
                    title_prompt_system = (
                        "You are a helpful assistant. Based on the conversation, do two things: "
                        "1. Generate a concise 4-5 word title for the journey. "
                        f"2. Analyze the title and conversation content. Choose the MOST semantically relevant folder for this journey from this list: [{folder_list_str}]. If none fit, you MUST return 'None'. "
                        "Respond ONLY in the format: Title: [Your Title] | Folder: [Chosen Folder Name or None]"
                    )
                    title_prompt_user = f"Conversation:\nUser: {message_text}\nAI: {ai_response_text}"

                    # Step 3: Make a second, quick call to the AI for this specific task.
                    title_response = client.chat.completions.create(
                        model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
                        messages=[
                            {"role": "system", "content": title_prompt_system},
                            {"role": "user", "content": title_prompt_user}
                        ],
                        temperature=0.5, max_tokens=60
                    )

                    raw_response = title_response.choices[0].message.content.strip()
                    logger.info(f"[AI Naming] Raw response for naming/sorting: '{raw_response}'")

                    # Step 4: Parse the AI's structured response robustly.
                    new_title = journey.title
                    chosen_folder_name = 'None'
                    if '|' in raw_response and 'Title:' in raw_response and 'Folder:' in raw_response:
                        parts = raw_response.split('|')
                        new_title_part = parts[0].replace('Title:', '').strip()
                        chosen_folder_part = parts[1].replace('Folder:', '').strip()

                        if new_title_part: new_title = new_title_part
                        if chosen_folder_part: chosen_folder_name = chosen_folder_part

                    journey.title = new_title

                    # Step 5: Assign to folder if a valid one was chosen.
                    if chosen_folder_name.lower() != 'none':
                        try:
                            target_folder = JourneyFolder.objects.get(user=request.user,
                                                                      name__iexact=chosen_folder_name)
                            journey.folder = target_folder
                            request.session['newly_auto_added_journey_id'] = str(journey.id)
                            logger.info(f"[AutoCategorize] Moved '{new_title}' to folder '{target_folder.name}'.")
                        except JourneyFolder.DoesNotExist:
                            logger.warning(
                                f"[AutoCategorize] AI chose folder '{chosen_folder_name}', but it wasn't found.")

                    journey.save()

                except Exception as e:
                    logger.error(f"[AINaming/AutoCategorize] Process failed: {e}", exc_info=True)

            # Return a success response with all necessary data for the UI
            return JsonResponse({
                'status': 'success',
                'user_message': message_text,
                'ai_message': ai_response_text,
                'ai_timestamp': ai_message_obj.timestamp.strftime('%I:%M %p').lstrip('0')
            })

        except Exception as e:
            logger.error(f"[ChatView] Main error: {e}", exc_info=True)
            # Return a structured error so the JavaScript doesn't break
            return JsonResponse(
                {'status': 'error', 'message': 'Sorry, an error occurred with the AI. Please try again.'}, status=500)

    context = {"active_journey": journey, "chat_messages": journey.messages.all()}
    return render(request, "career_coach/chat.html", context)



@login_required
def journeys_list_view(request):
    search_query = request.GET.get('q', '').strip()
    sort_order = request.GET.get('sort', 'newest')

    journeys_qs = CareerJourney.objects.filter(user=request.user)

    if search_query:
        journeys_qs = journeys_qs.filter(
            Q(title__icontains=search_query) |
            Q(messages__message__icontains=search_query) |
            Q(folder__name__icontains=search_query)
        ).distinct()

    sort_param_journeys = '-updated_at' if sort_order == 'newest' else 'updated_at'

    # UPDATED: We now sort folders by the `order` field.
    folders = JourneyFolder.objects.filter(user=request.user).order_by('order').prefetch_related(
        Prefetch('journeys', queryset=journeys_qs.order_by(sort_param_journeys))
    )

    unfoldered_journeys = journeys_qs.filter(folder__isnull=True).order_by(sort_param_journeys)

    newly_added_id = request.session.pop('newly_auto_added_journey_id', None)

    context = {
        'folders': folders,
        'unfoldered_journeys': unfoldered_journeys,
        'search_query': search_query,
        'current_sort': sort_order,
        'newly_auto_added_journey_id': newly_added_id,
    }
    return render(request, 'journeys/list.html', context)


# --- NEW VIEW TO HANDLE FOLDER REORDERING ---
@csrf_exempt
@require_POST
@login_required
def reorder_folders_view(request):
    try:
        data = json.loads(request.body)
        ordered_folder_ids = data.get('folder_ids', [])

        # Update the order of each folder in the database
        with transaction.atomic():
            for index, folder_id in enumerate(ordered_folder_ids):
                JourneyFolder.objects.filter(id=folder_id, user=request.user).update(order=index)

        logger.info(f"[ReorderFolders] User '{request.user.username}' updated folder order.")
        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.error(f"[ReorderFolders] Error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def explore_careers_view(request):
    user_journeys = CareerJourney.objects.filter(user=request.user)
    all_messages = ChatMessage.objects.filter(journey__in=user_journeys).order_by('timestamp')

    if not all_messages.exists():
        context = {'careers': [], 'has_messages': False}
        return render(request, "explore/constellation.html", context)

    documents = []
    current_document = ""
    for message in all_messages:
        msg_text = message.message + " "
        if len(current_document) + len(msg_text) > 5120:
            documents.append(current_document)
            current_document = msg_text
        else:
            current_document += msg_text
    if current_document:
        documents.append(current_document)

    if len(documents) > 10:
        documents = documents[-10:]

    extracted_phrases = set()
    try:
        if not documents:
            raise ValueError("No documents to analyze after batching.")
        language_client = TextAnalyticsClient(
            endpoint=settings.AZURE_LANGUAGE_ENDPOINT, credential=AzureKeyCredential(settings.AZURE_LANGUAGE_KEY)
        )
        response = language_client.extract_key_phrases(documents=documents)
        for doc in response:
            if not doc.is_error:
                for phrase in doc.key_phrases:
                    extracted_phrases.add(phrase.lower())
    except Exception as e:
        context = {'careers': [], 'has_messages': True, 'error': str(e)}
        return render(request, "explore/constellation.html", context)

    if not extracted_phrases:
        context = {'careers': [], 'has_messages': True}
        return render(request, "explore/constellation.html", context)

    all_careers = Career.objects.all()
    matched_careers = []
    for career in all_careers:
        career_keywords = set(kw.strip().lower() for kw in career.keywords.split(','))
        if not career_keywords: continue
        matching_words = extracted_phrases.intersection(career_keywords)
        if matching_words:
            score = (len(matching_words) / len(career_keywords)) * 100 * (1 + (len(matching_words) / 10))
            final_score = min(int(score), 100)
            if final_score > 15:
                matched_careers.append({
                    'id': career.id,
                    'name': career.name,
                    'match': final_score,
                    'matched_keywords': list(matching_words)
                })

    top_careers = sorted(matched_careers, key=lambda x: x['match'], reverse=True)[:7]

    positions = [
        {'top': 15, 'left': 20}, {'top': 25, 'left': 78}, {'top': 70, 'left': 85},
        {'top': 75, 'left': 15}, {'top': 10, 'left': 60}, {'top': 55, 'left': 5},
        {'top': 80, 'left': 50}
    ]
    random.shuffle(positions)

    for i, career_data in enumerate(top_careers):
        pos = positions[i % len(positions)]
        career_data['pos'] = pos

        dx = pos['left'] - 50
        dy = pos['top'] - 50

        distance = math.sqrt(dx ** 2 + dy ** 2)
        career_data['distance'] = distance

        angle = math.atan2(dy, dx) * (180 / math.pi)
        career_data['angle'] = angle

        career_data['animation_duration'] = random.uniform(30, 60)
        career_data['animation_delay'] = random.uniform(-60, 0)

    context = {
        'careers': top_careers,
        'has_messages': True,
        'extracted_phrases': sorted(list(extracted_phrases))
    }
    return render(request, "explore/constellation.html", context)


@csrf_exempt
@require_POST
@login_required
def move_journey_drag_drop(request):
    try:
        data = json.loads(request.body)
        journey_id = data.get('journey_id')
        folder_id = data.get('folder_id')
        journey = get_object_or_404(CareerJourney, id=journey_id, user=request.user)
        if folder_id:
            folder = get_object_or_404(JourneyFolder, id=folder_id, user=request.user)
            journey.folder = folder
            logger.info(
                f"[DragDrop] User '{request.user.username}' moved journey '{journey.title}' to folder '{folder.name}'.")
        else:
            journey.folder = None
            logger.info(f"[DragDrop] User '{request.user.username}' moved journey '{journey.title}' to Uncategorized.")
        journey.save()
        return JsonResponse({'status': 'success', 'message': 'Journey moved.'})
    except Exception as e:
        logger.error(f"[DragDrop] Error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def create_journey_view(request):
    new_journey = CareerJourney.objects.create(user=request.user)
    UserProfile.objects.get_or_create(user=request.user)
    return redirect('apps:career_coach.chat', journey_id=new_journey.id)


@login_required
@require_POST
def rename_journey_view(request, journey_id):
    journey = get_object_or_404(CareerJourney, id=journey_id, user=request.user)
    new_title = request.POST.get('new_title', '').strip()
    if new_title:
        journey.title = new_title
        journey.save()
    return redirect('apps:journeys.list')


@login_required
@require_POST
def delete_journey_view(request, journey_id):
    journey = get_object_or_404(CareerJourney, id=journey_id, user=request.user)
    journey.delete()
    return redirect('apps:journeys.list')


@login_required
@require_POST
def create_folder_view(request):
    folder_name = request.POST.get('folder_name', '').strip()
    if folder_name and not JourneyFolder.objects.filter(user=request.user, name=folder_name).exists():
        JourneyFolder.objects.create(user=request.user, name=folder_name)
    return redirect('apps:journeys.list')


@login_required
@require_POST
def rename_folder_view(request, folder_id):
    folder = get_object_or_404(JourneyFolder, id=folder_id, user=request.user)
    new_name = request.POST.get('folder_name', '').strip()
    if new_name and not JourneyFolder.objects.filter(user=request.user, name=new_name).exists():
        folder.name = new_name
        folder.save()
    return redirect('apps:journeys.list')


@login_required
@require_POST
@transaction.atomic
def delete_folder_view(request, folder_id):
    folder = get_object_or_404(JourneyFolder, id=folder_id, user=request.user)
    folder.journeys.all().update(folder=None)
    folder.delete()
    return redirect('apps:journeys.list')


@login_required
@require_POST
def move_journey_to_folder(request):
    journey_id, folder_id = request.POST.get('journey_id'), request.POST.get('folder_id')
    journey = get_object_or_404(CareerJourney, id=journey_id, user=request.user)
    journey.folder = get_object_or_404(JourneyFolder, id=folder_id, user=request.user) if folder_id != "None" else None
    journey.save()
    return redirect('apps:journeys.list')


@login_required
def get_personality_test_question(request):
    answered_questions_ids = UserPersonalityTestAnswer.objects.filter(user=request.user).values_list('question_id',
                                                                                                     flat=True)
    next_question = PersonalityTestQuestion.objects.exclude(id__in=answered_questions_ids).order_by('order').first()
    total_questions = PersonalityTestQuestion.objects.count()
    questions_answered = len(answered_questions_ids)
    if next_question:
        choices = [{'id': choice.id, 'text': choice.text} for choice in next_question.choices.all()]
        data = {
            'question_id': next_question.id,
            'question_text': next_question.text,
            'choices': choices,
            'progress': {'current': questions_answered + 1, 'total': total_questions}
        }
        return JsonResponse(data)
    else:
        return JsonResponse({'status': 'complete', 'message': 'You have completed the assessment!',
                             'progress': {'current': total_questions, 'total': total_questions}})


@login_required
@require_POST
def submit_personality_test_answer(request):
    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        choice_id = data.get('choice_id')
        UserPersonalityTestAnswer.objects.update_or_create(user=request.user, question_id=question_id,
                                                           defaults={'choice_id': choice_id})
        logger.info(f"[PersonalityTest] User {request.user.id} answered question {question_id} with choice {choice_id}")
        return JsonResponse({'status': 'success', 'message': 'Answer saved.'})
    except Exception as e:
        logger.error(f"[PersonalityTest] Error submitting answer for user {request.user.id}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Invalid data provided.'}, status=400)


@login_required
def calculate_personality_test_result(request):
    user_answers = UserPersonalityTestAnswer.objects.filter(user=request.user).select_related('choice')
    if not user_answers.exists():
        return JsonResponse({'status': 'error', 'message': 'No answers found.'}, status=400)
    scores = Counter(answer.choice.personality_code for answer in user_answers)
    top_three = scores.most_common(3)
    result_code = "".join([item[0] for item in top_three])
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.personality_type = result_code
    profile.save()
    logger.info(f"[PersonalityTest] Calculated result for user {request.user.id}: {result_code}")
    descriptions = {'R': 'Realistic (Doers)', 'I': 'Investigative (Thinkers)', 'A': 'Artistic (Creators)',
                    'S': 'Social (Helpers)', 'E': 'Enterprising (Persuaders)', 'C': 'Conventional (Organizers)'}
    primary_type_code = top_three[0][0]
    primary_type_name = descriptions.get(primary_type_code, "Unknown")
    return JsonResponse({'status': 'success', 'result_code': result_code, 'primary_type': primary_type_name,
                         'full_scores': dict(scores)})


@login_required
@require_POST
def reset_personality_test(request):
    try:
        answers_deleted, _ = UserPersonalityTestAnswer.objects.filter(user=request.user).delete()
        try:
            profile = request.user.profile
            profile.personality_type = None
            profile.save()
        except UserProfile.DoesNotExist:
            pass
        logger.info(
            f'[Personality Test] User {request.user.username} reset their test. {answers_deleted} answers were deleted.')
        return JsonResponse({'status': 'success', 'message': 'Your previous answers have been cleared.'})
    except Exception as e:
        logger.error(f'[Personality Test] Error resetting test for user {request.user.username}: {e}', exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Could not reset your assessment. Please try again.'},
                            status=500)


@login_required
def get_speech_token_view(request):
    """
    Generates a short-lived authorization token for the Azure Speech SDK.
    """
    if not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION:
        logger.error("[SpeechToken] Azure Speech Key or Region not configured in settings.")
        return JsonResponse({'status': 'error', 'message': 'Speech service not configured.'}, status=500)

    try:
        token_url = f"https://{settings.AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        headers = {
            'Ocp-Apim-Subscription-Key': settings.AZURE_SPEECH_KEY,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(token_url, headers=headers)
        response.raise_for_status()

        token = response.text
        logger.info(f"[SpeechToken] Successfully generated speech token for user '{request.user.username}'.")
        return JsonResponse({'status': 'ok', 'token': token, 'region': settings.AZURE_SPEECH_REGION})

    except requests.exceptions.RequestException as e:
        logger.error(f"[SpeechToken] Error requesting Azure token: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Could not communicate with speech service.'}, status=502)
    except Exception as e:
        logger.error(f"[SpeechToken] Unexpected error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)


@login_required
def my_opportunities_view(request):
    """
    Displays a central hub of all saved opportunities, with search and filtering.
    """
    search_query = request.GET.get('q', '').strip()

    action_plans_with_ops = ActionPlan.objects.filter(
        user=request.user,
        opportunities__isnull=False
    ).prefetch_related('opportunities').distinct()

    if search_query:
        # Filter the opportunities within each action plan
        filtered_plans = []
        for plan in action_plans_with_ops:
            # This logic is a bit complex in pure Django, so we filter in Python
            # For larger scale, this would be optimized.
            plan.filtered_opportunities = plan.opportunities.filter(
                Q(title__icontains=search_query) |
                Q(organization_name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
            if plan.filtered_opportunities.exists():
                filtered_plans.append(plan)
        action_plans_with_ops = filtered_plans

    context = {
        'action_plans_with_opportunities': action_plans_with_ops,
        'search_query': search_query,
    }
    return render(request, "opportunities/hub.html", context)


@login_required
def my_action_plans_view(request):
    return render(request, "plans/list.html", {})


@login_required
def profile_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('apps:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=user_profile)
    context = {'user_form': user_form, 'profile_form': profile_form}
    return render(request, "account/profile.html", context)


# ==============================================================================
# Cariera.AI - ACTION PLAN VIEWS (DEFINITIVE VERSION)
# ==============================================================================

@login_required
def action_plan_list_view(request):
    """
    Displays all of the user's created action plans and a form to create a new one.
    Also handles search functionality.
    """
    search_query = request.GET.get('q', '').strip()
    action_plans = ActionPlan.objects.filter(user=request.user).select_related('career')

    if search_query:
        action_plans = action_plans.filter(career__name__icontains=search_query)
        logger.info(f"User '{request.user.username}' searched for action plan: '{search_query}'.")

    context = {
        'action_plans': action_plans,
        'search_query': search_query,
    }
    return render(request, "plans/list.html", context)


@login_required
@require_POST
def create_action_plan_view(request):
    """
    Creates a new Action Plan based on user input and redirects to its detail page.
    """
    career_title = request.POST.get('career_title', '').strip()
    if not career_title:
        return redirect('apps:my_action_plans')

    career, created = Career.objects.get_or_create(
        name__iexact=career_title,
        defaults={'name': career_title}
    )
    if created:
        logger.info(f"New career '{career_title}' created for an action plan.")

    action_plan, created = ActionPlan.objects.get_or_create(
        user=request.user,
        career=career
    )

    # Redirect to the Opportunities Hub by default
    return redirect('apps:action_plan.opportunities', career_id=action_plan.career.id)


@login_required
@require_POST
def delete_action_plan_view(request, plan_id):
    """ Deletes an action plan. """
    plan = get_object_or_404(ActionPlan, id=plan_id, user=request.user)
    plan.delete()
    return redirect('apps:my_action_plans')


@login_required
def action_plan_opportunities_view(request, career_id):
    """
    Displays the job-board like UI for finding opportunities for a specific career.
    """
    career = get_object_or_404(Career, id=career_id)
    action_plan, created = ActionPlan.objects.get_or_create(user=request.user, career=career)
    opportunities = action_plan.opportunities.all()
    context = {'action_plan': action_plan, 'opportunities': opportunities}
    return render(request, "plans/action_plan_opportunities.html", context)


@login_required
def action_plan_roadmap_view(request, career_id):
    """
    Displays the AI-generated roadmap for a specific career action plan.
    """
    career = get_object_or_404(Career, id=career_id)
    action_plan, created = ActionPlan.objects.get_or_create(user=request.user, career=career)
    context = {'action_plan': action_plan}
    return render(request, "plans/action_plan_roadmap.html", context)


# ... (all other views and imports are the same) ...

@csrf_exempt
@require_POST
@login_required
def generate_roadmap_view(request):
    """
    API endpoint that uses the AI to generate a structured, JSON-based roadmap for a career.
    """
    data = json.loads(request.body)
    plan_id = data.get('plan_id')
    customization = data.get('customization', {})

    action_plan = get_object_or_404(ActionPlan, id=plan_id, user=request.user)

    logger.info(f"Generating structured roadmap for: {action_plan.career.name}")

    try:
        client = AzureOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_AGENT_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_AGENT_KEY"),
            api_version="2024-02-01"
        )

        # Build customized prompt based on user input
        system_prompt = (
            "You are a helpful career planning assistant. The user wants a step-by-step roadmap for a career. "
            "You MUST respond with ONLY a valid JSON object. Do not include any text or markdown before or after the JSON. "
            "The JSON object should have a single key 'roadmap' which is an array of steps. "
            "Each step object in the array should have three keys: 'title' (a short title like 'High School' or 'Residency'), "
            "'duration' (a string like '4 Years' or '3-7 Years'), and 'description' (a detailed markdown-formatted string explaining the step). "
            "Create between 4 and 8 logical steps for the roadmap. "
            "If special needs or accommodations are mentioned, include specific resources, alternative pathways, and accessibility considerations in your recommendations."
        )

        # Build user prompt with customizations
        user_prompt = f"Generate a JSON roadmap for becoming a {action_plan.career.name}."

        # Add customization details to the prompt
        customization_details = []

        starting_age = customization.get('starting_age', '').strip()
        if starting_age:
            customization_details.append(f"Starting at age {starting_age}")

        country = customization.get('country', '').strip()
        if country:
            customization_details.append(f"Country/Location: {country}")

        special_needs = customization.get('special_needs', '').strip()
        if special_needs:
            customization_details.append(f"Special needs and accommodations: {special_needs}")

        if customization_details:
            user_prompt += f"\n\nPlease customize this roadmap considering the following:\n" + "\n".join(
                f"- {detail}" for detail in customization_details)
            user_prompt += "\n\nEnsure the roadmap accounts for these specific requirements and includes relevant resources, alternative pathways, and accommodations where applicable."

        response = client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_AGENT_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,  # Slightly higher for more creative accommodations
            response_format={"type": "json_object"}
        )

        roadmap_content_json = response.choices[0].message.content
        roadmap_data = json.loads(roadmap_content_json)

        # Convert JSON to HTML using your existing CSS classes
        html_content = convert_roadmap_to_html(roadmap_data, customization)

        # Save the HTML to the database
        action_plan.roadmap_content = html_content
        action_plan.save()

        return JsonResponse({
            'status': 'success',
            'roadmap_content': html_content
        })

    except Exception as e:
        logger.error(f"[GenerateRoadmap] API call failed: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def convert_roadmap_to_html(roadmap_data, customization=None):
    """Convert JSON roadmap data to HTML using the template's CSS classes"""
    html_parts = ['<div class="roadmap-wrapper">']
    html_parts.append('<div class="roadmap-line"></div>')

    # Add customization header if any customizations were applied
    if customization and any(v.strip() for v in customization.values()):
        html_parts.append('<div class="alert alert-info mb-4">')
        html_parts.append('<h6><i class="ri-information-line me-2"></i>Personalized Roadmap</h6>')
        html_parts.append('<small>')

        details = []
        if customization.get('starting_age', '').strip():
            details.append(f"Starting at age {customization['starting_age']}")
        if customization.get('country', '').strip():
            details.append(f"For {customization['country']}")
        if customization.get('special_needs', '').strip():
            details.append("With accessibility considerations")

        if details:
            html_parts.append('This roadmap has been customized: ' + ' • '.join(details))

        html_parts.append('</small></div>')

    steps = roadmap_data.get('roadmap', [])
    for i, step in enumerate(steps, 1):
        html_parts.append(f'<div class="roadmap-item">')
        html_parts.append(f'<div class="roadmap-icon">{i}</div>')
        html_parts.append('<div class="roadmap-content">')
        html_parts.append(f'<div class="roadmap-duration">{step.get("duration", "")}</div>')
        html_parts.append(f'<h5 class="roadmap-title">{step.get("title", "")}</h5>')
        html_parts.append(f'<div class="text-muted">{step.get("description", "")}</div>')
        html_parts.append('</div></div>')

    html_parts.append('</div>')
    return ''.join(html_parts)


# ... (all other imports and views remain the same) ...

# ... (all other views and imports are the same) ...



def strip_emojis(text):
    """Remove emoji characters from text"""
    if not text:
        return text
    # Remove emoji and other 4-byte Unicode characters
    emoji_pattern = re.compile("["
                              u"\\U0001F600-\\U0001F64F"  # emoticons
                              u"\\U0001F300-\\U0001F5FF"  # symbols & pictographs
                              u"\\U0001F680-\\U0001F6FF"  # transport & map symbols
                              u"\\U0001F1E0-\\U0001F1FF"  # flags (iOS)
                              u"\\U00002702-\\U000027B0"
                              u"\\U000024C2-\\U0001F251"
                              "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)



@csrf_exempt
@require_POST
@login_required
def find_opportunities_view(request):
    """
    API endpoint that uses a direct, single-pass AI call to find and filter opportunities.
    """
    data = json.loads(request.body)
    career_id = data.get('career_id')
    career = get_object_or_404(Career, id=career_id)
    action_plan = get_object_or_404(ActionPlan, career=career, user=request.user)
    logger.info(f"[FindOpportunities] Request for career: {career.name}")

    try:
        # --- Step 1: Call our Azure Function to get RAW data ---
        function_url = os.environ.get("AZURE_FUNCTION_ENDPOINT_OPPORTUNITIES")
        function_args = {"career_title": career.name, "location": "Remote"}

        print(f"Step 1: Calling Azure Function to gather raw data with args: {function_args}")
        api_response = requests.post(function_url, json=function_args)
        api_response.raise_for_status()
        raw_data = api_response.json()
        raw_opportunities = raw_data.get("opportunities", [])

        # --- ADDED FOR DEBUGGING: Print the raw data to the console ---
        print("\\n" + "=" * 30 + " RAW DATA FROM AZURE FUNCTION " + "=" * 30)
        print(json.dumps(raw_data, indent=2))
        print("=" * 80 + "\\n")

        if not raw_opportunities:
            print("Azure Function returned no opportunities. Ending process.")
            return JsonResponse({'status': 'success', 'opportunities': []})

        # --- Step 2: Ask the AI to filter the raw data in a SINGLE call ---
        print(f"Step 2: Asking AI to filter and select the best results from {len(raw_opportunities)} opportunities...")
        client = AzureOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_AGENT_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_AGENT_KEY"),
            api_version="2024-05-01-preview"
        )

        # FIXED: More lenient system prompt
        system_prompt = (
            "You are an expert career assistant and data filter. Your task is to analyze a JSON list of potential career opportunities "
            "and select the most relevant ones for the user. Be inclusive rather than exclusive - if an opportunity could be "
            "reasonably relevant to someone interested in the career, include it. "
            "Your final response MUST be ONLY a valid JSON object with a single key 'opportunities' which is an array of the selected opportunity objects. "
            "Do not include any other text, greetings, or explanations in your response."
        )

        # FIXED: More flexible and encouraging user prompt
        user_prompt = (
            f"From the following JSON list of opportunities, please select up to 10 that could be relevant to a person interested in becoming a '{career.name}'. "
            f"IMPORTANT GUIDELINES:\\n"
            f"- If the career title is 'student', include ALL items with opportunity_type 'SCHOLARSHIP' regardless of field\\n"
            f"- For technical careers like 'software engineer', include scholarships for computer science, engineering, or STEM fields\\n"  
            f"- Include opportunities that might help someone transition into this career\\n"
            f"- Include general scholarships that could benefit someone pursuing this career\\n"
            f"- Be inclusive - when in doubt, include the opportunity rather than exclude it\\n"
            f"- If you're unsure whether something is relevant, include it\\n\\n"
            f"Career being searched for: '{career.name}'\\n\\n"
            f"Raw opportunities data:\\n{json.dumps(raw_opportunities, indent=2)}"
        )

        final_response = client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_AGENT_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        filtered_content = json.loads(final_response.choices[0].message.content)
        found_opportunities = filtered_content.get("opportunities", [])

        # --- DEBUGGING: Print what the AI returned ---
        print(f"\\n" + "=" * 30 + " AI FILTERED RESULTS " + "=" * 30)
        print(f"AI received {len(raw_opportunities)} opportunities")
        print(f"AI returned {len(found_opportunities)} opportunities")
        if found_opportunities:
            print("Sample filtered opportunity:")
            print(json.dumps(found_opportunities[0], indent=2))
        else:
            print("AI returned no opportunities!")
            print("AI response:")
            print(final_response.choices[0].message.content)
        print("=" * 80 + "\\n")

        # --- Step 3: Save and return the FINAL, filtered data ---
        print(f"Step 3: AI has filtered the list down to {len(found_opportunities)} opportunities. Saving to database.")
        action_plan.opportunities.all().delete()
        new_ops = []
        for op_data in found_opportunities:
            if isinstance(op_data, dict) and 'title' in op_data and 'source_url' in op_data:
                op = Opportunity.objects.create(
                    action_plan=action_plan,
                    title=strip_emojis(op_data.get('title')),
                    opportunity_type=op_data.get('opportunity_type', 'OTHER'),
                    organization_name=strip_emojis(op_data.get('organization_name')),
                    location=strip_emojis(op_data.get('location')),
                    description=strip_emojis(op_data.get('description')),
                    source_url=op_data.get('source_url')
                )
                new_ops.append({
                    'id': op.id, 'title': op.title, 'type': op.get_opportunity_type_display(),
                    'organization': op.organization_name, 'location': op.location,
                    'description': op.description, 'url': op.source_url
                })

        return JsonResponse({'status': 'success', 'opportunities': new_ops})

    except Exception as e:
        logger.error(f"[FindOpportunities] Execution failed: {e}", exc_info=True)
        print(f"[FindOpportunities] Execution failed: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



@csrf_exempt
@require_POST
@login_required
def toggle_opportunity_tracking(request, op_id):
    """ Toggles the is_tracked status of an opportunity. """
    opportunity = get_object_or_404(Opportunity, id=op_id, action_plan__user=request.user)
    opportunity.is_tracked = not opportunity.is_tracked
    opportunity.save()
    logger.info(f"Toggled tracking for opportunity {op_id} to {opportunity.is_tracked}")
    return JsonResponse({'status': 'success', 'is_tracked': opportunity.is_tracked})

# ... (other views)

@login_required
@require_POST
def rename_action_plan_view(request, plan_id):
    """ Renames an action plan. """
    plan = get_object_or_404(ActionPlan, id=plan_id, user=request.user)
    new_title = request.POST.get('career_title', '').strip()
    if new_title:
        # Find or create a career with the new title
        new_career, _ = Career.objects.get_or_create(name__iexact=new_title, defaults={'name': new_title})
        # Check if a plan for that career already exists
        if ActionPlan.objects.filter(user=request.user, career=new_career).exists():
            messages.warning(request, f"You already have an action plan for '{new_title}'.")
        else:
            plan.career = new_career
            plan.save()
            messages.success(request, 'Action plan renamed successfully.')
    return redirect('apps:my_action_plans')


# ==============================================================================
# AI INTERVIEW VIEWS
# ==============================================================================

@login_required
def interview_setup_view(request):
    """
    Page where users can configure, start, search, and see history.
    """
    # --- Search Functionality ---
    search_query = request.GET.get('q', '').strip()
    past_interviews = InterviewSession.objects.filter(user=request.user, status='completed').order_by('-start_time')

    if search_query:
        past_interviews = past_interviews.filter(
            Q(title__icontains=search_query) |
            Q(context__icontains=search_query)
        )
        logger.info(f"User '{request.user.username}' searched for interviews: '{search_query}'.")

    if request.method == 'POST':
        duration = request.POST.get('duration', '3')
        context_text = request.POST.get('context', '').strip()
        difficulty_level = request.POST.get('difficulty', 'standard')

        session = InterviewSession.objects.create(
            user=request.user,
            duration_minutes=int(duration),
            context=context_text,
            difficulty=difficulty_level
        )

        # --- Smart Title Generation ---
        if context_text:
            # Create a title from the first 50 chars of the context
            session.title = f"Interview Practice: {context_text[:50]}..."
        # If no context, the model's default title with the date will be used
        session.save()

        logger.info(
            f"[Interview] New session created for user {request.user.username} with ID {session.id} and title: '{session.title}'")
        return redirect('apps:interview.session', session_id=session.id)

    context = {
        'past_interviews': past_interviews,
        'search_query': search_query,  # Pass query back to template
    }
    return render(request, 'interviews/interview_setup.html', context)

@login_required
@require_POST
def interview_delete_view(request, session_id):
    """
    Deletes an interview session.
    """
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    logger.info(f"User '{request.user.username}' is deleting interview session '{session.title}' ({session.id})")
    session.delete()
    return redirect('apps:interview.setup')


@login_required
def interview_progress_view(request):
    """
    Displays charts and AI-powered insights about interview performance.
    """
    completed_interviews = InterviewSession.objects.filter(
        user=request.user,
        status='completed',
        result__isnull=False
    ).order_by('start_time').select_related('result')

    # Data for the line chart (historical trends)
    line_chart_data = {
        'labels': [iv.start_time.strftime('%b %d, %Y') for iv in completed_interviews],
        'overall': [iv.result.overall_score for iv in completed_interviews],
        'confidence': [iv.result.confidence_score for iv in completed_interviews],
        'clarity': [iv.result.clarity_score for iv in completed_interviews],
        'camera_presence': [iv.result.camera_presence_score for iv in completed_interviews],
    }

    # Data for the radar chart (latest interview snapshot)
    latest_interview = completed_interviews.last()
    radar_chart_data = None
    if latest_interview:
        radar_chart_data = {
            'overall': latest_interview.result.overall_score,
            'confidence': latest_interview.result.confidence_score,
            'clarity': latest_interview.result.clarity_score,
            'camera_presence': latest_interview.result.camera_presence_score,
        }

    # --- AI-Powered Motivational Insights ---
    ai_insights = ""
    if len(line_chart_data['overall']) > 1:
        try:
            client = AzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
                api_key=settings.AZURE_OPENAI_AGENT_KEY,
                api_version="2024-02-01"
            )
            score_history = ", ".join(map(str, line_chart_data['overall']))
            system_prompt = (
                "You are a motivational career coach named Cariera. Your role is to analyze a user's mock interview score history and provide a short (2-3 sentences), encouraging summary. "
                "Do not use emojis. Focus on trends like improvement, consistency, or bouncing back from a lower score. Be positive and forward-looking."
            )
            user_prompt = f"My overall interview scores over the last few sessions have been: [{score_history}]. What's your take on my progress?"
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7, max_tokens=100
            )
            ai_insights = response.choices[0].message.content.strip()
            logger.info(f"Generated AI insights for user {request.user.username}: {ai_insights}")
        except Exception as e:
            logger.error(f"Failed to get AI insights for user {request.user.username}: {e}")
            ai_insights = "Keep practicing to see your trends over time!"

    context = {
        'total_interviews': completed_interviews.count(),
        'latest_interview': latest_interview,
        'line_chart_data_json': json.dumps(line_chart_data),
        'radar_chart_data_json': json.dumps(radar_chart_data),
        'ai_insights': ai_insights,
    }
    return render(request, 'interviews/interview_progress.html', context)

@login_required
def interview_retry_view(request, session_id):
    """
    Creates a new interview session by duplicating the settings of a previous one.
    """
    original_session = get_object_or_404(InterviewSession, id=session_id, user=request.user)

    # Create a new session with the same settings
    new_session = InterviewSession.objects.create(
        user=request.user,
        context=original_session.context,
        difficulty=original_session.difficulty,
        duration_minutes=original_session.duration_minutes
    )

    # Smartly update the title for the new session
    new_session.title = f"Retry of: {original_session.title}"
    new_session.save()

    logger.info(
        f"User '{request.user.username}' is retrying interview {original_session.id}. New session created: {new_session.id}")

    # Redirect directly to the new interview session
    return redirect('apps:interview.session', session_id=new_session.id)


@login_required
def interview_session_view(request, session_id):
    """
    The main view that hosts the live interview session.
    """
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)

    # Your Azure Speech key and region are needed by the frontend JavaScript
    context = {
        'session': session,
        'azure_speech_key': settings.AZURE_SPEECH_KEY,
        'azure_speech_region': settings.AZURE_SPEECH_REGION,
    }
    return render(request, 'interviews/interview_session.html', context)


@login_required
def interview_result_view(request, session_id):
    """
    Displays the feedback and results after an interview is completed.
    Includes logic to poll for results if they are not ready yet.
    """
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    result = None
    results_ready = False
    
    # --- THIS IS THE CORRECTED PYTHON SYNTAX ---
    try:
        result = session.result
        # The result object exists. Now check if the analysis is complete.
        # We consider it complete if the session is marked 'completed'.
        if session.status == 'completed':
             results_ready = True

    except InterviewResult.DoesNotExist:
        # Result object doesn't exist yet, so it's definitely not ready.
        logger.warning(f"[InterviewResult] Result for session {session_id} not yet generated. Polling will begin.")
        results_ready = False
    # --- END OF CORRECTION ---

    context = {
        'session': session, 
        'result': result,
        'results_ready': results_ready, # Pass the flag to the template
    }
    return render(request, 'interviews/interview_result.html', context)




@login_required
def ats_resume_tools_view(request):
    """
    Renders the hub page that links to external tools and includes the keyword generator.
    """
    user_action_plans = ActionPlan.objects.filter(user=request.user).select_related('career')
    context = {
        'action_plans': user_action_plans
    }
    return render(request, 'tools/ats_resume_tools.html', context)


@login_required
@require_POST
def get_resume_keywords_view(request):
    """
    API endpoint that uses AI to generate resume keywords for a given career.
    """
    try:
        data = json.loads(request.body)
        career_title = data.get('career')
        if not career_title:
            return JsonResponse({'error': 'Career title is required.'}, status=400)

        logger.info(f"Generating resume keywords for '{career_title}' for user {request.user.username}")

        client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
            api_key=settings.AZURE_OPENAI_AGENT_KEY,
            api_version="2024-02-01"
        )

        system_prompt = (
            "You are an expert resume writer and career coach specializing in Applicant Tracking Systems (ATS). "
            "Your task is to generate a list of essential keywords and skills for a specific job title. "
            "You MUST respond with ONLY a valid JSON object. Do not include any other text. "
            "The JSON object should have a single key 'keywords' which is an array of 10-15 strings."
        )
        user_prompt = f"Generate the top ATS keywords for the job title: '{career_title}'"

        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        keywords_data = json.loads(response.choices[0].message.content)
        return JsonResponse(keywords_data)

    except Exception as e:
        logger.error(f"[GetResumeKeywords] AI call failed: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def optimize_resume_text_view(request):
    """
    API endpoint that uses AI to transform rough text into professional resume bullet points
    AND provides coaching suggestions.
    """
    try:
        data = json.loads(request.body)
        career_title = data.get('career')
        raw_text = data.get('text')

        if not career_title or not raw_text:
            return JsonResponse({'error': 'Career title and text are required.'}, status=400)

        logger.info(f"Optimizing resume text for '{career_title}' for user {request.user.username}")

        client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
            api_key=settings.AZURE_OPENAI_AGENT_KEY,
            api_version="2024-02-01"
        )

        # --- THIS IS THE UPDATED, MORE POWERFUL PROMPT ---
        system_prompt = (
            "You are an expert resume writer and career coach. Your task is to analyze a user's rough description of an accomplishment and provide two things in a single JSON object: rewritten bullet points, and coaching suggestions. "
            "You MUST respond with ONLY a valid JSON object. Do not include any other text. "
            "The JSON object must have two keys: 'bullet_points' (an array of 3-5 rewritten strings) and 'suggestions' (an array of 1-3 strings with coaching advice). "
            "For 'bullet_points': Start each with a strong action verb, add quantifiable metrics (even if you have to suggest a plausible number), and tailor the language for the job title. "
            "For 'suggestions': Analyze the original text and give the user advice on what was missing. For example, if they didn't provide numbers, suggest they add quantifiable achievements. If they used passive language, suggest stronger verbs."
        )
        user_prompt = f"Analyze and rewrite the following text for a resume targeting the job title '{career_title}':\n\n'{raw_text}'"

        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        optimized_data = json.loads(response.choices[0].message.content)
        return JsonResponse(optimized_data)

    except Exception as e:
        logger.error(f"[OptimizeResumeText] AI call failed: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@require_POST
@csrf_exempt
def analyze_interview_frame_view(request):
    """
    Receives an image frame and uses ONLY the Computer Vision API
    to detect if a person is present.
    """
    session_id = request.POST.get('session_id')
    try:
        image_data = request.FILES.get('frame').read()
        session = get_object_or_404(InterviewSession, id=session_id, user=request.user)

        vision_client = ImageAnalysisClient(
            endpoint=settings.AZURE_VISION_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_VISION_KEY)
        )

        vision_result = vision_client.analyze(
            image_data=image_data,
            visual_features=[VisualFeatures.PEOPLE],
        )
        
        person_was_detected = False
        if vision_result.people and len(vision_result.people) > 0:
            person_was_detected = True
        
        InterviewAnalysisPoint.objects.create(
            session=session,
            person_detected=person_was_detected
        )
        
        logger.info(f"Frame analysis for session {session_id}: Person detected = {person_was_detected}")
        return JsonResponse({'status': 'success', 'person_detected': person_was_detected})

    except Exception as e:
        logger.error(f"[AnalyzeFrame] Error for user {request.user.username} on session {session_id}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def ats_resume_tools_view(request):
    # This view is correct.
    user_action_plans = ActionPlan.objects.filter(user=request.user).select_related('career')
    context = {'action_plans': user_action_plans}
    return render(request, 'tools/ats_resume_tools.html', context)

@login_required
def whatsapp_subscribe_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- Action 1: Send a test digest ---
        if action == 'send_now':
            if user_profile.whatsapp_subscribed and user_profile.phone_number:
                if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                    logger.error("Twilio credentials are not configured in settings.py or .env file.")
                    messages.error(request, "Server configuration error: Twilio credentials are missing.")
                else:
                    try:
                        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                        success, message_text = send_digest_to_user(request.user, client)
                        if success:
                            messages.success(request, 'Test digest sent successfully! Check your WhatsApp.')
                        else:
                            messages.error(request, f'Failed to send digest: {message_text}')
                    except TwilioRestException as e:
                        logger.error(f"Twilio API Error when sending digest: {e}")
                        messages.error(request, f"Twilio Error: {e.msg}")
            else:
                messages.warning(request, 'You must be subscribed to send a test digest.')
            return redirect('apps:whatsapp.subscribe')

        # --- Action 2: Unsubscribe from the service ---
        elif action == 'unsubscribe':
            user_profile.whatsapp_subscribed = False
            user_profile.save()
            messages.info(request, 'You have been unsubscribed from the WhatsApp Career Digest.')
            logger.info(f"User '{request.user.username}' unsubscribed from WhatsApp digest.")
            return redirect('apps:whatsapp.subscribe')

            # Default Action: Handle the subscription/update form submission
        else:
            form = WhatsAppSubscribeForm(request.POST, instance=user_profile)
            if form.is_valid():
                phone_number = form.cleaned_data['phone_number']
                # Add validation for the '+' prefix
                if not phone_number.startswith('+'):
                    form.add_error('phone_number', 'Number must start with a + country code.')
                    # If this error is added, the form is no longer valid, and it will fall through to the render below
                else:
                    user_profile.phone_number = f"whatsapp:{phone_number}"
                    user_profile.whatsapp_subscribed = True
                    user_profile.save()
                    messages.success(request, 'Subscription updated successfully!')
                    return redirect('apps:whatsapp.subscribe')
            # If the form is invalid (either from the start or because we added an error),
            # the code will now automatically fall through to the final render statement,
            # passing the form object that contains the errors.
    else:
        # This block now ONLY handles GET requests
        initial_data = {}
        if user_profile.phone_number:
            initial_data['phone_number'] = user_profile.phone_number.replace('whatsapp:', '')
        form = WhatsAppSubscribeForm(instance=user_profile, initial=initial_data)

    context = {
        'form': form,
        # This 'form' is now guaranteed to be the correct one (either a clean one for GET, or one with errors for POST)
        'is_subscribed': user_profile.whatsapp_subscribed
    }
    return render(request, 'whatsapp/subscribe.html', context)


@csrf_exempt
def whatsapp_webhook(request):
    return HttpResponse("")