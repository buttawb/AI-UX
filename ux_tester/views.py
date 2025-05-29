import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .gemini_keys import AVIALDO_GEMINI_KEY  # Ensure you have this file with your API key
import re

# Hardcoded Figma file ID
FIGMA_FILE_ID = '1J2MSZzASUTEKNrrQm5o8b'
FIGMA_ACCESS_TOKEN = 'figd_8KqZh4idtJM7bfuJ8AXSoTAGyJ_n42hLZwgNVUx8'
RAMSHA_FIGMA_ACCESS_TOKEN = 'figd_3bgofXhJbrbVRuPxlaXmrH-AwL6RTdr9hW1PLydz'
OPENAI_API_KEY = "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"
TEMP_TOKEN = "328267-66c5803b-80d4-4989-ad6f-8430d60fb714"
FIGMA_NODE_ID = '0:1'


@csrf_exempt
def upload_design(request):
    """
    Upload a design (not used in this case as we fetch designs directly from Figma).
    """
    return render(request, 'upload.html')


@csrf_exempt
def fetch_figma_file(request):
    """
    Fetch the hardcoded Figma file data using the Figma API.
    """
    url = "https://api.figma.com/v1/me"
    headers = {"X-Figma-Token": FIGMA_ACCESS_TOKEN}

    response = requests.get(url, headers=headers) # This call to /v1/me seems to be for a health check or auth check but its result is not used.

    url = f"https://api.figma.com/v1/files/{FIGMA_FILE_ID}"  # Using the hardcoded file ID
    response = requests.get(url, headers=headers)

    print("DONEE")
    if response.status_code == 200:
        return JsonResponse(response.json())
    return JsonResponse({"error": "Failed to fetch Figma file."}, status=400)


@csrf_exempt
def generate_heatmap(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        figma_data = data.get('figma_data')

        try:
            # heatmap_data = call_openai_heatmap(figma_data) # Can switch to OpenAI if needed
            heatmap_data = call_gemini_heatmap(figma_data)
        except Exception as e:
            return JsonResponse({'error': f'Model call failed: {str(e)}'}, status=500)

        return JsonResponse({'heatmap_data': heatmap_data})

    return JsonResponse({'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def call_openai_heatmap(figma_data):
    prompt = f"""
    You are a UX/UI expert analyzing a digital design represented by the following Figma design JSON data.

    1. Provide a detailed critique of the design, including:
    - Visual hierarchy clarity
    - Button styles (color contrast, size, placement)
    - Text readability (font size, color contrast)
    - Layout consistency and spacing
    - Any confusing or cluttered areas
    - Accessibility issues (color blindness, focus states, etc.)
    - Suggestions to improve user engagement and clarity

    2. Identify potential user behavior patterns on this design, such as:
    - Areas likely to attract clicks or hovers
    - Possible confusing flows or abandoned points
    - Elements that might cause hesitation or repeated clicks

    3. Return three separate outputs:

    a) A JSON array of simulated user interaction points for a heatmap.
        Each point should have:
        - "x": horizontal coordinate (integer)
        - "y": vertical coordinate (integer)
        - "intensity": a float from 0 to 1 indicating the strength of interaction

        Example:
        [
            {{"x": 123, "y": 456, "intensity": 0.9}},
            {{"x": 200, "y": 300, "intensity": 0.5}}
        ]

    b) A detailed UX/UI report as plain text summarizing all observations and recommendations.

    c) A JSON array of UX improvement suggestions, where each suggestion has:
        - "x": horizontal coordinate (integer) indicating where the suggestion applies
        - "y": vertical coordinate (integer)
        - "suggestion": a short actionable suggestion for improvement (string)

        Example:
        [
            {{"x": 150, "y": 400, "suggestion": "Increase button contrast for better visibility."}},
            {{"x": 320, "y": 220, "suggestion": "Enlarge font size for readability."}}
        ]

    The Figma design data is:
    {json.dumps(figma_data)}

    Respond with a JSON object with exactly three keys:
    {{
    "heatmap": [/* JSON array of heatmap points */],
    "report": "Your detailed UX/UI critique and recommendations here.",
    "suggestions": [/* JSON array of suggestions with coordinates and text */]
    }}

    Important: Output ONLY valid JSON with these three keys, no extra commentary.
    """
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    openai_payload = {
        "model": "gpt-4o",  # or "gpt-3.5-turbo"
        "messages": [
            {"role": "system", "content": "You are a UX analyst and UI design expert."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", json=openai_payload, headers=headers)
    response.raise_for_status()
    result = response.json()

    content = result["choices"][0]["message"]["content"]
    print("OpenAI response content:", content)  # Debugging output

    heatmap_report = extract_json_from_model_response(content) # Renamed for clarity
    return heatmap_report

@csrf_exempt
def call_gemini_heatmap(figma_data):
    """
    Get UX analysis from Google's Gemini API using direct HTTP requests.
    """
    prompt = f"""
    As a UX/UI expert, analyze this Figma design JSON data and provide:
    1. A heatmap of likely user interactions
    2. A UX/UI critique
    3. Specific improvement suggestions
    
    Design data: {json.dumps(figma_data)}
    
    Format response as JSON with these keys:
    {{
        "heatmap": [
            {{"x": 123, "y": 456, "intensity": 0.9}}
        ],
        "report": "UX analysis text here",
        "suggestions": [
            {{"x": 150, "y": 400, "suggestion": "Improvement text"}}
        ]
    }}
    Important: Output ONLY valid JSON with these three keys, no extra commentary. Ensure the JSON is well-formed.
    """

    # Option 1: Try gemini-1.0-pro (often a good default for this endpoint)
    # model_name = "gemini-1.0-pro"
    
    # Option 2: Try the latest 1.5 pro model
    model_name = "gemini-1.5-pro-latest" # Using this as it's generally preferred if available

    # Construct the API URL with the chosen model name
    gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={AVIALDO_GEMINI_KEY}"
    
    headers = {
        'Content-Type': 'application/json',
    }

    request_body = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 4096, # Increased further for safety with complex responses
        }
    }

    try:
        print(f"Calling Gemini API with URL: {gemini_api_url}") # Log the URL being used
        response = requests.post(gemini_api_url, headers=headers, json=request_body, timeout=180) # Increased timeout
        response.raise_for_status()
        
        response_json = response.json()

        if "candidates" not in response_json or not response_json["candidates"]:
            prompt_feedback = response_json.get("promptFeedback")
            error_message = f"Gemini API returned no candidates for model {model_name}."
            if prompt_feedback:
                block_reason = prompt_feedback.get('blockReason')
                safety_ratings = prompt_feedback.get('safetyRatings')
                error_message += f" Prompt feedback: Block Reason: {block_reason}, Safety Ratings: {safety_ratings}"
            # Log the full response if no candidates are found for debugging
            print(f"Gemini API response with no candidates: {response_json}")
            raise Exception(error_message)

        content_data = response_json["candidates"][0].get("content")
        if not content_data or "parts" not in content_data or not content_data["parts"]:
            print(f"Gemini API response missing 'parts' in content: {response_json}")
            raise Exception(f"Gemini API response missing 'parts' in content for model {model_name}.")
            
        parts = content_data["parts"]
        if "text" not in parts[0]:
            print(f"Gemini API response missing 'text' in parts[0]: {response_json}")
            raise Exception(f"Gemini API response missing 'text' in parts[0] for model {model_name}.")
            
        content = parts[0]["text"]
        # print("Gemini response raw content:", content) 
        
        heatmap_report = extract_json_from_model_response(content)
        return heatmap_report

    except requests.exceptions.HTTPError as e:
        print(f"HTTPError calling Gemini API (Status: {e.response.status_code}): {str(e)}")
        print(f"Gemini API Response Body: {e.response.text}")
        # Specific check for 404 to reiterate model name issue if it persists
        if e.response.status_code == 404:
             raise Exception(f"Failed to call Gemini API: Model '{model_name}' not found or not supported for generateContent on v1beta. Check model name and API key permissions. Response: {e.response.text}")
        raise Exception(f"Failed to call Gemini API (HTTPError): {str(e)}. Response: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API (RequestException): {str(e)}")
        raise Exception(f"Failed to call Gemini API (RequestException): {str(e)}")
    except KeyError as e_key:
        print(f"Error parsing Gemini API response (KeyError): {str(e_key)}. Response: {response_json if 'response_json' in locals() else 'Response JSON not available'}")
        raise Exception(f"Failed to parse Gemini API response: Invalid structure. Error: {str(e_key)}")
    except Exception as e_gen: # Catch other potential errors like JSONDecodeError
        print(f"Error processing Gemini response: {str(e_gen)}")
        raise


def extract_json_from_model_response(content): # Renamed from extract_json_from_openai
    """
    Extracts JSON object from a model's text response that might include markdown code fences.
    """
    # Remove triple backticks or any markdown code fences (json, etc.)
    cleaned = re.sub(r"```(?:json)?|```", "", content, flags=re.IGNORECASE).strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e_direct:
        # Try to find first JSON object substring if direct parsing fails
        # This regex looks for content starting with { and ending with }
        json_match = re.search(r"\{[^{}]*(((?<Core>{[^{}]*})|(?<-Core>[^{}]*)|[^{}Core])*)\}", cleaned, re.DOTALL)

        if json_match:
            try:
                return json.loads(json_match.group(0)) # Use group(0) for the entire match
            except json.JSONDecodeError as e_match:
                print(f"Failed to parse extracted JSON: {e_match}")
                print(f"Content that failed parsing after regex: '{json_match.group(0)}'")
                raise Exception(f"Could not decode JSON from model response even after regex extraction. Original error: {e_direct}, Regex error: {e_match}, Content: '{cleaned}'")
        else:
            print(f"Direct JSON parsing failed: {e_direct}")
            print(f"No JSON object found with regex in content: '{cleaned}'")
            raise Exception(f"Could not decode JSON from model response and no JSON object found via regex. Original error: {e_direct}, Content: '{cleaned}'")


@csrf_exempt
def fetch_figma_image_url(request):
    """
    Fetch PNG image URL of a specific Figma node (frame) via Figma Image API.
    """
    headers = {"X-Figma-Token": FIGMA_ACCESS_TOKEN}
    # Ensure FIGMA_NODE_ID is URL-encoded if it contains special characters, though typically it doesn't.
    url = f"https://api.figma.com/v1/images/{FIGMA_FILE_ID}?ids={FIGMA_NODE_ID}&format=png"

    try:
        response = requests.get(url, headers=headers, timeout=20) # Increased timeout for image rendering
        response.raise_for_status()
    except requests.RequestException as e:
        return JsonResponse({"error": f"Failed to fetch image URL from Figma: {str(e)}"}, status=500)

    data = response.json()
    
    if data.get("err"): # Figma API returns "err" for errors in the image rendering
        return JsonResponse({"error": f"Figma API error for image: {data['err']}"}, status=400)

    images = data.get("images", {})
    image_url = images.get(FIGMA_NODE_ID)

    if not image_url:
        return JsonResponse({"error": "Image URL not found for given node ID in Figma response. Ensure node ID is correct and the frame is exportable."}, status=404)

    return JsonResponse({"image_url": image_url})
