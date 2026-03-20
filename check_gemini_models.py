import vertexai
from vertexai.generative_models import GenerativeModel
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='vertexai')

# Initialize Vertex AI
vertexai.init(project="project-228d36c7-cf8a-4430-917", location="global")

# The most stable and advanced IDs for March 2026:
advanced_models = [
    "gemini-3.1-pro-preview",     # Deepest reasoning (use this for your ID extraction)
    "gemini-3-flash-preview",     # High-speed alternative
    "gemini-2.5-pro",              # The ultra-stable fallback
    "Gemini 2.0 Flash",
]

"""print("--- Testing Model Access ---")
for model_id in advanced_models:
    try:
        model = GenerativeModel(model_id)
        # We send a tiny 'hi' to verify it's active
        response = model.generate_content("hi", generation_config={"max_output_tokens": 1})
        print(f"✅ {model_id} is ACTIVE.")
    except Exception as e:
        print(f"❌ {model_id} failed. Error: {e}")"""

def is_model_available(model_name):
    print(f"--- Testing '{model_name}' Access ---")
    try:
        model = GenerativeModel(model_name)
        # We send a tiny 'hi' to verify it's active
        response = model.generate_content("hi", generation_config={"max_output_tokens": 1})
        print(f"✅ {model_name} is ACTIVE.")
        return True
    except Exception as e:
        print(f"❌ {model_name} failed. Error: {e}")
        return False