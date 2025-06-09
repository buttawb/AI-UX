import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# Ensure you have this file with your API key
from .gemini_keys import GLOBAL_SEARCH_API_KEY, OPENAI_API_KEY_SULTAN
import re
from google import genai

# Default Figma file ID (will be overridden by user input)
DEFAULT_FIGMA_FILE_ID = 'dl5VgCWMZwL3uRi9mIOMvX'

# Figma access tokens
FIGMA_TOKENS = {
    'wahab_token': 'figd_str4YMXlfbmgslAlQnZnJIKI_DPqlQoq8wiMKl4Q',
    'ramsha_token': 'figd_3bgofXhJbrbVRuPxlaXmrH-AwL6RTdr9hW1PLydz',
    'farzam_token': 'figd_iVOxEWPrSYY0MFIOD06Btza3Z2ofcJvaPENMSNSB'
}


# Base prompt template that will be used for both OpenAI and Gemini
BASE_PROMPT_TEMPLATE = """
You are a world-class UX/UI design expert. Analyze the provided Figma design JSON.
Your task is to analyze ONLY the frames with the following node IDs and their dimensions: {frame_data}

{user_prompt_section}

For EACH of these specific frames, provide a detailed analysis. The final output must be a single, valid JSON object where each key is one of the frame's node IDs listed above.
The value for each key should be another JSON object with five keys: "heatmap", "report", "suggestions", "positive_points", and "ux_score".

For EACH frame, provide a comprehensive UX report that includes the following sections with HTML formatting:

<h2>Overall Assessment</h2>
<p>[2-3 sentences providing a high-level overview of the design]</p>

<h2>Key Strengths</h2>
<ul>
<li>[First major strength]</li>
<li>[Second major strength]</li>
<li>[Third major strength]</li>
</ul>

<h2>Areas for Improvement</h2>
<ul>
<li>[First area needing improvement]</li>
<li>[Second area needing improvement]</li>
<li>[Third area needing improvement]</li>
</ul>

<h2>Recommendations</h2>
<ul>
<li>[First actionable recommendation]</li>
<li>[Second actionable recommendation]</li>
<li>[Third actionable recommendation]</li>
</ul>

The report should be detailed enough to provide clear insights but concise enough to be easily digestible.

IMPORTANT: For EACH frame, you MUST identify at least 2-3 UI components or regions where users might get confused, stuck, or abandon the task.  
These MUST be provided as an array called "drop_off_points". Each item should include:  
- "x": percentage horizontal coordinate (0-100)  
- "y": percentage vertical coordinate (0-100)  
- "reason": a brief natural language explanation of why this spot causes drop-off.

Also, for EACH frame, identify 2-3 UI components or regions that are particularly well-designed or effective.
These MUST be provided as an array called "positive_points". Each item should include:
- "x": percentage horizontal coordinate (0-100)
- "y": percentage vertical coordinate (0-100)
- "reason": a brief natural language explanation of what makes this element effective or well-designed.

IMPORTANT: For coordinates in heatmap, suggestions, and positive_points:
1. Use percentage-based coordinates (0-100) for both x and y values
2. x: 0 means left edge, 100 means right edge
3. y: 0 means top edge, 100 means bottom edge
4. Example: x: 50, y: 50 means center of the frame
5. DO NOT use pixel values, use percentages only
6. Make sure there are at least 6 heatmap points and suggestions in a single node

For the ux_score:
Calculate a score from 0-100 based on the following criteria:
1. Visual Hierarchy and Layout (25 points)
   - Clear visual hierarchy
   - Proper spacing and alignment
   - Balanced composition
2. Usability and Navigation (25 points)
   - Intuitive navigation
   - Clear call-to-actions
   - Logical user flow
3. Content and Readability (25 points)
   - Clear typography
   - Appropriate contrast
   - Well-organized content
4. Interaction Design (25 points)
   - Responsive feedback
   - Error prevention
   - Smooth interactions

Deduct points based on:
- Number and severity of drop-off points (-5 to -15 points each)
- Number and severity of suggestions (-3 to -10 points each)
- Missing critical elements (-5 to -20 points each)

Add points based on:
- Number and quality of positive points (+5 to +15 points each)
- Innovative solutions (+5 to +10 points)
- Accessibility considerations (+5 to +10 points)

The final score should reflect the overall quality of the design while considering both strengths and weaknesses.

Example of the required final JSON output structure and make sure to follow it exactly:
{{
    "analysis_data": {{
        "3:15": {{
            "heatmap":  [{{"x": 50, "y": 50, "intensity": 0.9}}],
            "report": "<h2>Overall Assessment</h2><p>This design demonstrates a strong focus on user experience with clear visual hierarchy and intuitive navigation. The layout effectively guides users through the content while maintaining visual balance and proper spacing.</p><h2>Key Strengths</h2><ul><li>Prominent call-to-action placement with excellent contrast</li><li>Consistent visual language throughout the interface</li><li>Well-structured content hierarchy</li></ul><h2>Areas for Improvement</h2><ul><li>Mobile responsiveness needs enhancement</li><li>Feedback mechanisms for user interactions could be improved</li><li>Error states need to be more prominent</li></ul><h2>Recommendations</h2><ul><li>Implement more responsive touch targets for mobile users</li><li>Add visual feedback for all interactive elements</li><li>Enhance error state visibility and messaging</li></ul>",
            "suggestions": [{{"x": 25, "y": 75, "suggestion": "Move button to bottom left for better thumb reach"}}],
            "positive_points": [{{"x": 40, "y": 60, "reason": "Clear and prominent call-to-action button with excellent contrast"}}],
            "ux_score": 85,
            "drop_off_points": [
                {{"x":40,"y":60,"reason":"Users get stuck here because the button label is unclear."}},
            ],
        }},
        "4:2": {{
            "heatmap":  [{{"x": 75, "y": 25, "intensity": 0.8}}],
            "report": "<h2>Overall Assessment</h2><p>The interface presents a clean and modern design with excellent use of white space and typography. The content organization is logical and the visual hierarchy effectively guides users through the information.</p><h2>Key Strengths</h2><ul><li>Consistent color scheme and visual language</li><li>Well-structured navigation elements</li><li>Excellent use of white space and typography</li></ul><h2>Areas for Improvement</h2><ul><li>Contrast issues in certain areas</li><li>Error handling could be more intuitive</li><li>Mobile touch targets need optimization</li></ul><h2>Recommendations</h2><ul><li>Enhance contrast ratios for better readability</li><li>Implement more intuitive error states</li><li>Optimize touch targets for mobile users</li></ul>",
            "suggestions": [{{"x": 10, "y": 90, "suggestion": "Increase contrast in bottom left for better readability"}}],
            "positive_points": [{{"x": 50, "y": 30, "reason": "Excellent use of white space and typography creates clear visual hierarchy"}}],
            "ux_score": 78,
            "drop_off_points": [
                {{"x":40,"y":60,"reason":"Users get stuck here because the button label is unclear."}},
            ],
        }}
    }}
}}

Here is the Figma design data:
{figma_data}
"""


def landing_page(request):
    """
    View function for the landing page.
    """
    return render(request, 'index.html')


@csrf_exempt
def upload_design(request):
    """
    Upload a design (not used in this case as we fetch designs directly from Figma).
    """
    context = {'figma_file_id': DEFAULT_FIGMA_FILE_ID}
    return render(request, 'upload.html', context)


@csrf_exempt
def fetch_figma_file(request):
    """
    Fetch the Figma file data using the Figma API.
    """
    file_id = request.GET.get('file_id', DEFAULT_FIGMA_FILE_ID)
    access_token = request.GET.get('access_token')

    if not access_token:
        return JsonResponse({"error": "No access token provided"}, status=400)

    # Get the actual token value if it's a predefined token
    if access_token in FIGMA_TOKENS:
        access_token = FIGMA_TOKENS[access_token]

    # url = "https://api.figma.com/v1/me"
    headers = {"X-Figma-Token": access_token}

    # response = requests.get(url, headers=headers)
    # print("Logged In Figma User:", response.json())

    url = f"https://api.figma.com/v1/files/{file_id}"
    response = requests.get(url, headers=headers)

    print("DONE fetch_figma_file")
    if response.status_code == 200:
        return JsonResponse(response.json())
    return JsonResponse({"error": "Failed to fetch Figma file."}, status=400)


@csrf_exempt
def generate_heatmap(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        figma_data = data.get('figma_data')
        user_prompt = data.get('user_prompt', '')

        try:
            # heatmap_data = call_openai_heatmap(figma_data, user_prompt) # Can switch to OpenAI if needed
            heatmap_data = call_gemini_heatmap(figma_data, user_prompt)
            print("heatmap")
            print(heatmap_data)
            print("End")
        except Exception as e:
            return JsonResponse({'error': f'Model call failed: {str(e)}'}, status=500)

        return JsonResponse({'heatmap_data': heatmap_data})

    return JsonResponse({'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def call_openai_heatmap(figma_data, user_prompt=''):
    # Extract frame data
    frame_data = {}
    for canvas in figma_data.get('children', []):
        for frame in canvas.get('children', []):
            if frame.get('type') == 'FRAME':
                frame_data[frame.get('id')] = {
                    'width': frame.get('absoluteBoundingBox', {}).get('width', 0),
                    'height': frame.get('absoluteBoundingBox', {}).get('height', 0)
                }

    # Add user prompt section if provided
    user_prompt_section = f"""
    Additional User Instructions:
    {user_prompt}
    
    Please incorporate these instructions while maintaining the required output structure.
    """ if user_prompt else ""

    prompt = BASE_PROMPT_TEMPLATE.format(
        frame_data=json.dumps(frame_data),
        user_prompt_section=user_prompt_section,
        figma_data=json.dumps(figma_data)
    )

    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY_SULTAN}',
        'Content-Type': 'application/json',
    }
    openai_payload = {
        "model": "gpt-4",  # or "gpt-3.5-turbo"
        "messages": [
            {"role": "system", "content": "You are a UX analyst and UI design expert."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions", json=openai_payload, headers=headers)
    response.raise_for_status()
    result = response.json()

    content = result["choices"][0]["message"]["content"]
    print("OpenAI response content:", content)

    heatmap_report = extract_json_from_model_response(content)
    return heatmap_report


@csrf_exempt
def call_gemini_heatmap(figma_data, user_prompt=''):
    """
    Get UX analysis from Google's Gemini API using the genai client.
    """
    # Extract frame data
    frame_data = {}
    for canvas in figma_data.get('children', []):
        for frame in canvas.get('children', []):
            if frame.get('type') == 'FRAME':
                frame_data[frame.get('id')] = {
                    'width': frame.get('absoluteBoundingBox', {}).get('width', 0),
                    'height': frame.get('absoluteBoundingBox', {}).get('height', 0)
                }

    # Add user prompt section if provided
    user_prompt_section = f"""
    Additional User Instructions:
    {user_prompt}
    
    Please incorporate these instructions while maintaining the required output structure.
    """ if user_prompt else ""

    prompt = BASE_PROMPT_TEMPLATE.format(
        frame_data=json.dumps(frame_data),
        user_prompt_section=user_prompt_section,
        figma_data=json.dumps(figma_data)
    )

    # Try models in order of preference
    model_names = [
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-05-06",
        "gemini-2.5-pro-preview-tts",
        "gemini-2.0-flash",
        "gemini-2.0-flash-preview-image-generation",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "veo-2.0-generate-001",
        "gemini-2.0-flash-live-001",
    ]

    last_error = None
    client = genai.Client(api_key=GLOBAL_SEARCH_API_KEY)

    for model_name in model_names:
        try:
            print(f"Attempting with model: {model_name}")

            response = client.models.generate_content(
                model=model_name,
                contents=[{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }],
            )

            if response.candidates:
                content_data = response.candidates[0].content
                if not content_data or not content_data.parts:
                    continue

                parts = content_data.parts
                if not parts[0].text:
                    continue

                content = parts[0].text
                heatmap_report = extract_json_from_model_response(content)

                if "analysis_data" in heatmap_report:
                    unexpected_frames = set(
                        heatmap_report["analysis_data"].keys()) - set(frame_data.keys())
                    if unexpected_frames:
                        print(
                            f"Warning: Response contains unexpected frame IDs: {unexpected_frames}")
                        heatmap_report["analysis_data"] = {
                            k: v for k, v in heatmap_report["analysis_data"].items()
                            if k in frame_data.keys()
                        }

                return heatmap_report

        except Exception as e:
            last_error = e
            print(f"Error with model {model_name}: {str(e)}")
            continue

    if last_error:
        raise Exception(
            f"All Gemini models failed. Last error: {str(last_error)}")
    raise Exception(
        "All Gemini models failed without specific error information")


# Renamed from extract_json_from_openai
def extract_json_from_model_response(content):
    """
    Extracts JSON object from a model's text response that might include markdown code fences.
    """
    # Remove triple backticks or any markdown code fences (json, etc.)
    cleaned = re.sub(r"```(?:json)?|```", "", content,
                     flags=re.IGNORECASE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e_direct:
        # Try to find first JSON object substring if direct parsing fails
        # This regex looks for content starting with { and ending with }
        json_match = re.search(
            r"\{[^{}]*(((?<Core>{[^{}]*})|(?<-Core>[^{}]*)|[^{}Core])*)\}", cleaned, re.DOTALL)

        if json_match:
            try:
                # Use group(0) for the entire match
                return json.loads(json_match.group(0))
            except json.JSONDecodeError as e_match:
                print(f"Failed to parse extracted JSON: {e_match}")
                print(
                    f"Content that failed parsing after regex: '{json_match.group(0)}'")
                raise Exception(
                    f"Could not decode JSON from model response even after regex extraction. Original error: {e_direct}, Regex error: {e_match}, Content: '{cleaned}'")
        else:
            print(f"Direct JSON parsing failed: {e_direct}")
            print(f"No JSON object found with regex in content: '{cleaned}'")
            raise Exception(
                f"Could not decode JSON from model response and no JSON object found via regex. Original error: {e_direct}, Content: '{cleaned}'")


@csrf_exempt
def fetch_figma_image_urls(request):
    """
    Fetches PNG image URLs for a list of Figma nodes in a single request.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST request required."}, status=405)

    try:
        data = json.loads(request.body)
        node_ids = data.get('node_ids')
        file_id = data.get('file_id', DEFAULT_FIGMA_FILE_ID)
        access_token = data.get('access_token')

        if not access_token:
            return JsonResponse({"error": "No access token provided"}, status=400)

        # Get the actual token value if it's a predefined token
        if access_token in FIGMA_TOKENS:
            access_token = FIGMA_TOKENS[access_token]

        if not node_ids or not isinstance(node_ids, list):
            return JsonResponse({"error": "Invalid or missing 'node_ids' list."}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body."}, status=400)

    ids_query_param = ",".join(node_ids)
    url = f"https://api.figma.com/v1/images/{file_id}?ids={ids_query_param}&format=png&scale=2"
    headers = {"X-Figma-Token": access_token}

    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        if data.get("err"):
            return JsonResponse({"error": f"Figma API error: {data['err']}"}, status=400)

        return JsonResponse({"image_urls": data.get("images", {})})

    except requests.RequestException as e:
        print("INN EXCEPTION of fetch_figma_image_urls:", str(e))
        return JsonResponse({"error": f"Failed to fetch image URLs from Figma: {str(e)}"}, status=500)
