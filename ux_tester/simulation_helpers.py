import json
import os
from django.shortcuts import render
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.conf import settings
import base64
from PIL import Image, ImageDraw
import io
import datetime
from google import genai
from google.genai import types
import re

from ux_tester.views import DEFAULT_FIGMA_FILE_ID, FIGMA_TOKENS, OPENAI_API_KEY_SULTAN, GLOBAL_SEARCH_API_KEY

# Simulation prompt template
SIMULATION_PROMPT = '''
You are a UX expert. Given the frames, interactions, and actual images from Figma:

Frames:
{frames}

Interactions:
{interactions}

Task: {task_description}

For each step in the simulation, describe the visual changes needed to show the interaction:
1. Cursor position and movement
2. Click effects
3. Text input animations
4. Transition effects

Generate a JSON video simulation script in this format:

{{
  "steps": [
    {{
      "frame_id": "ID of the frame",
      "action": "description of the action",
      "duration": seconds,
      "overlay_text": "text to show during this step",
      "changes": [
        {{
          "type": "cursor|click|highlight|text",
          "position": {{
            "x": number,
            "y": number,
            "width": number (optional),
            "height": number (optional)
          }},
          "text": "text to show" (for text type)
        }}
      ],
      "interaction": {{
        "element_id": "ID of the element being interacted with",
        "element_name": "Name of the element",
        "element_type": "Type of the element",
        "interaction_type": "Type of interaction from Figma",
        "position": {{
          "x": number,
          "y": number,
          "width": number,
          "height": number
        }}
      }}
    }}
  ]
}}

Make it a 10-20 seconds video simulation. For each step, describe the visual changes needed to show the interaction.
'''

@csrf_exempt
def simulation(request):
    """
    Render the simulation page.
    """
    context = {'figma_file_id': DEFAULT_FIGMA_FILE_ID}
    return render(request, 'simulation.html', context)


def fetch_figma_json(file_id, access_token):
    url = f'https://api.figma.com/v1/files/{file_id}'
    headers = {'X-Figma-Token': access_token}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def extract_frames_and_prototypes(figma_json):
    frames = []
    interactions = []
    
    def extract_node_interactions(node, parent_frame=None):
        node_id = node.get('id')
        node_name = node.get('name')
        node_type = node.get('type')
        
        # Extract interactions from prototype data
        proto = node.get('prototype') or {}
        if proto:
            dest_id = proto.get('destinationId') or node.get('prototypeNodeID')
            if dest_id:
                interactions.append({
                    'element_id': node_id,
                    'element_name': node_name,
                    'element_type': node_type,
                    'frame_id': parent_frame,
                    'interaction_type': proto.get('transitionType', 'instant'),
                    'destination_id': dest_id,
                    'action': proto.get('action', 'tap/click'),
                    'animation': proto.get('animation', {}),
                    'position': {
                        'x': node.get('absoluteBoundingBox', {}).get('x', 0),
                        'y': node.get('absoluteBoundingBox', {}).get('y', 0),
                        'width': node.get('absoluteBoundingBox', {}).get('width', 0),
                        'height': node.get('absoluteBoundingBox', {}).get('height', 0)
                    }
                })
        
        # Extract reactions
        if 'reactions' in node:
            for reaction in node['reactions']:
                dest = reaction.get('action', {}).get('destinationId')
                if dest:
                    interactions.append({
                        'element_id': node_id,
                        'element_name': node_name,
                        'element_type': node_type,
                        'frame_id': parent_frame,
                        'interaction_type': reaction.get('transitionType', 'instant'),
                        'destination_id': dest,
                        'action': reaction.get('trigger', 'tap/click'),
                        'animation': reaction.get('animation', {}),
                        'position': {
                            'x': node.get('absoluteBoundingBox', {}).get('x', 0),
                            'y': node.get('absoluteBoundingBox', {}).get('y', 0),
                            'width': node.get('absoluteBoundingBox', {}).get('width', 0),
                            'height': node.get('absoluteBoundingBox', {}).get('height', 0)
                        }
                    })
        
        # Recursively process children
        for child in node.get('children', []):
            extract_node_interactions(child, node_id if node_type == 'FRAME' else parent_frame)
    
    # Process all canvases and their children
    canvases = figma_json.get('document', {}).get('children', [])
    for canvas in canvases:
        for node in canvas.get('children', []):
            if node.get('type') == 'FRAME':
                frame_id = node.get('id')
                frame_name = node.get('name')
                frames.append({
                    'id': frame_id,
                    'name': frame_name,
                    'position': {
                        'x': node.get('absoluteBoundingBox', {}).get('x', 0),
                        'y': node.get('absoluteBoundingBox', {}).get('y', 0),
                        'width': node.get('absoluteBoundingBox', {}).get('width', 0),
                        'height': node.get('absoluteBoundingBox', {}).get('height', 0)
                    }
                })
                extract_node_interactions(node, frame_id)
    
    return frames, interactions

def fetch_images_for_frames(file_id, frame_ids, access_token):
    url = f'https://api.figma.com/v1/images/{file_id}?ids={",".join(frame_ids)}&format=png&scale=2'
    headers = {'X-Figma-Token': access_token}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    images = r.json().get('images', {})
    
    # Download all images
    downloaded_images = {}
    for frame_id, image_url in images.items():
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        # Ensure proper base64 padding
        image_data = base64.b64encode(img_response.content).decode('utf-8')
        # Add padding if needed
        padding = len(image_data) % 4
        if padding:
            image_data += '=' * (4 - padding)
        downloaded_images[frame_id] = {
            'url': image_url,
            'data': image_data
        }
    
    return downloaded_images

def manipulate_image(image_data, changes):
    """Apply visual changes to an image based on the model's instructions."""
    try:
        # Ensure proper base64 padding
        padding = len(image_data) % 4
        if padding:
            image_data += '=' * (4 - padding)
            
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        draw = ImageDraw.Draw(img)
        
        # Apply changes based on the model's instructions
        for change in changes:
            if change['type'] == 'cursor':
                # Draw cursor
                x, y = change['position']['x'], change['position']['y']
                draw.polygon([(x, y), (x+15, y+25), (x+5, y+20)], fill='white')
                
            elif change['type'] == 'click':
                # Draw click effect
                x, y = change['position']['x'], change['position']['y']
                draw.ellipse([x-10, y-10, x+10, y+10], outline='white', width=2)
                
            elif change['type'] == 'highlight':
                # Draw highlight
                x, y = change['position']['x'], change['position']['y']
                w, h = change['position']['width'], change['position']['height']
                draw.rectangle([x, y, x+w, y+h], outline='white', width=2)
                
            elif change['type'] == 'text':
                # Draw text input
                x, y = change['position']['x'], change['position']['y']
                draw.rectangle([x, y, x+200, y+30], outline='white', width=1)
                draw.text((x+10, y+5), change['text'], fill='white')
        
        # Convert back to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error in manipulate_image: {str(e)}")
        raise ValueError(f"Failed to manipulate image: {str(e)}")

def call_openai_to_generate_script(task_description, frames, interactions, frame_images):
    # Prepare the images for OpenAI
    image_descriptions = []
    for frame_id, image_data in frame_images.items():
        image_descriptions.append({
            'frame_id': frame_id,
            'image_data': image_data['data'],
            'interactions': [i for i in interactions if i['frame_id'] == frame_id]
        })

    # Format the prompt with actual data
    prompt = SIMULATION_PROMPT.format(
        frames=json.dumps(frames, indent=2),
        interactions=json.dumps(interactions, indent=2),
        task_description=task_description
    )

    try:
        print("Sending request to OpenAI...")
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY_SULTAN}',
            'Content-Type': 'application/json'
        }
        
        # Prepare messages with images
        messages = [
            {
                "role": "system",
                "content": "You are a UX/UI expert. You will receive Figma frames and their interactions. For each frame, describe the visual changes needed to show the interaction happening (cursor movements, clicks, text input, etc.)."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        # Add each image as a separate message
        for img_desc in image_descriptions:
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_desc['image_data']}",
                    "detail": "high"
                }
            })
            messages[1]["content"].append({
                "type": "text",
                "text": f"Frame {img_desc['frame_id']} with interactions: {json.dumps(img_desc['interactions'])}"
            })

        data = {
            "model": "gpt-4.1",
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.7,
        }
        
        print("OpenAI request data:", json.dumps(data, indent=2))
        
        response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
        print("OpenAI response status:", response.status_code)
        print("OpenAI response headers:", dict(response.headers))
        print("OpenAI response text:", response.text)
        
        response.raise_for_status()
        
        response_json = response.json()
        if not response_json.get('choices'):
            raise ValueError("No choices in OpenAI response")
            
        content = response_json['choices'][0]['message']['content']
        print("OpenAI response content:", content)
        
        # Try to parse the content as JSON
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                print("Extracted JSON string:", json_str)
                parsed_json = json.loads(json_str)
                print("Parsed JSON:", json.dumps(parsed_json, indent=2))
                
                # Apply the changes to each frame
                for step in parsed_json['steps']:
                    frame_id = step['frame_id']
                    if frame_id in frame_images:
                        try:
                            manipulated_image = manipulate_image(
                                frame_images[frame_id]['data'],
                                step['changes']
                            )
                            step['manipulated_image'] = f"data:image/png;base64,{manipulated_image}"
                        except Exception as e:
                            print(f"Error manipulating image for step {step['action']}: {str(e)}")
                            raise
                
                return json.dumps(parsed_json)
            else:
                print("Content that failed to parse:", content)
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

def call_gemini_to_generate_script(task_description, frames, interactions, frame_images):
    """Generate simulation script using Gemini API."""
    try:
        client = genai.Client(api_key=GLOBAL_SEARCH_API_KEY)
        
        # Format the prompt with actual data
        prompt = SIMULATION_PROMPT.format(
            frames=json.dumps(frames, indent=2),
            interactions=json.dumps(interactions, indent=2),
            task_description=task_description
        )
        
        # Prepare content for Gemini
        contents = []
        
        # Add text prompt
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Add images and their interactions
        for frame_id, image_data in frame_images.items():
            # Add image
            contents.append({
                "role": "user",
                "parts": [{
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data['data']
                    }
                }]
            })
            
            # Add frame interactions as text
            frame_interactions = [i for i in interactions if i['frame_id'] == frame_id]
            contents.append({
                "role": "user",
                "parts": [{
                    "text": f"Frame {frame_id} with interactions: {json.dumps(frame_interactions)}"
                }]
            })
        
        # Generate content using the model
        response = client.models.generate_content(
            model="gemini-1.5-pro-latest",
            contents=contents
        )
        
        print("Gemini response:", response)
        
        if not response.candidates:
            raise ValueError("No candidates in Gemini response")
            
        content = response.candidates[0].content.parts[0].text
        print("Gemini response content:", content)
        
        # Parse the response
        try:
            # Clean the content by removing comments and markdown code blocks
            cleaned_content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)  # Remove single-line comments
            cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)  # Remove multi-line comments
            cleaned_content = re.sub(r'```(?:json)?|```', '', cleaned_content, flags=re.IGNORECASE).strip()  # Remove markdown code blocks
            
            json_start = cleaned_content.find('{')
            json_end = cleaned_content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_content[json_start:json_end]
                print("Extracted JSON string:", json_str)
                parsed_json = json.loads(json_str)
                print("Parsed JSON:", json.dumps(parsed_json, indent=2))
                
                # Apply the changes to each frame
                for step in parsed_json['steps']:
                    frame_id = step['frame_id']
                    if frame_id in frame_images:
                        try:
                            manipulated_image = manipulate_image(
                                frame_images[frame_id]['data'],
                                step['changes']
                            )
                            step['manipulated_image'] = f"data:image/png;base64,{manipulated_image}"
                        except Exception as e:
                            print(f"Error manipulating image for step {step['action']}: {str(e)}")
                            raise
                
                return json.dumps(parsed_json)
            else:
                print("Content that failed to parse:", cleaned_content)
                raise ValueError("No JSON object found in response")
        except json.JSONDecodeError as e:
            print("JSON parsing error:", str(e))
            print("Content that failed to parse:", cleaned_content)
            raise ValueError(f"Invalid JSON in Gemini response: {str(e)}")
            
    except Exception as e:
        print(f"Error in call_gemini_to_generate_script: {str(e)}")
        raise ValueError(f"Error generating simulation script with Gemini: {str(e)}")

def generate_simulation_script(task_description, frames, interactions, frame_images, use_gemini=False):
    """Generate simulation script using either OpenAI or Gemini."""
    try:
        if use_gemini and GLOBAL_SEARCH_API_KEY:
            print("Using Gemini for simulation generation...")
            return call_gemini_to_generate_script(task_description, frames, interactions, frame_images)
        else:
            print("Using OpenAI for simulation generation...")
            return call_openai_to_generate_script(task_description, frames, interactions, frame_images)
    except Exception as e:
        print(f"Error in generate_simulation_script: {str(e)}")
        # If the first attempt fails, try the other model
        try:
            if use_gemini:
                print("Falling back to OpenAI...")
                return call_openai_to_generate_script(task_description, frames, interactions, frame_images)
            else:
                print("Falling back to Gemini...")
                return call_gemini_to_generate_script(task_description, frames, interactions, frame_images)
        except Exception as fallback_error:
            print(f"Fallback also failed: {str(fallback_error)}")
            raise ValueError(f"Both OpenAI and Gemini failed to generate simulation: {str(e)}")

@csrf_exempt
def generate_simulation(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    try:
        data = json.loads(request.body)
        design_data = data.get('design_data')
        task_description = data.get('task_description')
        access_token = data.get('access_token')
        use_gemini = data.get('use_gemini', False)

        if not design_data or not task_description:
            return JsonResponse({'error': 'Missing design_data or task_description.'}, status=400)

        if not access_token:
            return JsonResponse({'error': 'No access token provided'}, status=400)

        # Get the actual token value if it's a predefined token
        if access_token in FIGMA_TOKENS:
            access_token = FIGMA_TOKENS[access_token]

        if design_data['type'] != 'figma':
            return JsonResponse({'error': 'Only figma type supported in this example.'}, status=400)

        figma_file_id = design_data.get('id')
        print(f"Processing Figma file ID: {figma_file_id}")
        
        figma_json = fetch_figma_json(figma_file_id, access_token)
        frames, interactions = extract_frames_and_prototypes(figma_json)

        if not frames:
            return JsonResponse({'error': 'No frames found in Figma file.'}, status=400)

        frame_ids = [f['id'] for f in frames]
        frame_images = fetch_images_for_frames(figma_file_id, frame_ids, access_token)
        
        print(f"Found {len(frames)} frames and {len(interactions)} interactions")
        print("Frame images:", frame_images)

        # Call the appropriate model to generate script
        simulation_script_str = generate_simulation_script(
            task_description, 
            frames, 
            interactions, 
            frame_images,
            use_gemini=use_gemini
        )
        print("Received simulation script:", simulation_script_str)
        
        try:
            simulation_script = json.loads(simulation_script_str)
        except json.JSONDecodeError as e:
            print("Error parsing simulation script:", str(e))
            print("Script content:", simulation_script_str)
            raise ValueError(f"Invalid simulation script format: {str(e)}")

        # Commenting out image saving code since we're using base64 data directly
        """
        # Create static directory if it doesn't exist
        static_dir = os.path.join(settings.BASE_DIR, 'static', 'assets', 'simulations', 'images')
        staticfiles_dir = os.path.join(settings.BASE_DIR, 'staticfiles', 'assets', 'simulations', 'images')
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(staticfiles_dir, exist_ok=True)

        # Save manipulated images
        for i, step in enumerate(simulation_script['steps'], 1):
            try:
                print(f"Processing step {i}:", step)
                
                # Validate manipulated_image
                image_data = step['manipulated_image']
                if not isinstance(image_data, str) or not image_data.startswith('data:image/png;base64,'):
                    raise ValueError(f"Invalid image data format in step {i}. Expected base64-encoded PNG image.")
                
                # Remove data URL prefix
                image_data = image_data.replace('data:image/png;base64,', '')
                
                # Add padding if needed
                padding = len(image_data) % 4
                if padding:
                    image_data += '=' * (4 - padding)
                
                try:
                    image_bytes = base64.b64decode(image_data)
                except Exception as e:
                    print(f"Base64 decode error for step {i}:", str(e))
                    print("Image data length:", len(image_data))
                    print("Image data preview:", image_data[:100])
                    raise ValueError(f"Invalid base64 data in step {i}: {str(e)}")
                
                image_filename = f'{figma_file_id}_step_{i}.png'
                image_path = os.path.join('assets', 'simulations', 'images', image_filename)
                
                # Save to static directory
                static_path = os.path.join(static_dir, image_filename)
                with open(static_path, 'wb') as f:
                    f.write(image_bytes)
                
                # Save to staticfiles directory
                staticfiles_path = os.path.join(staticfiles_dir, image_filename)
                with open(staticfiles_path, 'wb') as f:
                    f.write(image_bytes)
                
                # Update the frame_url to point to our static storage
                step['frame_url'] = f"assets/simulations/images/{image_filename}"
                print(f"Saved manipulated image to: {static_path}")
                print(f"Image URL: {step['frame_url']}")
            except Exception as e:
                print(f"Error processing step {i}:", str(e))
                raise
        """

        # Return the simulation data
        return JsonResponse({
            'simulation_data': simulation_script
        })

    except Exception as e:
        print(f"Error in generate_simulation: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Commenting out the save_manipulated_image function since it's no longer used
"""
def save_manipulated_image(image_data, filename):
    # Create directories if they don't exist
    static_dir = os.path.join(settings.BASE_DIR, 'static', 'assets', 'simulations', 'images')
    staticfiles_dir = os.path.join(settings.BASE_DIR, 'staticfiles', 'assets', 'simulations', 'images')
    
    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(staticfiles_dir, exist_ok=True)
    
    # Save to static directory
    static_path = os.path.join(static_dir, filename)
    with open(static_path, 'wb') as f:
        f.write(image_data)
    
    # Save to staticfiles directory
    staticfiles_path = os.path.join(staticfiles_dir, filename)
    with open(staticfiles_path, 'wb') as f:
        f.write(image_data)
    
    # Return the relative path for the URL
    return os.path.join('assets', 'simulations', 'images', filename)
"""
