import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import re

# Hardcoded Figma file ID
FIGMA_FILE_ID = '1J2MSZzASUTEKNrrQm5o8b'
FIGMA_ACCESS_TOKEN = 'figd_8KqZh4idtJM7bfuJ8AXSoTAGyJ_n42hLZwgNVUx8'
RAMSHA_FIGMA_ACCESS_TOKEN = 'figd_3bgofXhJbrbVRuPxlaXmrH-AwL6RTdr9hW1PLydz'
OPENAI_API_KEY = "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"
TEMP_TOKEN = "328267-66c5803b-80d4-4989-ad6f-8430d60fb714"
FIGMA_NODE_ID = '0:1';


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

    response = requests.get(url, headers=headers)



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
            heatmap_data = call_openai_heatmap(figma_data)
        except Exception as e:
            return JsonResponse({'error': f'OpenAI call failed: {str(e)}'}, status=500)

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

   heatmap_report = extract_json_from_openai(content)  # Your function to safely parse JSON from response

   return heatmap_report


def extract_json_from_openai(content):
    # Remove triple backticks or any markdown code fences
    cleaned = re.sub(r"```json|```", "", content, flags=re.IGNORECASE).strip()
    # Sometimes it can have extra explanation before/after JSON, try to extract JSON array/object part
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find first JSON array/object substring
        json_match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        else:
            raise

@csrf_exempt
def fetch_figma_image_url(request):
    """
    Fetch PNG image URL of a specific Figma node (frame) via Figma Image API.
    """
    headers = {"X-Figma-Token": FIGMA_ACCESS_TOKEN}
    url = f"https://api.figma.com/v1/images/{FIGMA_FILE_ID}?ids={FIGMA_NODE_ID}&format=png"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return JsonResponse({"error": f"Failed to fetch image URL: {str(e)}"}, status=500)

    data = response.json()
    images = data.get("images", {})
    image_url = images.get(FIGMA_NODE_ID)

    if not image_url:
        return JsonResponse({"error": "Image URL not found for given node ID"}, status=404)

    return JsonResponse({"image_url": image_url})