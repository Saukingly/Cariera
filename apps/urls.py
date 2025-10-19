from django.urls import path
from .views import (
    # Journey & Folder Views
    journeys_list_view, create_journey_view, delete_journey_view,
    career_coach_chat_view, rename_journey_view, create_folder_view,
    move_journey_to_folder, rename_folder_view, delete_folder_view,
    move_journey_drag_drop, reorder_folders_view,

    # Action Plan & Opportunity Views
    action_plan_list_view,
    create_action_plan_view,
    delete_action_plan_view,
    action_plan_opportunities_view,
    action_plan_roadmap_view,
    find_opportunities_view,
    generate_roadmap_view,
    my_opportunities_view,
    toggle_opportunity_tracking,
    rename_action_plan_view,

    # Other Main Views
    explore_careers_view,
    profile_view,

    # Personality Test API
    get_personality_test_question,
    submit_personality_test_answer,
    calculate_personality_test_result,
    reset_personality_test,

    # Speech Service API
    get_speech_token_view,

    interview_setup_view,
    interview_session_view,
    interview_result_view,

    interview_delete_view,
    interview_progress_view,
    interview_retry_view,


    ats_resume_tools_view,
    get_resume_keywords_view,
    optimize_resume_text_view,

    analyze_interview_frame_view,

    
    whatsapp_subscribe_view,
    whatsapp_webhook,



)

app_name = "apps"

urlpatterns = [
    # Career Journey URLs
    path("journeys/", view=journeys_list_view, name="journeys.list"),
    path("journeys/new/", view=create_journey_view, name="journeys.new"),
    path("journeys/delete/<uuid:journey_id>/", view=delete_journey_view, name="journeys.delete"),
    path("journeys/rename/<uuid:journey_id>/", view=rename_journey_view, name="journeys.rename"),
    path("career-coach/chat/<uuid:journey_id>/", view=career_coach_chat_view, name="career_coach.chat"),

    # Folder Management URLs
    path("folders/new/", view=create_folder_view, name="folders.new"),
    path("folders/rename/<uuid:folder_id>/", view=rename_folder_view, name="folders.rename"),
    path("folders/delete/<uuid:folder_id>/", view=delete_folder_view, name="folders.delete"),
    path("folders/reorder/", view=reorder_folders_view, name="folders.reorder"),
    path("journeys/move-to-folder/", view=move_journey_to_folder, name="journeys.move_to_folder"),
    path("journeys/move-via-drag/", view=move_journey_drag_drop, name="journeys.move_drag_drop"),

    # --- ACTION PLAN & OPPORTUNITIES URLS ---
    path("my-action-plans/", view=action_plan_list_view, name="my_action_plans"),
    path("my-action-plans/new/", view=create_action_plan_view, name="create_action_plan"),
    path("my-action-plans/delete/<uuid:plan_id>/", view=delete_action_plan_view, name="delete_action_plan"),
    path("my-action-plans/opportunities/<int:career_id>/", view=action_plan_opportunities_view, name="action_plan.opportunities"),
    path("my-action-plans/roadmap/<int:career_id>/", view=action_plan_roadmap_view, name="action_plan.roadmap"),

    # API endpoints for AJAX calls
    path("api/find-opportunities/", view=find_opportunities_view, name="api.find_opportunities"),
    path("api/generate-roadmap/", view=generate_roadmap_view, name="api.generate_roadmap"),
    path("api/toggle-opportunity-tracking/<int:op_id>/", view=toggle_opportunity_tracking, name="api.toggle_tracking"),
    path("my-action-plans/rename/<uuid:plan_id>/", view=rename_action_plan_view, name="rename_action_plan"),
    path("my-opportunities/", view=my_opportunities_view, name="my_opportunities"),

    # Personality Test API Endpoints
    path("personality-test/question/", view=get_personality_test_question, name="personality_test.get_question"),
    path("personality-test/submit-answer/", view=submit_personality_test_answer, name="personality_test.submit_answer"),
    path("personality-test/calculate-result/", view=calculate_personality_test_result, name="personality_test.calculate_result"),
    path("personality-test/reset/", view=reset_personality_test, name="personality_test.reset"),

    # Speech Service API
    path("speech-token/", view=get_speech_token_view, name="speech_token"),

    # Other Pages
    path("explore-careers/", view=explore_careers_view, name="explore_careers"),
    path("profile/", view=profile_view, name="profile"),

    path("interviews/", view=interview_setup_view, name="interview.setup"),
    path("interviews/session/<uuid:session_id>/", view=interview_session_view, name="interview.session"),
    path("interviews/result/<uuid:session_id>/", view=interview_result_view, name="interview.result"),
    path("interviews/delete/<uuid:session_id>/", view=interview_delete_view, name="interview.delete"),
    # <-- New URL for deleting
    path("interviews/progress/", view=interview_progress_view, name="interview.progress"),
    # <-- New URL for progress chart
    path("interviews/retry/<uuid:session_id>/", view=interview_retry_view, name="interview.retry"),

  

    path("ats-resume-tools/", view=ats_resume_tools_view, name="ats_resume_tools"),
    # API Endpoints for the tools page
    path("api/get-resume-keywords/", view=get_resume_keywords_view, name="api.get_resume_keywords"),
    path("api/optimize-resume-text/", view=optimize_resume_text_view, name="api.optimize_resume_text"),

    path("api/analyze-frame/", view=analyze_interview_frame_view, name="api.analyze_frame"),



    path("whatsapp/subscribe/", view=whatsapp_subscribe_view, name="whatsapp.subscribe"),
    path("webhooks/whatsapp/", view=whatsapp_webhook, name="whatsapp.webhook"),

]
