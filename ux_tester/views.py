import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import re

# Hardcoded Figma file ID
FIGMA_FILE_ID = '8DvxAgdawJcUG4SBbtwxzm'
FIGMA_ACCESS_TOKEN = 'figd_8KqZh4idtJM7bfuJ8AXSoTAGyJ_n42hLZwgNVUx8'
RAMSHA_FIGMA_ACCESS_TOKEN = 'figd_3bgofXhJbrbVRuPxlaXmrH-AwL6RTdr9hW1PLydz'
OPENAI_API_KEY = "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"
TEMP_TOKEN = "328267-66c5803b-80d4-4989-ad6f-8430d60fb714"

@csrf_exempt
def upload_design(request):
    """
    Upload a design (not used in this case as we fetch designs directly from Figma).
    """
    if request.method == 'POST' and request.FILES['design']:
        file = request.FILES['design']
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        file_url = fs.url(filename)
        return JsonResponse({'design_url': file_url})
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
    Analyze this Figma design data and simulate user interactions like clicks, hovers, drop-offs.
    Return a JSON list of heatmap points, each with x, y, and intensity from 0 to 1.
    Here is the design data:
    {json.dumps(figma_data)}

    Respond ONLY with a JSON array of objects: [{{"x": 123, "y": 456, "intensity": 0.8}}, ...]
    """

    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    openai_payload = {
        "model": "gpt-4o-mini",  # or "gpt-3.5-turbo"
        "messages": [
            {"role": "system", "content": "You are a UX analyst."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", json=openai_payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    # Extract the JSON array from the assistant message
    content = result["choices"][0]["message"]["content"]

    heatmap_data = extract_json_from_openai(content)
    return heatmap_data


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