import json
import os
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings

from ux_tester.views import FIGMA_ACCESS_TOKEN, OPENAI_API_KEY_SULTAN



def fetch_figma_json(file_id):
    url = f'https://api.figma.com/v1/files/{file_id}'
    headers = {'X-Figma-Token': FIGMA_ACCESS_TOKEN}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def extract_frames_and_prototypes(figma_json):
    frames = []
    transitions = []
    canvases = figma_json.get('document', {}).get('children', [])
    for canvas in canvases:
        for node in canvas.get('children', []):
            if node.get('type') == 'FRAME':
                frame_id = node.get('id')
                frame_name = node.get('name')
                frames.append({'id': frame_id, 'name': frame_name})
                proto = node.get('prototype') or {}
                dest_id = proto.get('destinationId') or node.get('prototypeNodeID')
                if dest_id:
                    transitions.append({
                        'from': frame_id,
                        'to': dest_id,
                        'action': 'tap/click to navigate'
                    })
                if 'reactions' in node:
                    for reaction in node['reactions']:
                        dest = reaction.get('action', {}).get('destinationId')
                        if dest:
                            transitions.append({
                                'from': frame_id,
                                'to': dest,
                                'action': reaction.get('trigger', 'tap/click')
                            })
    return frames, transitions

def fetch_images_for_frames(file_id, frame_ids):
    url = f'https://api.figma.com/v1/images/{file_id}?ids={",".join(frame_ids)}&format=png&scale=2'
    headers = {'X-Figma-Token': FIGMA_ACCESS_TOKEN}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get('images', {})

def call_openai_to_generate_script(task_description, frames, transitions, frame_images):
    prompt = f"""
You are a UX expert. Given the frames and navigation:

Frames:
{json.dumps(frames, indent=2)}

Transitions:
{json.dumps(transitions, indent=2)}

Frame images URLs:
{json.dumps(frame_images, indent=2)}

Task: {task_description}

Generate a JSON video simulation script in the format:

{{
  "steps": [
    {{
      "frame_url": "URL from frame_images object",
      "action": "description of the action",
      "duration": seconds,
      "overlay_text": "text to show during this step"
    }},
    ...
  ]
}}

Make it a 10-20 seconds video simulation.
"""
    try:
        print("Sending request to OpenAI...")
        print("Prompt:", prompt)  # Debug log
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY_SULTAN}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a UX/UI expert and video script generator."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7,
        }
        
        print("OpenAI request data:", json.dumps(data, indent=2))
        
        response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
        response.raise_for_status()
        
        print("OpenAI response status:", response.status_code)
        print("OpenAI response:", response.text)
        
        response_json = response.json()
        if not response_json.get('choices'):
            raise ValueError("No choices in OpenAI response")
            
        content = response_json['choices'][0]['message']['content']
        print("OpenAI response content:", content)
        
        # Try to parse the content as JSON
        try:
            # First, try to find JSON in the content (in case there's additional text)
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                print("Extracted JSON string:", json_str)  # Debug log
                parsed_json = json.loads(json_str)
                print("Parsed JSON:", json.dumps(parsed_json, indent=2))  # Debug log
                return json_str
            else:
                raise ValueError("No JSON object found in response")
        except json.JSONDecodeError as e:
            print("JSON parsing error:", str(e))
            print("Content that failed to parse:", content)
            raise ValueError(f"Invalid JSON in OpenAI response: {str(e)}")
            
    except requests.exceptions.RequestException as e:
        print("OpenAI API request failed:", str(e))
        raise ValueError(f"OpenAI API request failed: {str(e)}")
    except Exception as e:
        print("Unexpected error in call_openai_to_generate_script:", str(e))
        raise ValueError(f"Error generating simulation script: {str(e)}")


@csrf_exempt
def generate_simulation(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    try:
        data = json.loads(request.body)
        design_data = data.get('design_data')
        task_description = data.get('task_description')

        if not design_data or not task_description:
            return JsonResponse({'error': 'Missing design_data or task_description.'}, status=400)

        if design_data['type'] != 'figma':
            return JsonResponse({'error': 'Only figma type supported in this example.'}, status=400)

        figma_file_id = design_data.get('id')
        print(f"Processing Figma file ID: {figma_file_id}")
        
        figma_json = fetch_figma_json(figma_file_id)
        frames, transitions = extract_frames_and_prototypes(figma_json)

        if not frames:
            return JsonResponse({'error': 'No frames found in Figma file.'}, status=400)

        frame_ids = [f['id'] for f in frames]
        frame_images = fetch_images_for_frames(figma_file_id, frame_ids)
        
        print(f"Found {len(frames)} frames and {len(transitions)} transitions")
        print("Frame images:", frame_images)

        # Call OpenAI to generate script
        simulation_script_str = call_openai_to_generate_script(task_description, frames, transitions, frame_images)
        print("Received simulation script:", simulation_script_str)
        
        try:
            simulation_script = json.loads(simulation_script_str)
        except json.JSONDecodeError as e:
            print("Error parsing simulation script:", str(e))
            print("Script content:", simulation_script_str)
            raise ValueError(f"Invalid simulation script format: {str(e)}")

        # Create static directory if it doesn't exist
        static_dir = os.path.join(settings.STATIC_ROOT, 'assets', 'simulations', 'images')
        os.makedirs(static_dir, exist_ok=True)

        # Download and store images locally
        for i, step in enumerate(simulation_script['steps'], 1):
            try:
                print(f"Processing step {i}:", step)  # Debug log
                frame_url = step.get('frame_url')
                if not frame_url:
                    print(f"Warning: No frame_url in step {i}, skipping")
                    continue

                # Generate filename using Figma file ID and frame ID
                image_filename = f'{figma_file_id}_{frame_url.split("/")[-1]}.png'
                image_path = os.path.join('assets', 'simulations', 'images', image_filename)
                
                # Download the image
                print(f"Downloading image from: {frame_url}")  # Debug log
                response = requests.get(frame_url)
                response.raise_for_status()
                
                # Save the image to STATIC_ROOT
                full_path = os.path.join(settings.STATIC_ROOT, image_path)
                with open(full_path, 'wb') as f:
                    f.write(response.content)
                
                # Update the frame_url to point to our static storage
                step['frame_url'] = f"assets/simulations/images/{image_filename}"
                print(f"Saved image to: {full_path}")
                print(f"Image URL: {step['frame_url']}")
            except Exception as e:
                print(f"Error processing step {i}:", str(e))
                raise

        # Return the simulation data directly
        return JsonResponse({
            'simulation_data': simulation_script
        })

    except Exception as e:
        print(f"Error in generate_simulation: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
