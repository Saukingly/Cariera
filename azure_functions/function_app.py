import azure.functions as func
import logging
import requests
import json
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta
from typing import List

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def run_linkedin_search(query: str, headers: dict) -> List[dict]:
    """Uses the correct LinkedIn job search endpoint."""
    logging.info(f"=== LINKEDIN SEARCH START ===")
    logging.info(f"Query: '{query}'")

    # FIXED: Using the correct endpoint from your working curl example
    url = "https://linkedin-api-data.p.rapidapi.com/job/search"

    # FIXED: Using the correct parameters from your curl example
    querystring = {
        "query": query,
        "offsite": "0",
        "limit": "10",
        "geo": "102478259"  # Adding geo parameter from your example
    }

    # Keep the headers as they are in your curl example
    headers_with_content_type = {
        **headers,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logging.info(f"Request URL: {url}")
    logging.info(f"Query params: {querystring}")
    logging.info(f"Headers: {headers_with_content_type}")

    try:
        response = requests.get(url, headers=headers_with_content_type, params=querystring, timeout=15)
        logging.info(f"Response status: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"LinkedIn API error: {response.status_code}")
            logging.error(f"Error response: {response.text}")
            return []

        data = response.json()
        logging.info(f"LinkedIn response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        logging.info(f"LinkedIn response (first 1500 chars): {json.dumps(data, indent=2)[:1500]}...")

        results = []

        # Parse based on the structure you showed in the example
        if data.get('success') and data.get('data', {}).get('elements'):
            elements = data['data']['elements']
            logging.info(f"Found {len(elements)} LinkedIn job elements")

            for element in elements[:5]:  # Limit to 5 results
                job_card = element.get('jobCard', {}).get('jobPostingCard', {})

                # Extract job details from the nested structure
                title = job_card.get('title', 'Software Engineer Position')
                company = job_card.get('companyName', 'LinkedIn Company')
                location = job_card.get('location', 'Various')

                # Create a more descriptive title if original is missing
                if not title or title == 'Software Engineer Position':
                    title = f"{query.title()} Position"

                results.append({
                    'title': title,
                    'opportunity_type': 'JOB',
                    'organization_name': company,
                    'location': location,
                    'description': f"Job opportunity for {query} position at {company}",
                    'source_url': 'https://linkedin.com/jobs'
                })
        else:
            logging.info("LinkedIn API returned unsuccessful response or no elements")

        logging.info(f"=== LINKEDIN SEARCH END: {len(results)} results ===")
        return results

    except Exception as e:
        logging.error(f"LinkedIn API error: {e}")
        return []


def run_bing_search(query: str, result_type: str, headers: dict) -> List[dict]:
    """Uses the Bing search API with corrected response parsing."""
    logging.info(f"=== BING SEARCH START ===")
    logging.info(f"Query: '{query}', Type: '{result_type}'")

    url = "https://bing-search-scraper-api-10x-cheaper.p.rapidapi.com/bing"
    querystring = {
        "query": query,
        "device": "desktop",
        "count": "10",
        "max_pages": "1",
        "setLang": "en",
        "cc": "US"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        logging.info(f"Response status: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"Bing API error: {response.status_code} - {response.text}")
            return []

        data = response.json()
        logging.info(f"Bing response keys: {list(data.keys())}")

        results = []

        # FIXED: Based on your logs, the structure is pages -> "1" -> search_results
        pages = data.get('pages', {})
        page_1 = pages.get('1', {})
        search_results = page_1.get('search_results', [])

        logging.info(f"Found {len(search_results)} Bing search results")
        logging.info(f"First result sample: {search_results[0] if search_results else 'None'}")

        for result in search_results[:5]:  # Limit to 5 results
            domain = urlparse(result.get('link', '')).netloc
            results.append({
                'title': result.get('title', 'N/A'),
                'opportunity_type': result_type,
                'organization_name': domain.replace('www.', '').replace('bing.com',
                                                                        '').capitalize() if domain else 'Unknown',
                'location': "Online / Various",
                'description': result.get('snippet', ''),
                'source_url': result.get('link', '#')
            })

        logging.info(f"=== BING SEARCH END: {len(results)} results ===")
        return results

    except Exception as e:
        logging.error(f"Bing API error: {e}")
        return []


def run_instagram_scrape(headers: dict) -> List[dict]:
    """Uses the correct Instagram API endpoint from your documentation."""
    logging.info(f"=== INSTAGRAM SEARCH START ===")
    username = "scholarshipjamaica"
    logging.info(f"Username: {username}")

    # FIXED: Using the exact endpoint from your curl example
    url = "https://instagram-social-api.p.rapidapi.com/v1/posts"

    # FIXED: Removing the 'count' parameter that caused the 400 error
    # Using only the parameter from your curl example
    querystring = {
        "username_or_id_or_url": username
        # Removed 'count' parameter as it's invalid according to the error
    }

    logging.info(f"Request URL: {url}")
    logging.info(f"Query params: {querystring}")
    logging.info(f"Headers: {headers}")

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=20)
        logging.info(f"Response status: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"Instagram API error: {response.status_code}")
            logging.error(f"Error response: {response.text}")
            return []

        data = response.json()
        logging.info(f"Instagram response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        logging.info(f"Instagram response (first 1500 chars): {json.dumps(data, indent=2)[:1500]}...")

        results = []
        five_weeks_ago = datetime.now() - timedelta(weeks=5)

        # Parse based on actual response structure - we'll adjust based on logs
        posts_data = data.get("data", {})
        if isinstance(posts_data, dict):
            items = posts_data.get("items", [])
        else:
            items = posts_data if isinstance(posts_data, list) else []

        logging.info(f"Found {len(items)} Instagram posts")

        for post in items:
            post_timestamp = post.get("taken_at", 0)
            if post_timestamp and datetime.fromtimestamp(post_timestamp) < five_weeks_ago:
                continue

            caption_data = post.get("caption", {})
            caption = ""
            if isinstance(caption_data, dict):
                caption = caption_data.get("text", "")
            elif isinstance(caption_data, str):
                caption = caption_data

            if caption:  # Only add posts with captions
                results.append({
                    'title': caption.split('\\n')[0][:80] + "..." if len(caption.split('\\n')[0]) > 80 else
                    caption.split('\\n')[0],
                    'opportunity_type': 'SCHOLARSHIP',
                    'organization_name': 'ScholarshipJamaica (Instagram)',
                    'location': 'Jamaica',
                    'description': caption,
                    'source_url': f"https://www.instagram.com/p/{post.get('code', '')}/"
                })

        logging.info(f"=== INSTAGRAM SEARCH END: {len(results)} results ===")
        return results

    except Exception as e:
        logging.error(f"Instagram API error: {e}")
        return []


@app.route(route="find_opportunities")
def find_opportunities(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('=== FUNCTION START ===')

    try:
        req_body = req.get_json()
        career_title = req_body.get('career_title', 'software developer')
        location = req_body.get('location', 'remote')
        logging.info(f"Career: '{career_title}', Location: '{location}'")
    except ValueError as e:
        logging.error(f"Invalid JSON in request: {e}")
        return func.HttpResponse("Invalid JSON.", status_code=400)

    api_key = os.environ.get("RAPIDAPI_KEY")
    logging.info(f"API Key present: {bool(api_key)}")
    logging.info(f"API Key length: {len(api_key) if api_key else 0}")

    if not api_key:
        logging.error("RAPIDAPI_KEY environment variable not found")
        return func.HttpResponse(
            json.dumps({"error": "Server configuration missing API key."}),
            status_code=500
        )

    # Set up headers exactly as shown in your curl examples
    linkedin_headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "linkedin-api-data.p.rapidapi.com"
    }

    bing_headers = {
        "Accept": "application/json",
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "bing-search-scraper-api-10x-cheaper.p.rapidapi.com"
    }

    instagram_headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "instagram-social-api.p.rapidapi.com"
    }

    # Construct queries
    job_query = career_title  # Simplified - just the career title for LinkedIn jobfunction search
    scholarship_query = f"{career_title} scholarship Jamaica university"

    logging.info(f"Job query: '{job_query}'")
    logging.info(f"Scholarship query: '{scholarship_query}'")
    logging.info("=== STARTING API CALLS ===")

    # Fetch from all sources
    linkedin_jobs = run_linkedin_search(job_query, linkedin_headers)
    instagram_scholarships = run_instagram_scrape(instagram_headers)
    bing_scholarships = run_bing_search(scholarship_query, "SCHOLARSHIP", bing_headers)

    all_opportunities = linkedin_jobs + instagram_scholarships + bing_scholarships

    logging.info(f"=== FINAL RESULTS ===")
    logging.info(f"LinkedIn: {len(linkedin_jobs)} opportunities")
    logging.info(f"Instagram: {len(instagram_scholarships)} opportunities")
    logging.info(f"Bing: {len(bing_scholarships)} opportunities")
    logging.info(f"Total: {len(all_opportunities)} opportunities")

    if all_opportunities:
        logging.info(f"Sample opportunity: {json.dumps(all_opportunities[0], indent=2)}")

    return func.HttpResponse(
        json.dumps({"opportunities": all_opportunities}),
        mimetype="application/json",
        status_code=200
    )