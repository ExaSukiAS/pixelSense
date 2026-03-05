import urllib.request
import json
import base64

class GeminiClient:
    def __init__(self, apiKey, modelName, onContentChunk=None):
        self.apiKey = apiKey
        self.modelName = modelName
        self.onContentChunk = onContentChunk
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelName}:streamGenerateContent?alt=sse"
    
    # Helper function to create the request payload
    def generatePayload(self, systemInstruction, prompt, base64Image=None):
        payload = {
            "system_instruction": {
                "parts": [
                    {"text": systemInstruction}
                ]
            },
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        # Add image if provided
        if base64Image:
            payload["contents"][0]["parts"].append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64Image
                }
            })
            
        return json.dumps(payload).encode('utf-8')

    # Function to call the Gemini API and handle streaming response
    def generateContentStream(self, systemInstruction, prompt, image=None):
        base64Image = base64.b64encode(image).decode('utf-8') if image else None

        requestPayload = self.generatePayload(systemInstruction, prompt, base64Image)

        req = urllib.request.Request(self.url, data=requestPayload)
        req.add_header('Content-Type', 'application/json')
        req.add_header('x-goog-api-key', self.apiKey)

        try:
            # using urlopen to get a file-like object
            with urllib.request.urlopen(req) as response:

                # Read line by line as data arrives
                for line in response:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith("data: "):
                        json_str = line[6:]
                        
                        # Handle potential "data: [DONE]" or empty data
                        if json_str == "[DONE]":
                            break
                        
                        try:
                            result = json.loads(json_str)
                            # Extract text chunk
                            text_chunk = result['candidates'][0]['content']['parts'][0]['text']
                            self.onContentChunk(text_chunk)
                        except Exception:
                            pass
            self.onContentChunk("#$$#") # indicates end of stream

        except Exception as e:
            print(f"Error: {e}")
