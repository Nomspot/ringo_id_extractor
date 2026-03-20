import time
from google import genai
from google.genai import types



def create_job(project_id, bucket_id, model_name = "gemini-3.1-pro-preview"):
    client = genai.Client(
        vertexai=True, 
        project=project_id, 
        location="global" 
    )

    print(f"🚀 Starting Batch Job")
    try:
        batch_job = client.batches.create(
            model=model_name,
            src=f"gs://{bucket_id}/requests.jsonl",
            config=types.CreateBatchJobConfig(
                display_name="Israeli_ID_Final_Run",
                dest="gs://{bucket_id}/results/"
            )
        )
        print(f"✅ SUCCESS! Job Created: {batch_job.name}")
        print(f"You can now see it here: https://console.cloud.google.com/vertex-ai/batch-predictions?project={project_id}")

        return batch_job

    except Exception as e:
        print(f"❌ Hit a wall: {e}")
        
    return None