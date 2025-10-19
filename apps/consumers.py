import json
import logging
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from openai import AzureOpenAI
from .models import InterviewSession, InterviewTurn, UserProfile, InterviewResult, InterviewAnalysisPoint

logger = logging.getLogger(__name__)

class InterviewConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.user = self.scope["user"]
        
        logger.info(f"[WebSocket] Connection attempt:")
        logger.info(f"  - Session ID: {self.session_id}")
        logger.info(f"  - User: {self.user}")
        logger.info(f"  - Authenticated: {self.user.is_authenticated}")
        logger.info(f"  - Path: {self.scope.get('path')}")
        
        if not self.user.is_authenticated:
            logger.warning(f"[WebSocket] REJECTED - User not authenticated")
            await self.close()
            return
        
        try:
            self.session = await self.get_interview_session(self.session_id)
            logger.info(f"[WebSocket] Session found: {self.session.id}")
        except Exception as e:
            logger.error(f"[WebSocket] Session lookup failed: {e}")
            await self.close()
            return
        
        await self.channel_layer.group_add(f'interview_{self.session_id}', self.channel_name)
        await self.accept()
        logger.info(f"[WebSocket] ✅ CONNECTION ACCEPTED for session {self.session_id}")
        
        await self.send_ai_message("Hello! I'm your AI interviewer from Cariera. I'm here to help you practice. When you're ready, please tell me a bit about yourself to begin.")

    async def disconnect(self, close_code):
        logger.info(f"[WebSocket] Disconnected for session {self.session_id}. Triggering analysis.")
        asyncio.create_task(self.analyze_and_save_results())
        await self.channel_layer.group_discard(f'interview_{self.session_id}', self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'user_speech':
            user_message = data.get('message', '')
            await self.create_interview_turn(user_message, 'user')
            await self.get_and_send_ai_response(user_message)

    async def get_and_send_ai_response(self, user_message):
        try:
            personality_context = "The user has not completed a personality assessment."
            try:
                user_profile = await self.get_user_profile(self.user)
                if user_profile.personality_type:
                    personality_context = f"User's Holland Code is {user_profile.personality_type}. Tailor questions accordingly."
            except UserProfile.DoesNotExist:
                pass

            system_prompt = (
                f"You are an expert AI mock interviewer named Cariera. Be friendly and professional. "
                f"Interview Context: '{self.session.context or 'General Practice'}' | Difficulty: '{self.session.get_difficulty_display()}'. "
                f"Ask one question at a time. {personality_context}"
            )
            
            client = AzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
                api_key=settings.AZURE_OPENAI_AGENT_KEY,
                api_version="2024-02-01"
            )
            
            conversation_history = [{"role": "system", "content": system_prompt}]
            turns = await self.get_interview_turns()
            for turn in turns:
                role = "user" if turn.speaker == 'user' else "assistant"
                conversation_history.append({"role": role, "content": turn.text})

            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
                messages=conversation_history,
                temperature=0.8,
                max_tokens=200,
            )
            ai_response_text = response.choices[0].message.content.strip()

            await self.create_interview_turn(ai_response_text, 'ai')
            await self.send_ai_message(ai_response_text)
        except Exception as e:
            logger.error(f"[AIResponse] Error: {e}", exc_info=True)
            await self.send_ai_message("I'm sorry, I encountered an error. Please try speaking again.")

    async def analyze_and_save_results(self):
        try:
            logger.info(f"[Analysis] Starting analysis for session {self.session_id}")
            await self.update_session_status_completed()
            turns = await self.get_interview_turns()

            if not turns or len(turns) < 2:
                logger.warning(f"[Analysis] Session {self.session_id} has too few turns. Creating a default result.")
                await self.create_interview_result({
                    'overall_score': 0,
                    'confidence_score': 0,
                    'clarity_score': 0,
                    'feedback_summary': "This interview session was too short to generate a meaningful analysis. Please try again and complete at least one full exchange with the AI interviewer."
                }, 0)
                return

            transcript = "\n".join([f"{turn.speaker.upper()}: {turn.text}" for turn in turns])
            analysis_points = await self.get_analysis_points()
            
            presence_summary = "Camera analysis was not enabled for this session."
            camera_presence_score = 0
            
            if analysis_points:
                total_points = len(analysis_points)
                presence_count = sum(1 for point in analysis_points if point.person_detected)
                presence_percentage = (presence_count / total_points) * 100 if total_points > 0 else 0
                camera_presence_score = int(presence_percentage)
                presence_summary = f"Camera Presence Analysis: The user was visibly present on camera for approximately {camera_presence_score}% of the interview."

            system_prompt = (
                "You are a positive and encouraging AI career coach named Cariera. Your task is to analyze an interview transcript and provide constructive feedback and scores in a valid JSON format. "
                "You MUST respond with ONLY a valid JSON object. "
                "The JSON object must have keys: 'overall_score', 'confidence_score', 'clarity_score', and 'feedback_summary'.\n\n"
                "SCORING RUBRIC (0-100 scale):\n"
                "- **50-60:** Average performance. The user answered the questions but lacked detail or structure.\n"
                "- **70-80:** Good performance. The user was clear, confident, and provided good examples.\n"
                "- **80-90:** Excellent performance. The user was articulate, confident, and gave structured, impactful answers.\n"
                "- **90+:** Exceptional, job-ready performance.\n\n"
                "METRIC DEFINITIONS:\n"
                "- **Clarity Score:** How clear and easy to understand were the user's answers? Did they use STAR method (Situation, Task, Action, Result) logic?\n"
                "- **Confidence Score:** How confident did the user sound? Base this on their word choice and the provided Engagement Score from the camera analysis. A high engagement score should lead to a higher confidence score.\n"
                "- **Overall Score:** Your holistic assessment based on all factors.\n\n"
                "FEEDBACK GUIDELINES:\n"
                "- Start by highlighting a key strength.\n"
                "- Gently point out 1-2 areas for improvement.\n"
                "- End with an encouraging statement.\n\n"
                f"CONTEXT FOR THIS ANALYSIS:\n"
                f"- User's On-Camera Engagement Score was: {camera_presence_score}/100. Incorporate this into your assessment of their confidence."
            )
            
            user_prompt = f"Analyze this transcript:\n\n{transcript}"

            client = AzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_AGENT_ENDPOINT,
                api_key=settings.AZURE_OPENAI_AGENT_KEY,
                api_version="2024-02-01"
            )
            
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_AGENT_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            analysis_json = json.loads(response.choices[0].message.content)
            await self.create_interview_result(analysis_json, camera_presence_score)
            logger.info(f"[Analysis] Successfully saved analysis for session {self.session_id}")

        except Exception as e:
            logger.error(f"[Analysis] Failed for session {self.session_id}: {e}", exc_info=True)
            await self.create_interview_result({
                'overall_score': 0,
                'confidence_score': 0,
                'clarity_score': 0,
                'feedback_summary': "An unexpected error occurred while analyzing your interview. Please try again."
            }, 0)

    async def send_ai_message(self, message):
        await self.send(text_data=json.dumps({'type': 'ai_response', 'message': message}))

    @database_sync_to_async
    def get_interview_session(self, session_id):
        return InterviewSession.objects.select_related('user').get(id=session_id)
        
    @database_sync_to_async
    def update_session_status_completed(self):
        session = InterviewSession.objects.get(id=self.session_id)
        session.status = 'completed'
        session.end_time = datetime.now()
        session.save()
        self.session = session

    @database_sync_to_async
    def get_user_profile(self, user):
        return UserProfile.objects.get(user=user)

    @database_sync_to_async
    def create_interview_turn(self, text, speaker):
        session = InterviewSession.objects.get(id=self.session_id)
        return InterviewTurn.objects.create(session=session, text=text, speaker=speaker)

    @database_sync_to_async
    def get_interview_turns(self):
        return list(InterviewTurn.objects.filter(session_id=self.session_id).order_by('timestamp'))

    @database_sync_to_async
    def get_analysis_points(self):
        return list(InterviewAnalysisPoint.objects.filter(session_id=self.session_id).order_by('timestamp'))

    @database_sync_to_async
    def create_interview_result(self, analysis_data, camera_presence_score):
        session = InterviewSession.objects.get(id=self.session_id)
        InterviewResult.objects.update_or_create(
            session=session,
            defaults={
                'overall_score': analysis_data.get('overall_score', 0),
                'confidence_score': analysis_data.get('confidence_score', 0),
                'clarity_score': analysis_data.get('clarity_score', 0),
                'camera_presence_score': camera_presence_score,
                'feedback_summary': analysis_data.get('feedback_summary', 'Analysis could not be generated.')
            }
        )