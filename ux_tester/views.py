import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .gemini_keys import AVIALDO_GEMINI_KEY  # Ensure you have this file with your API key
import re

# Default Figma file ID (will be overridden by user input)
DEFAULT_FIGMA_FILE_ID = '1J2MSZzASUTEKNrrQm5o8b'
FIGMA_ACCESS_TOKEN = 'figd_8KqZh4idtJM7bfuJ8AXSoTAGyJ_n42hLZwgNVUx8'
RAMSHA_FIGMA_ACCESS_TOKEN = 'figd_3bgofXhJbrbVRuPxlaXmrH-AwL6RTdr9hW1PLydz'
OPENAI_API_KEY = "sk-proj-TqTaxIMCk6fsrNcaGXE1yF-PehXerkG-e4EJaqGft33i13RlRJq_xRmiV_lGQUHdpQO3 5kxXhaT3BlbkFJ1xfcvTfnnPxsuNGzvhLdYBU25sc-VgK4QA7IhR0KdBWkqiijTRGjbsp1-zqKJnObr6lkftWyUA"
TEMP_TOKEN = "328267-66c5803b-80d4-4989-ad6f-8430d60fb714"

# Base prompt template that will be used for both OpenAI and Gemini
BASE_PROMPT_TEMPLATE = """
You are a world-class UX/UI design expert. Analyze the provided Figma design JSON.
Your task is to analyze ONLY the frames with the following node IDs and their dimensions: {frame_data}

{user_prompt_section}

For EACH of these specific frames, provide a detailed analysis. The final output must be a single, valid JSON object where each key is one of the frame's node IDs listed above.
The value for each key should be another JSON object with four keys: "heatmap", "report", "suggestions", and "ux_score".

For EACH frame, identify UI components or regions where users might get confused, stuck, or abandon the task.  
Provide these as an array called "drop_off_points". Each item should include:  
- "x": percentage horizontal coordinate (0-100)  
- "y": percentage vertical coordinate (0-100)  
- "reason": a brief natural language explanation of why this spot causes drop-off.
Include at least 1-2 drop-off points per frame if you find that something important to highlight else none can also happen.


IMPORTANT: For coordinates in heatmap and suggestions:
1. Use percentage-based coordinates (0-100) for both x and y values
2. x: 0 means left edge, 100 means right edge
3. y: 0 means top edge, 100 means bottom edge
4. Example: x: 50, y: 50 means center of the frame
5. DO NOT use pixel values, use percentages only
6. Make sure there are at least 6 heatmap points and suggestions in a single node

For the ux_score:
- Calculate a score from 0-100 based on your analysis
- Consider the number and severity of suggestions
- Consider the heatmap distribution
- Consider the overall design quality and user experience
- Higher scores indicate better UX

Example of the required final JSON output structure and make sure to follow it exactly:
{{
    "analysis_data": {{
        "3:15": {{
            "heatmap":  [{{"x": 50, "y": 50, "intensity": 0.9}}],
            "report": "...",
            "suggestions": [{{"x": 25, "y": 75, "suggestion": "Move button to bottom left"}}],
            "ux_score": 85,
            "drop_off_points": [
                {{"x":40,"y":60,"reason":"Users get stuck here because the button label is unclear."}},
                {{"x":80,"y":20,"reason":"High abandonment due to missing feedback after click."}},
                {{"x":10,"y":90,"reason":"Confusing navigation causes drop-off."}}
            ],
        }},
        "4:2": {{
            "heatmap":  [{{"x": 75, "y": 25, "intensity": 0.8}}],
            "report": "...",
            "suggestions": [{{"x": 10, "y": 90, "suggestion": "Increase contrast in bottom left"}}],
            "ux_score": 78,
            "drop_off_points": [
                {{"x":40,"y":60,"reason":"Users get stuck here because the button label is unclear."}},
                {{"x":80,"y":20,"reason":"High abandonment due to missing feedback after click."}},
                {{"x":10,"y":90,"reason":"Confusing navigation causes drop-off."}}
            ],
        }}
    }}
}}

Here is the Figma design data:
{figma_data}
"""

@csrf_exempt
def upload_design(request):
    """
    Upload a design (not used in this case as we fetch designs directly from Figma).
    """
    return render(request, 'upload.html')

@csrf_exempt
def fetch_figma_file(request):
    """
    Fetch the Figma file data using the Figma API.
    """
    file_id = request.GET.get('file_id', DEFAULT_FIGMA_FILE_ID)
    
    url = "https://api.figma.com/v1/me"
    headers = {"X-Figma-Token": FIGMA_ACCESS_TOKEN}

    response = requests.get(url, headers=headers)

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
        'Authorization': f'Bearer {OPENAI_API_KEY}',
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

    response = requests.post("https://api.openai.com/v1/chat/completions", json=openai_payload, headers=headers)
    response.raise_for_status()
    result = response.json()

    content = result["choices"][0]["message"]["content"]
    print("OpenAI response content:", content)

    heatmap_report = extract_json_from_model_response(content)
    return heatmap_report

@csrf_exempt
def call_gemini_heatmap(figma_data, user_prompt=''):
    """
    Get UX analysis from Google's Gemini API using direct HTTP requests.
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
    ]
    
    last_error = None
    for model_name in model_names:
        try:
            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={AVIALDO_GEMINI_KEY}"
            
            headers = {
                'Content-Type': 'application/json',
            }

            request_body = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.9,
                    "topK": 60,
                    "topP": 0.98,
                    "maxOutputTokens": 8192,
                    "candidateCount": 1,
                    "stopSequences": [],
                }
            }

            print(f"Attempting with model: {model_name}")
            response = requests.post(gemini_api_url, headers=headers, json=request_body, timeout=900)
            response.raise_for_status()
            
            response_json = response.json()
            if "candidates" in response_json and response_json["candidates"]:
                content_data = response_json["candidates"][0].get("content")
                if not content_data or "parts" not in content_data or not content_data["parts"]:
                    continue
                    
                parts = content_data["parts"]
                if "text" not in parts[0]:
                    continue
                    
                content = parts[0]["text"]
                heatmap_report = extract_json_from_model_response(content)
                
                if "analysis_data" in heatmap_report:
                    unexpected_frames = set(heatmap_report["analysis_data"].keys()) - set(frame_data.keys())
                    if unexpected_frames:
                        print(f"Warning: Response contains unexpected frame IDs: {unexpected_frames}")
                        heatmap_report["analysis_data"] = {
                            k: v for k, v in heatmap_report["analysis_data"].items() 
                            if k in frame_data.keys()
                        }
                
                return heatmap_report
                
        except requests.exceptions.HTTPError as e:
            last_error = e
            print(f"Failed with model {model_name}: {str(e)}")
            if e.response.status_code == 400 and "token count" in e.response.text.lower():
                print(f"Token limit exceeded with model {model_name}, trying next model...")
                continue
            if e.response.status_code == 404:
                print(f"Model {model_name} not found, trying next model...")
                continue
            raise Exception(f"Failed to call Gemini API (HTTPError): {str(e)}. Response: {e.response.text}")
        except Exception as e:
            last_error = e
            print(f"Error with model {model_name}: {str(e)}")
            continue
    
    if last_error:
        raise Exception(f"All Gemini models failed. Last error: {str(last_error)}")
    raise Exception("All Gemini models failed without specific error information")

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
        
        if not node_ids or not isinstance(node_ids, list):
            return JsonResponse({"error": "Invalid or missing 'node_ids' list."}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body."}, status=400)

    ids_query_param = ",".join(node_ids)
    url = f"https://api.figma.com/v1/images/{file_id}?ids={ids_query_param}&format=png&scale=2"
    headers = {"X-Figma-Token": FIGMA_ACCESS_TOKEN}

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

